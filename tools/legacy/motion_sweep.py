#!/usr/bin/env python3
"""Collect reproducible EVN ALPHA motor tuning datasets over one CDC session."""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial not installed")

from motion_metrics import compute, load_last_trace, verdicts

RP2040_VID = 0x2E8A
RESULTS = os.path.join("bench", "results")
TRACE_SECONDS = 2.65


def trace_block_rows_valid(start, next_start, rows):
    if len(rows) != next_start - start:
        return False
    timestamps = [row[0] for row in rows]
    if len(timestamps) >= 2:
        sample_ms = timestamps[1] - timestamps[0]
    elif start > 0:
        sample_ms, remainder = divmod(timestamps[0], start)
        if remainder:
            return False
    else:
        sample_ms = 1
    return sample_ms > 0 and timestamps == [index * sample_ms
                                             for index in range(start, next_start)]


def find_port(requested=None):
    if requested:
        return requested
    for port in list_ports.comports():
        if port.vid == RP2040_VID:
            return port.device
    return None


class BoardSession:
    def __init__(self, port, min_battery_mv=6500, min_cell_mv=3000,
                 max_battery_age_us=250000):
        self.last_trace_data = b""
        self.min_battery_mv = min_battery_mv
        self.min_cell_mv = min_cell_mv
        self.max_battery_age_us = max_battery_age_us
        self.serial = serial.Serial(port, 115200, timeout=0.05, write_timeout=2.0)
        self.serial.dtr = False
        time.sleep(0.05)
        self.serial.dtr = True
        self.read_for(1.0)
        self.send("S", 0.5, expect="Core1:", retries=3)

    def read_for(self, seconds):
        deadline = time.time() + seconds
        chunks = []
        while time.time() < deadline:
            chunk = self.serial.read(4096)
            if chunk:
                chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", "replace")

    def write_command(self, command, timeout_s=2.0):
        pending = command.encode("ascii") + b"\n"
        deadline = time.time() + timeout_s
        while pending and time.time() < deadline:
            written = self.serial.write(pending)
            if written:
                pending = pending[written:]
            else:
                self.read_for(0.05)
        if pending:
            raise TimeoutError(f"command write did not queue: {command!r}")

    def send(self, command, read_seconds=0.20, expect=None, retries=3):
        responses = []
        for _ in range(retries):
            self.write_command(command)
            response = self.read_for(read_seconds)
            if expect and expect not in response:
                response += self.read_for(1.0)
            responses.append(response)
            if not expect or expect in response:
                return "".join(responses)
        raise RuntimeError(
            f"command not acknowledged after {retries} attempts: {command!r}; "
            f"response={''.join(responses)!r}")

    def require_battery(self):
        response = self.send("B", 0.20, expect="BATTERY")
        line = next((item for item in response.splitlines()
                     if item.startswith("BATTERY")), "")
        if "unavailable" in line:
            raise RuntimeError("battery telemetry unavailable before motion")
        fields = dict(token.split("=", 1) for token in line.split() if "=" in token)
        battery = {name: int(fields[name]) for name in
                   ("pack_mv", "cell1_mv", "cell2_mv", "age_us")}
        if battery["age_us"] > self.max_battery_age_us:
            raise RuntimeError(
                f"battery sample stale: {battery['age_us']} us > {self.max_battery_age_us} us")
        if battery["pack_mv"] < self.min_battery_mv:
            raise RuntimeError(
                f"battery too low: {battery['pack_mv']} mV < {self.min_battery_mv} mV")
        low_cell = min(battery["cell1_mv"], battery["cell2_mv"])
        if low_cell < self.min_cell_mv:
            raise RuntimeError(
                f"battery cell too low: {low_cell} mV < {self.min_cell_mv} mV")
        return battery

    def read_trace(self, timeout_s=60.0):
        deadline = time.time() + timeout_s
        data = bytearray()
        begin = -1
        while time.time() < deadline:
            chunk = self.serial.read(4096)
            if chunk:
                data.extend(chunk)
            if begin < 0:
                begin = data.find(b"TRACE BEGIN")
                if begin < 0 and len(data) > 4096:
                    del data[:-64]
            if begin >= 0:
                end = data.find(b"TRACE END", begin)
                if end >= 0:
                    newline = data.find(b"\n", end)
                    if newline >= 0:
                        return bytes(data[begin:newline + 1]).decode("utf-8", "replace")
        self.last_trace_data = bytes(data)
        raise TimeoutError(
            f"trace did not produce an ordered frame: bytes={len(data)} begin={begin}")

    def read_trace_block(self, start, count=32, retries=3, timeout_s=5.0):
        block_marker = f"TRACE BLOCK start={start} ".encode("ascii")
        first_marker = b"TRACE BEGIN" if start == 0 else block_marker
        end_marker = b"TRACE BLOCK END "
        last_data = b""
        for _ in range(retries):
            self.write_command(f"D {start} {count}")
            deadline = time.time() + timeout_s
            data = bytearray()
            begin = -1
            while time.time() < deadline:
                chunk = self.serial.read(4096)
                if chunk:
                    data.extend(chunk)
                if begin < 0:
                    begin = data.find(first_marker)
                if begin >= 0:
                    end = data.find(end_marker, begin)
                    if end >= 0:
                        newline = data.find(b"\n", end)
                        if newline >= 0:
                            response = bytes(data[begin:newline + 1])
                            decoded = response.decode("utf-8", "replace")
                            end_line = decoded[decoded.rfind("TRACE BLOCK END "):]
                            fields = dict(token.split("=", 1) for token in end_line.split()
                                          if "=" in token)
                            next_start = int(fields["next"])
                            total = int(fields["total"])
                            block_line = f"TRACE BLOCK start={start} count={next_start - start}\n"
                            block_at = decoded.find(block_line)
                            end_at = decoded.rfind("TRACE BLOCK END ")
                            if block_at < 0 or end_at < block_at:
                                last_data = response
                                break

                            csv_rows = []
                            for line in decoded[block_at + len(block_line):end_at].splitlines():
                                parts = line.split(",")
                                if len(parts) != 8:
                                    continue
                                try:
                                    csv_rows.append([int(part) for part in parts])
                                except ValueError:
                                    continue
                            first_block_valid = start != 0 or (
                                all(field in decoded for field in (
                                    "TRACE BEGIN ", " target=", " vmax=", " accel=",
                                    " vscale=", " ascale=", " vsrc=", " vwin="))
                                and "t_ms,ref_mdeg,enc_mdeg,hat_mdeg,vref_mdegs," in decoded
                            )
                            final_block_valid = next_start < total or "TRACE END\n" in decoded
                            if (trace_block_rows_valid(start, next_start, csv_rows)
                                    and first_block_valid
                                    and final_block_valid):
                                return decoded, next_start, total
                            last_data = response
                            break
            last_data = bytes(data)
            self.read_for(0.1)
        self.last_trace_data = last_data
        raise TimeoutError(f"trace block {start} incomplete after {retries} attempts")

    def pull_trace(self, block_rows=32):
        chunks = []
        start = 0
        total = None
        while total is None or start < total:
            response, next_start, response_total = self.read_trace_block(start, block_rows)
            if next_start <= start:
                raise RuntimeError(f"trace block made no progress: {start} -> {next_start}")
            if total is not None and response_total != total:
                raise RuntimeError(f"trace total changed: {total} -> {response_total}")
            total = response_total
            chunks.append(response)
            start = next_start
        frame = "".join(chunks)
        if "TRACE BEGIN" not in frame or "TRACE END\n" not in frame:
            raise RuntimeError("pulled trace is missing frame markers")
        return frame

    def close(self):
        try:
            try:
                self.send("c", 0.5)
            except (serial.SerialException, serial.SerialTimeoutException, OSError):
                pass
        finally:
            self.serial.close()


def gain_cases():
    large = [
        ("L0", 8.0e-5, 1.0e-6, 1.0e-6),
        ("L1", 1.0e-4, 1.0e-6, 2.0e-6),
        ("L2", 1.2e-4, 1.0e-6, 2.5e-6),
        ("L3", 1.4e-4, 1.0e-6, 3.0e-6),
    ]
    medium = [
        ("M0", 8.0e-5, 8.0e-7, 8.0e-7),
        ("M1", 1.0e-4, 8.0e-7, 1.5e-6),
        ("M2", 1.2e-4, 8.0e-7, 2.0e-6),
        ("M3", 1.4e-4, 8.0e-7, 2.5e-6),
    ]
    cases = []
    for axis, candidates in ((1, large), (3, medium)):
        for label, kp, ki, kv in candidates:
            for direction, delta in (("pos", 90.0), ("neg", -90.0)):
                cases.append({
                    "name": f"{label}_{direction}", "axis": axis,
                    "delta": delta, "vmax": 180.0, "accel": 900.0,
                    "kp": kp, "ki": ki, "kv": kv,
                    "start_duty": 0.12, "hold_duty": 0.12,
                })
    return cases


def medium_breakaway_cases():
    cases = []
    for label, start_duty in (("B0", 0.45), ("B1", 0.55), ("B2", 0.65), ("B3", 0.75)):
        for direction, delta in (("pos", 90.0), ("neg", -90.0)):
            cases.append({
                "name": f"{label}_{direction}", "axis": 3,
                "delta": delta, "vmax": 180.0, "accel": 900.0,
                "kp": 1.2e-4, "ki": 8.0e-7, "kv": 2.0e-6,
                "start_duty": start_duty, "hold_duty": 0.45,
            })
    return cases


def dynamics_cases():
    cases = []
    for label, kv in (("LD0", 3.0e-6), ("LD1", 4.0e-6),
                      ("LD2", 5.0e-6), ("LD3", 6.0e-6)):
        for direction, delta in (("pos", 90.0), ("neg", -90.0)):
            cases.append({
                "name": f"{label}_{direction}", "axis": 1,
                "delta": delta, "vmax": 180.0, "accel": 900.0,
                "kp": 1.4e-4, "ki": 1.0e-6, "kv": kv,
                "start_duty": 0.12, "hold_duty": 0.12,
            })
    for label, kv in (("MD0", 2.0e-6), ("MD1", 3.0e-6),
                      ("MD2", 4.0e-6), ("MD3", 5.0e-6)):
        for direction, delta in (("pos", 90.0), ("neg", -90.0)):
            cases.append({
                "name": f"{label}_{direction}", "axis": 3,
                "delta": delta, "vmax": 180.0, "accel": 900.0,
                "kp": 1.2e-4, "ki": 8.0e-7, "kv": kv,
                "start_duty": 0.65, "hold_duty": 0.55,
            })
    return cases


def edge_speed_cases():
    cases = []
    for axis, prefix, kp, ki, start, hold, gains in (
        (1, "LE", 1.4e-4, 1.0e-6, 0.12, 0.12, (1.0e-6, 2.0e-6, 3.0e-6)),
        (3, "ME", 1.2e-4, 8.0e-7, 0.65, 0.55, (5.0e-7, 1.0e-6, 1.5e-6)),
    ):
        for index, kv in enumerate(gains):
            for direction, delta in (("pos", 90.0), ("neg", -90.0)):
                cases.append({
                    "name": f"{prefix}{index}_{direction}", "axis": axis,
                    "delta": delta, "vmax": 180.0, "accel": 900.0,
                    "kp": kp, "ki": ki, "kv": kv,
                    "start_duty": start, "hold_duty": hold,
                    "speed_source": 2,
                })
    return cases


def filtered_edge_cases():
    cases = []
    for axis, prefix, kp, ki, start, hold, combinations in (
        (1, "LF", 1.4e-4, 1.0e-6, 0.12, 0.12,
         ((0.03, 3.0e-6), (0.03, 5.0e-6), (0.06, 3.0e-6), (0.06, 5.0e-6))),
        (3, "MF", 1.2e-4, 8.0e-7, 0.65, 0.55,
         ((0.03, 5.0e-7), (0.03, 1.0e-6), (0.06, 5.0e-7), (0.06, 1.0e-6))),
    ):
        for index, (alpha, kv) in enumerate(combinations):
            for direction, delta in (("pos", 90.0), ("neg", -90.0)):
                cases.append({
                    "name": f"{prefix}{index}_{direction}", "axis": axis,
                    "delta": delta, "vmax": 180.0, "accel": 900.0,
                    "kp": kp, "ki": ki, "kv": kv,
                    "start_duty": start, "hold_duty": hold,
                    "speed_source": 3, "speed_alpha": alpha,
                })
    return cases


def observer_speed_cases():
    cases = []
    for axis, prefix, kp, ki, start, hold, gains in (
        (1, "LO", 1.4e-4, 1.0e-6, 0.12, 0.12, (1.0e-6, 2.0e-6, 3.0e-6)),
        (3, "MO", 1.2e-4, 8.0e-7, 0.65, 0.55, (2.5e-7, 5.0e-7, 7.5e-7)),
    ):
        for index, kv in enumerate(gains):
            for direction, delta in (("pos", 90.0), ("neg", -90.0)):
                cases.append({
                    "name": f"{prefix}{index}_{direction}", "axis": axis,
                    "delta": delta, "vmax": 180.0, "accel": 900.0,
                    "kp": kp, "ki": ki, "kv": kv,
                    "start_duty": start, "hold_duty": hold,
                    "speed_source": 0, "speed_alpha": 0.05,
                })
    return cases


def profile_margin_cases():
    cases = []
    margins = ((0.95, 0.80), (0.95, 0.65), (0.90, 0.80), (0.90, 0.65))
    for axis, prefix, kp, ki, kv, start, hold in (
        (1, "LM", 1.4e-4, 1.0e-6, 6.0e-6, 0.12, 0.12),
        (3, "MM", 1.2e-4, 8.0e-7, 2.0e-6, 0.65, 0.45),
    ):
        for index, (vel_scale, accel_scale) in enumerate(margins):
            for direction, delta in (("pos", 90.0), ("neg", -90.0)):
                cases.append({
                    "name": f"{prefix}{index}_{direction}", "axis": axis,
                    "delta": delta, "vmax": 180.0, "accel": 900.0,
                    "kp": kp, "ki": ki, "kv": kv,
                    "start_duty": start, "hold_duty": hold,
                    "speed_source": 1, "speed_alpha": 0.05,
                    "vel_scale": vel_scale, "accel_scale": accel_scale,
                })
    return cases


def margin_refine_cases():
    cases = []
    for direction, delta in (("pos", 90.0), ("neg", -90.0)):
        cases.append({
            "name": f"LR_{direction}", "axis": 1,
            "delta": delta, "vmax": 180.0, "accel": 900.0,
            "kp": 1.4e-4, "ki": 1.0e-6, "kv": 6.0e-6,
            "start_duty": 0.12, "hold_duty": 0.12,
            "speed_source": 1, "speed_alpha": 0.05,
            "vel_scale": 0.90, "accel_scale": 0.60,
        })
    margins = ((0.85, 0.50), (0.85, 0.40), (0.80, 0.50), (0.80, 0.40))
    for index, (vel_scale, accel_scale) in enumerate(margins):
        for direction, delta in (("pos", 90.0), ("neg", -90.0)):
            cases.append({
                "name": f"MR{index}_{direction}", "axis": 3,
                "delta": delta, "vmax": 180.0, "accel": 900.0,
                "kp": 1.2e-4, "ki": 8.0e-7, "kv": 2.0e-6,
                "start_duty": 0.65, "hold_duty": 0.55,
                "speed_source": 1, "speed_alpha": 0.05,
                "vel_scale": vel_scale, "accel_scale": accel_scale,
            })
    return cases


def startup_pause_cases():
    cases = []
    for index, start_duty in enumerate((0.45, 0.55, 0.65)):
        for direction, delta in (("pos", 90.0), ("neg", -90.0)):
            cases.append({
                "name": f"SP{index}_{direction}", "axis": 3,
                "delta": delta, "vmax": 180.0, "accel": 900.0,
                "kp": 1.2e-4, "ki": 8.0e-7, "kv": 2.0e-6,
                "start_duty": start_duty, "hold_duty": 0.55,
                "speed_source": 1, "speed_alpha": 0.05,
                "vel_scale": 0.85, "accel_scale": 0.40,
            })
    return cases


def window_speed_cases():
    cases = []
    for window in (20, 30, 40, 60):
        for kv in (5.0e-7, 1.0e-6):
            for direction, delta in (("pos", 90.0), ("neg", -90.0)):
                cases.append({
                    "name": f"W{window}_K{int(kv * 1e7)}_{direction}", "axis": 3,
                    "delta": delta, "vmax": 180.0, "accel": 900.0,
                    "kp": 1.2e-4, "ki": 8.0e-7, "kv": kv,
                    "start_duty": 0.55, "hold_duty": 0.55,
                    "speed_source": 1, "speed_window": window,
                    "speed_alpha": 0.05,
                    "vel_scale": 0.85, "accel_scale": 0.40,
                })
    return cases


def profile_cases(args):
    profiles = [
        ("short", 10.0, 180.0, 900.0),
        ("slow", 45.0, 45.0, 225.0),
        ("nominal", 90.0, 180.0, 900.0),
        ("fast", 180.0, 360.0, 1800.0),
    ]
    cases = []
    for axis in range(1, 5):
        if axis <= 2:
            kp, ki, kv = args.large_kp, args.large_ki, args.large_kv
        else:
            kp, ki, kv = args.medium_kp, args.medium_ki, args.medium_kv
        for label, magnitude, vmax, accel in profiles:
            for direction, sign in (("pos", 1.0), ("neg", -1.0)):
                cases.append({
                    "name": f"axis{axis}_{label}_{direction}", "axis": axis,
                    "delta": sign * magnitude, "vmax": vmax, "accel": accel,
                    "kp": kp, "ki": ki, "kv": kv,
                    "start_duty": args.large_start if axis <= 2 else args.medium_start,
                    "hold_duty": args.large_floor if axis <= 2 else args.medium_floor,
                    "speed_source": args.speed_source,
                    "speed_window": args.speed_window,
                    "vel_scale": args.vel_scale, "accel_scale": args.accel_scale,
                })
    return cases


def case_score(metrics):
    checks = verdicts(metrics)
    failures = sum(1 for *_, ok in checks if not ok)
    penalty = (
        abs(metrics.get("profile_end_error_deg", 0.0)) * 2.0
        + abs(metrics["final_err_deg"]) * 2.0
        + metrics["max_track_err_deg"] / 2.0
        + metrics["rms_track_err_deg"]
        + abs(metrics["overshoot_deg"]) * 2.0
        + metrics["duty_saturation_frac"] * 10.0
        + (1.0 - metrics["duty_smoothness"]) * 5.0
        + metrics["duty_cruise_ripple_pp"]
        + min(metrics["regressive_reversals"], 20) * 0.1
    )
    return failures, round(penalty, 4), len(checks) - failures, len(checks)


def run_case(board, case, output_dir):
    axis = case["axis"]
    board.send("c", expect="coast all")
    board.send(f"u {case.get('speed_source', 1)}", expect="velocity source")
    board.send(f"j {axis} {case.get('speed_window', 60)}", expect="velocity window")
    board.send(f"l {axis} {case.get('speed_alpha', 0.05):.6g}", expect="edge speed alpha")
    board.send(f"h {axis} {case.get('vel_scale', 1.0):.6g} {case.get('accel_scale', 1.0):.6g}",
               expect=f"M{axis} profile scale")
    board.send(f"G {axis} {case['kp']:.9g} {case['ki']:.9g} {case['kv']:.9g} 0 0",
               expect=f"gains M{axis}")
    board.send(f"b {axis} {case['start_duty']:.6g} {case['hold_duty']:.6g}",
               expect=f"M{axis} stiction")
    board.send(f"t {axis}", expect="trace armed")
    battery = board.require_battery()
    print(f"  battery={battery['pack_mv']}mV cells={battery['cell1_mv']}/{battery['cell2_mv']}mV "
          f"age={battery['age_us']}us", flush=True)
    board.send(f"X {axis} {case['delta']:.6g} {case['vmax']:.6g} {case['accel']:.6g}",
               expect=f"profile M{axis}", retries=1)
    board.read_for(TRACE_SECONDS)

    frame = board.pull_trace()
    status = board.send("S", 0.5)
    board.send("c")

    trace_path = os.path.join(output_dir, case["name"] + ".txt")
    with open(trace_path, "w", encoding="utf-8", newline="") as trace_file:
        trace_file.write(frame)

    meta, rows = load_last_trace(trace_path)
    expected_rows = int(meta.get("rows", 0)) if meta else 0
    if meta is None or expected_rows < 100 or len(rows) != expected_rows:
        raise RuntimeError(
            f"{case['name']}: expected {expected_rows} framed rows, got {len(rows) if rows else 0}")
    metrics = compute(meta, rows)
    if metrics is None:
        raise RuntimeError(f"{case['name']}: metrics rejected trace")
    metrics["case"] = case
    metrics["battery_pre_run"] = battery
    metrics["core1_status"] = next(
        (line for line in status.splitlines() if line.startswith("Core1:")), "missing")
    failures, score, passed, total = case_score(metrics)
    metrics["acceptance_passed"] = passed
    metrics["acceptance_total"] = total
    metrics["failure_count"] = failures
    metrics["score"] = score

    metrics_path = os.path.join(output_dir, case["name"] + ".json")
    with open(metrics_path, "w", encoding="utf-8") as metrics_file:
        json.dump(metrics, metrics_file, indent=2)
    return metrics


def write_summary(output_dir, results):
    summary_path = os.path.join(output_dir, "summary.csv")
    fields = [
        "name", "axis", "delta", "vmax", "accel", "kp", "ki", "kv",
        "start_duty", "hold_duty", "speed_source", "speed_window", "speed_alpha",
        "vel_scale", "accel_scale", "peak_vel_degs", "peak_accel_degs2",
        "passed", "total", "failures", "score", "max_track_err_deg",
        "rms_track_err_deg", "overshoot_deg", "final_err_deg",
        "duty_saturation_frac", "duty_smoothness", "duty_cruise_ripple_pp",
        "regressive_reversals", "core1_status",
        "battery_pack_mv", "battery_cell1_mv", "battery_cell2_mv", "battery_age_us",
    ]
    with open(summary_path, "w", newline="", encoding="utf-8") as summary_file:
        writer = csv.DictWriter(summary_file, fieldnames=fields)
        writer.writeheader()
        for metrics in results:
            case = metrics["case"]
            battery = metrics.get("battery_pre_run", {})
            writer.writerow({
                "name": case["name"], "axis": case["axis"],
                "delta": case["delta"], "vmax": case["vmax"],
                "accel": case["accel"], "kp": case["kp"],
                "ki": case["ki"], "kv": case["kv"],
                "start_duty": case["start_duty"], "hold_duty": case["hold_duty"],
                "speed_source": case.get("speed_source", 1),
                "speed_window": case.get("speed_window", 60),
                "speed_alpha": case.get("speed_alpha", 0.05),
                "vel_scale": case.get("vel_scale", 1.0),
                "accel_scale": case.get("accel_scale", 1.0),
                "peak_vel_degs": metrics["peak_vel_degs"],
                "peak_accel_degs2": metrics["peak_accel_degs2"],
                "passed": metrics["acceptance_passed"],
                "total": metrics["acceptance_total"],
                "failures": metrics["failure_count"], "score": metrics["score"],
                "max_track_err_deg": metrics["max_track_err_deg"],
                "rms_track_err_deg": metrics["rms_track_err_deg"],
                "overshoot_deg": metrics["overshoot_deg"],
                "final_err_deg": metrics["final_err_deg"],
                "duty_saturation_frac": metrics["duty_saturation_frac"],
                "duty_smoothness": metrics["duty_smoothness"],
                "duty_cruise_ripple_pp": metrics["duty_cruise_ripple_pp"],
                "regressive_reversals": metrics["regressive_reversals"],
                "core1_status": metrics["core1_status"],
                "battery_pack_mv": battery.get("pack_mv"),
                "battery_cell1_mv": battery.get("cell1_mv"),
                "battery_cell2_mv": battery.get("cell2_mv"),
                "battery_age_us": battery.get("age_us"),
            })
    with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as summary_file:
        json.dump(results, summary_file, indent=2)
    return summary_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port")
    parser.add_argument("--suite", choices=("gain-search", "medium-breakaway",
                                             "dynamics", "edge-speed",
                                             "filtered-edge", "observer-speed",
                                             "profile-margin", "margin-refine",
                                             "startup-pause", "window-speed",
                                             "profiles"),
                        default="gain-search")
    parser.add_argument("--output")
    parser.add_argument("--case", action="append", default=[],
                        help="run only named cases; repeat to select a subset")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--batch-size", type=int, default=1,
                        help="cleanly reopen CDC after this many completed cases")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--large-kp", type=float, default=1.0e-4)
    parser.add_argument("--large-ki", type=float, default=1.0e-6)
    parser.add_argument("--large-kv", type=float, default=2.0e-6)
    parser.add_argument("--large-start", type=float, default=0.12)
    parser.add_argument("--large-floor", type=float, default=0.12)
    parser.add_argument("--medium-kp", type=float, default=1.0e-4)
    parser.add_argument("--medium-ki", type=float, default=8.0e-7)
    parser.add_argument("--medium-kv", type=float, default=1.5e-6)
    parser.add_argument("--medium-start", type=float, default=0.65)
    parser.add_argument("--medium-floor", type=float, default=0.25)
    parser.add_argument("--speed-source", type=int, choices=(0, 1, 2, 3), default=1)
    parser.add_argument("--speed-window", type=int, default=60)
    parser.add_argument("--vel-scale", type=float, default=0.9)
    parser.add_argument("--accel-scale", type=float, default=0.65)
    parser.add_argument("--min-battery-mv", type=int, default=6500)
    parser.add_argument("--min-cell-mv", type=int, default=3000)
    parser.add_argument("--max-battery-age-ms", type=int, default=250)
    args = parser.parse_args()

    if args.suite == "gain-search":
        cases = gain_cases()
    elif args.suite == "medium-breakaway":
        cases = medium_breakaway_cases()
    elif args.suite == "dynamics":
        cases = dynamics_cases()
    elif args.suite == "edge-speed":
        cases = edge_speed_cases()
    elif args.suite == "filtered-edge":
        cases = filtered_edge_cases()
    elif args.suite == "observer-speed":
        cases = observer_speed_cases()
    elif args.suite == "profile-margin":
        cases = profile_margin_cases()
    elif args.suite == "margin-refine":
        cases = margin_refine_cases()
    elif args.suite == "startup-pause":
        cases = startup_pause_cases()
    elif args.suite == "window-speed":
        cases = window_speed_cases()
    else:
        cases = profile_cases(args)
    if args.case:
        selected = set(args.case)
        cases = [case for case in cases if case["name"] in selected]
        missing = selected - {case["name"] for case in cases}
        if missing:
            parser.error("unknown case(s): " + ", ".join(sorted(missing)))
    if args.dry_run:
        print(json.dumps(cases, indent=2))
        return 0

    port = find_port(args.port)
    if not port:
        sys.exit("EVN RP2040 serial port not found")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output or os.path.join(RESULTS, f"sweep_{args.suite}_{timestamp}")
    os.makedirs(output_dir, exist_ok=args.resume)

    results = []
    completed = set()
    if args.resume:
        for path in sorted(Path(output_dir).glob("*.json")):
            if path.name == "summary.json":
                continue
            metrics = json.loads(path.read_text(encoding="utf-8"))
            results.append(metrics)
            completed.add(metrics["case"]["name"])
        write_summary(output_dir, results)

    board = None
    batch_count = 0
    try:
        for index, case in enumerate(cases, 1):
            if case["name"] in completed:
                print(f"[{index:02d}/{len(cases):02d}] {case['name']} (already complete)", flush=True)
                continue
            if board is None or batch_count >= args.batch_size:
                if board is not None:
                    board.close()
                    time.sleep(1.0)
                port = find_port(args.port)
                if not port:
                    raise RuntimeError("EVN serial port disappeared between batches")
                board = BoardSession(port, args.min_battery_mv, args.min_cell_mv,
                                     args.max_battery_age_ms * 1000)
                board.send("w 25000", 0.3)
                batch_count = 0
            print(f"[{index:02d}/{len(cases):02d}] {case['name']}", flush=True)
            try:
                metrics = run_case(board, case, output_dir)
            except Exception:
                if board.last_trace_data:
                    partial_path = os.path.join(output_dir, case["name"] + "_partial.txt")
                    with open(partial_path, "wb") as partial_file:
                        partial_file.write(board.last_trace_data)
                raise
            results.append(metrics)
            write_summary(output_dir, results)
            batch_count += 1
            print(
                f"  {metrics['acceptance_passed']}/{metrics['acceptance_total']} "
                f"score={metrics['score']:.3f} maxerr={metrics['max_track_err_deg']:.3f} "
                f"overshoot={metrics['overshoot_deg']:.3f} "
                f"smooth={metrics['duty_smoothness']:.3f}",
                flush=True,
            )
    finally:
        if board is not None:
            board.close()

    summary_path = write_summary(output_dir, results)
    ranked = sorted(results, key=lambda item: (item["failure_count"], item["score"]))
    print(f"summary: {summary_path}")
    for metrics in ranked[:8]:
        print(f"rank {metrics['case']['name']}: failures={metrics['failure_count']} score={metrics['score']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
