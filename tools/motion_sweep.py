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


def find_port(requested=None):
    if requested:
        return requested
    for port in list_ports.comports():
        if port.vid == RP2040_VID:
            return port.device
    return None


class BoardSession:
    def __init__(self, port):
        self.last_trace_data = b""
        self.serial = serial.Serial(port, 115200, timeout=0.05, write_timeout=2.0)
        self.serial.dtr = False
        time.sleep(0.05)
        self.serial.dtr = True
        self.read_for(1.0)

    def read_for(self, seconds):
        deadline = time.time() + seconds
        chunks = []
        while time.time() < deadline:
            chunk = self.serial.read(4096)
            if chunk:
                chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", "replace")

    def send(self, command, read_seconds=0.20):
        self.serial.write(command.encode("ascii") + b"\n")
        self.serial.flush()
        return self.read_for(read_seconds)

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
                })
    return cases


def case_score(metrics):
    checks = verdicts(metrics)
    failures = sum(1 for *_, ok in checks if not ok)
    penalty = (
        metrics["max_track_err_deg"] / 2.0
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
    board.send("c")
    board.send(f"G {axis} {case['kp']:.9g} {case['ki']:.9g} {case['kv']:.9g} 0 0")
    board.send(f"b {axis} {case['start_duty']:.6g} {case['hold_duty']:.6g}")
    board.send(f"t {axis}")
    board.send(f"X {axis} {case['delta']:.6g} {case['vmax']:.6g} {case['accel']:.6g}")
    board.read_for(TRACE_SECONDS)

    board.serial.write(b"d\n")
    board.serial.flush()
    frame = board.read_trace()
    status = board.send("S", 0.5)
    board.send("c")

    trace_path = os.path.join(output_dir, case["name"] + ".txt")
    with open(trace_path, "w", encoding="utf-8", newline="") as trace_file:
        trace_file.write(frame)

    meta, rows = load_last_trace(trace_path)
    if meta is None or len(rows) != 2500:
        raise RuntimeError(f"{case['name']}: expected 2500 framed rows, got {len(rows) if rows else 0}")
    metrics = compute(meta, rows)
    if metrics is None:
        raise RuntimeError(f"{case['name']}: metrics rejected trace")
    metrics["case"] = case
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
        "start_duty", "hold_duty",
        "passed", "total", "failures", "score", "max_track_err_deg",
        "rms_track_err_deg", "overshoot_deg", "final_err_deg",
        "duty_saturation_frac", "duty_smoothness", "duty_cruise_ripple_pp",
        "regressive_reversals", "core1_status",
    ]
    with open(summary_path, "w", newline="", encoding="utf-8") as summary_file:
        writer = csv.DictWriter(summary_file, fieldnames=fields)
        writer.writeheader()
        for metrics in results:
            case = metrics["case"]
            writer.writerow({
                "name": case["name"], "axis": case["axis"],
                "delta": case["delta"], "vmax": case["vmax"],
                "accel": case["accel"], "kp": case["kp"],
                "ki": case["ki"], "kv": case["kv"],
                "start_duty": case["start_duty"], "hold_duty": case["hold_duty"],
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
            })
    with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as summary_file:
        json.dump(results, summary_file, indent=2)
    return summary_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port")
    parser.add_argument("--suite", choices=("gain-search", "medium-breakaway", "profiles"),
                        default="gain-search")
    parser.add_argument("--output")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--batch-size", type=int, default=4,
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
    args = parser.parse_args()

    if args.suite == "gain-search":
        cases = gain_cases()
    elif args.suite == "medium-breakaway":
        cases = medium_breakaway_cases()
    else:
        cases = profile_cases(args)
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
                board = BoardSession(port)
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
