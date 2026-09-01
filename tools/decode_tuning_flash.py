#!/usr/bin/env python3
"""Decode autonomous EVN motion traces saved from the tail-flash journal."""

import argparse
import csv
import json
import struct
import sys
import zlib
from pathlib import Path

from motion_metrics import compute, verdicts

FLASH_BASE_ADDRESS = 0x10F00000
XIP_BASE_ADDRESS = 0x10000000
FLASH_REGION_SIZE = 0x000F0000
SUPERBLOCK_SIZE = 0x1000
SLOT_SIZE = 0xE000
PAGE_SIZE = 256
CASE_COUNT = 16
WINDOW_RUN_ID = 0x26090201
TRAJECTORY_RUN_ID = 0x26090202
STARTUP_GOVERNOR_RUN_ID = 0x26090203
FRICTION_SWEEP_RUN_ID = 0x26090204
STARTUP_RELEASE_RUN_ID = 0x26090205
EDGE_WATCHDOG_RUN_ID = 0x26090206
SCHEMA_VERSION = 1
SUPER_MAGIC = 0x31535645
RECORD_MAGIC = 0x31525645
STATUS_COMPLETE = 1
UF2_MAGIC_START0 = 0x0A324655
UF2_MAGIC_START1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30


def crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def read_u32(data, word):
    return struct.unpack_from("<I", data, word * 4)[0]


def read_i32(data, word):
    return struct.unpack_from("<i", data, word * 4)[0]


def read_f32(data, word):
    return struct.unpack_from("<f", data, word * 4)[0]


def crc_with_zeroed_word(data, word):
    mutable = bytearray(data)
    struct.pack_into("<I", mutable, word * 4, 0)
    return crc32(mutable)


def load_uf2(path):
    content = Path(path).read_bytes()
    if len(content) % 512:
        raise ValueError("UF2 length is not a multiple of 512 bytes")
    image = bytearray(b"\xff" * FLASH_REGION_SIZE)
    seen = 0
    for offset in range(0, len(content), 512):
        block = content[offset:offset + 512]
        magic0, magic1, flags, target, payload_size = struct.unpack_from("<5I", block)
        del flags
        if (magic0, magic1, read_u32(block, 127)) != (
                UF2_MAGIC_START0, UF2_MAGIC_START1, UF2_MAGIC_END):
            raise ValueError(f"invalid UF2 block at file offset {offset}")
        if payload_size > 476:
            raise ValueError(f"invalid UF2 payload size {payload_size}")
        start = target - FLASH_BASE_ADDRESS
        end = start + payload_size
        if end <= 0 or start >= FLASH_REGION_SIZE:
            continue
        source_start = max(0, -start)
        destination_start = max(0, start)
        count = min(payload_size - source_start,
                    FLASH_REGION_SIZE - destination_start)
        image[destination_start:destination_start + count] = \
            block[32 + source_start:32 + source_start + count]
        seen += 1
    if not seen:
        raise ValueError("UF2 contains no tuning flash blocks")
    return bytes(image)


def load_image(path):
    path = Path(path)
    if path.suffix.lower() == ".uf2":
        return load_uf2(path)
    content = path.read_bytes()
    if len(content) == FLASH_REGION_SIZE:
        return content
    flash_offset = FLASH_BASE_ADDRESS - XIP_BASE_ADDRESS
    if len(content) >= flash_offset + FLASH_REGION_SIZE:
        return content[flash_offset:flash_offset + FLASH_REGION_SIZE]
    raise ValueError(
        f"binary must be exactly {FLASH_REGION_SIZE} bytes for the tuning range")


def validate_superblock(image):
    page = image[:PAGE_SIZE]
    expected = read_u32(page, 6)
    actual = crc_with_zeroed_word(page, 6)
    fields = tuple(read_u32(page, word) for word in range(6))
    wanted = (SUPER_MAGIC, SCHEMA_VERSION, CASE_COUNT, 0x00F00000, SLOT_SIZE)
    comparable = (fields[0], fields[1], fields[3], fields[4], fields[5])
    if comparable != wanted or expected != actual:
        raise ValueError(
            f"invalid tuning superblock fields={fields!r} "
            f"crc=0x{expected:08x}/0x{actual:08x}")
    return fields[2]


def decode_header(page, case_index, run_id):
    expected = read_u32(page, 7)
    actual = crc_with_zeroed_word(page, 7)
    if read_u32(page, 0) != RECORD_MAGIC or expected != actual:
        return None
    header = {
        "schema_version": read_u32(page, 1),
        "run_id": read_u32(page, 2),
        "case_index": read_u32(page, 3),
        "status": read_u32(page, 4),
        "trace_rows": read_u32(page, 5),
        "trace_crc32": read_u32(page, 6),
        "axis": read_u32(page, 8),
        "delta_mdeg": read_i32(page, 9),
        "target_mdeg": read_i32(page, 10),
        "vmax_mdegs": read_u32(page, 11),
        "accel_mdegs2": read_u32(page, 12),
        "kp": read_f32(page, 13),
        "ki": read_f32(page, 14),
        "kv": read_f32(page, 15),
        "kd": read_f32(page, 16),
        "kff": read_f32(page, 17),
        "start_duty": read_f32(page, 18),
        "hold_duty": read_f32(page, 19),
        "speed_source": read_u32(page, 20),
        "speed_window": read_u32(page, 21),
        "speed_alpha": read_f32(page, 22),
        "vel_scale": read_f32(page, 23),
        "accel_scale": read_f32(page, 24),
        "battery_pack_mv": read_u32(page, 25),
        "battery_cell1_mv": read_u32(page, 26),
        "battery_cell2_mv": read_u32(page, 27),
        "battery_age_us": read_u32(page, 28),
        "core_tick_count": read_u32(page, 29),
        "core_period_min_us": read_u32(page, 30),
        "core_period_max_us": read_u32(page, 31),
        "core_exec_max_us": read_u32(page, 32),
        "core_missed_ticks": read_u32(page, 33),
        "final_angle_mdeg": read_i32(page, 34),
        "final_speed_mdegs": read_i32(page, 35),
        "motion_flags": read_u32(page, 36),
        "sample_div": read_u32(page, 37),
        "pwm_hz": read_u32(page, 38),
        "duration_us": read_u32(page, 39),
        "trajectory_type": read_u32(page, 40),
        "repeat_index": read_u32(page, 41),
        "startup_reference_governor": read_u32(page, 42),
        "friction_feedforward_permille": read_u32(page, 43),
        "startup_release_speed_mdegs": read_u32(page, 44),
        "edge_watchdog_enabled": read_u32(page, 45),
    }
    if (header["schema_version"] != SCHEMA_VERSION or
            header["run_id"] != run_id or
            header["case_index"] != case_index):
        raise ValueError(f"case {case_index}: valid CRC but incompatible header")
    max_rows = (SLOT_SIZE - PAGE_SIZE) // 32
    if header["trace_rows"] > max_rows:
        raise ValueError(f"case {case_index}: trace row count exceeds slot")
    return header


def case_name(header):
    if header["run_id"] == EDGE_WATCHDOG_RUN_ID:
        prefix = "E" if header["edge_watchdog_enabled"] else "D"
        direction = "pos" if header["delta_mdeg"] >= 0 else "neg"
        return f"{prefix}{header['repeat_index']}_{direction}"
    if header["run_id"] == STARTUP_RELEASE_RUN_ID:
        direction = "pos" if header["delta_mdeg"] >= 0 else "neg"
        return (f"H{header['startup_release_speed_mdegs'] // 1000}_"
                f"R{header['repeat_index']}_{direction}")
    if header["run_id"] == FRICTION_SWEEP_RUN_ID:
        direction = "pos" if header["delta_mdeg"] >= 0 else "neg"
        return (f"F{header['friction_feedforward_permille']}_"
                f"R{header['repeat_index']}_{direction}")
    if header["run_id"] == STARTUP_GOVERNOR_RUN_ID:
        prefix = "G" if header["startup_reference_governor"] else "B"
        direction = "pos" if header["delta_mdeg"] >= 0 else "neg"
        return f"{prefix}{header['repeat_index']}_{direction}"
    if header["run_id"] == TRAJECTORY_RUN_ID:
        prefix = "J" if header["trajectory_type"] == 1 else "T"
        direction = "pos" if header["delta_mdeg"] >= 0 else "neg"
        return f"{prefix}{header['repeat_index']}_{direction}"
    gain = round(header["kv"] * 1e7)
    direction = "pos" if header["delta_mdeg"] >= 0 else "neg"
    return f"W{header['speed_window']}_K{gain}_{direction}"


def decode_rows(image, case_index, header):
    slot = SUPERBLOCK_SIZE + case_index * SLOT_SIZE
    size = header["trace_rows"] * 32
    payload = image[slot + PAGE_SIZE:slot + PAGE_SIZE + size]
    actual = crc32(payload)
    if actual != header["trace_crc32"]:
        raise ValueError(
            f"case {case_index}: trace CRC 0x{header['trace_crc32']:08x}/"
            f"0x{actual:08x}")
    rows = [list(row) for row in struct.iter_unpack("<8i", payload)]
    if rows:
        start_ms = rows[0][0]
        for row in rows:
            row[0] -= start_ms
    return rows


def trace_metadata(header):
    return {
        "axis": str(header["axis"]),
        "rows": str(header["trace_rows"]),
        "kp": f"{header['kp']:.9g}",
        "ki": f"{header['ki']:.9g}",
        "kv": f"{header['kv']:.9g}",
        "kd": f"{header['kd']:.9g}",
        "kff": f"{header['kff']:.9g}",
        "ff": "1",
        "pwm": str(header["pwm_hz"]),
        "target": f"{header['target_mdeg'] / 1000.0:.6g}",
        "duration": f"{header['duration_us'] / 1e6:.6g}",
        "vmax": f"{header['vmax_mdegs'] / 1000.0:.6g}",
        "accel": f"{header['accel_mdegs2'] / 1000.0:.6g}",
        "vscale": f"{header['vel_scale']:.6g}",
        "ascale": f"{header['accel_scale']:.6g}",
        "vsrc": str(header["speed_source"]),
        "vwin": str(header["speed_window"]),
        "valpha": f"{header['speed_alpha']:.6g}",
    }


def write_trace(path, meta, rows):
    header = "TRACE BEGIN " + " ".join(f"{key}={value}" for key, value in meta.items())
    columns = "t_ms,ref_mdeg,enc_mdeg,hat_mdeg,vref_mdegs,what_mdegs,duty_milli,cur_01ma"
    lines = [header, columns]
    lines.extend(",".join(str(value) for value in row) for row in rows)
    lines.append("TRACE END")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def score_metrics(metrics):
    checks = verdicts(metrics)
    failures = sum(1 for *_, passed in checks if not passed)
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


def decode(image, output_dir):
    run_id = validate_superblock(image)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for index in range(CASE_COUNT):
        slot = SUPERBLOCK_SIZE + index * SLOT_SIZE
        header = decode_header(image[slot:slot + PAGE_SIZE], index, run_id)
        if header is None:
            continue
        name = case_name(header)
        record = {"name": name, "header": header}
        if header["status"] == STATUS_COMPLETE:
            rows = decode_rows(image, index, header)
            meta = trace_metadata(header)
            write_trace(output_dir / f"{name}.txt", meta, rows)
            metrics = compute(meta, rows)
            if metrics is None:
                raise ValueError(f"case {index}: metrics rejected trace")
            failures, score, passed, total = score_metrics(metrics)
            metrics.update({
                "case": {
                    "name": name,
                    "axis": header["axis"],
                    "delta": header["delta_mdeg"] / 1000.0,
                    "vmax": header["vmax_mdegs"] / 1000.0,
                    "accel": header["accel_mdegs2"] / 1000.0,
                    "kp": header["kp"], "ki": header["ki"], "kv": header["kv"],
                    "start_duty": header["start_duty"],
                    "hold_duty": header["hold_duty"],
                    "speed_source": header["speed_source"],
                    "speed_window": header["speed_window"],
                    "speed_alpha": header["speed_alpha"],
                    "vel_scale": header["vel_scale"],
                    "accel_scale": header["accel_scale"],
                    "trajectory_type": header["trajectory_type"],
                    "repeat_index": header["repeat_index"],
                    "startup_reference_governor":
                        bool(header["startup_reference_governor"]),
                    "friction_feedforward_permille":
                        header["friction_feedforward_permille"],
                    "startup_release_speed_mdegs":
                        header["startup_release_speed_mdegs"],
                    "edge_watchdog_enabled": bool(header["edge_watchdog_enabled"]),
                },
                "battery_pre_run": {
                    "pack_mv": header["battery_pack_mv"],
                    "cell1_mv": header["battery_cell1_mv"],
                    "cell2_mv": header["battery_cell2_mv"],
                    "age_us": header["battery_age_us"],
                },
                "core1_status": (
                    f"Core1: {header['core_tick_count']} ticks, period "
                    f"{header['core_period_min_us']}-{header['core_period_max_us']} us, "
                    f"exec max {header['core_exec_max_us']} us, "
                    f"missed {header['core_missed_ticks']}"
                ),
                "acceptance_passed": passed,
                "acceptance_total": total,
                "failure_count": failures,
                "score": score,
            })
            record["metrics"] = metrics
            (output_dir / f"{name}.json").write_text(
                json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        results.append(record)

    (output_dir / "flash_records.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8")
    complete = [item["metrics"] for item in results if "metrics" in item]
    complete.sort(key=lambda item: (item["failure_count"], item["score"]))
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["name", "passed", "total", "failures", "score", "max_track_err_deg",
                  "rms_track_err_deg", "overshoot_deg", "final_err_deg",
                  "duty_smoothness", "duty_cruise_ripple_pp", "core1_status"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for metrics in complete:
            writer.writerow({
                "name": metrics["case"]["name"],
                "passed": metrics["acceptance_passed"],
                "total": metrics["acceptance_total"],
                "failures": metrics["failure_count"],
                "score": metrics["score"],
                "max_track_err_deg": metrics["max_track_err_deg"],
                "rms_track_err_deg": metrics["rms_track_err_deg"],
                "overshoot_deg": metrics["overshoot_deg"],
                "final_err_deg": metrics["final_err_deg"],
                "duty_smoothness": metrics["duty_smoothness"],
                "duty_cruise_ripple_pp": metrics["duty_cruise_ripple_pp"],
                "core1_status": metrics["core1_status"],
            })
    return results, complete


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="picotool tuning-range UF2 or raw binary")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        image = load_image(args.image)
        records, ranked = decode(image, args.output)
    except (OSError, ValueError, KeyError, struct.error) as error:
        sys.exit(f"decode failed: {error}")
    print(f"decoded {len(records)}/{CASE_COUNT} committed records, "
          f"{len(ranked)} complete traces")
    for metrics in ranked:
        print(f"rank {metrics['case']['name']}: {metrics['acceptance_passed']}/"
              f"{metrics['acceptance_total']} failures={metrics['failure_count']} "
              f"score={metrics['score']}")
    return 0 if len(ranked) == CASE_COUNT else 2


if __name__ == "__main__":
    sys.exit(main())
