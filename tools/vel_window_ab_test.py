#!/usr/bin/env python3
"""EVN ALPHA vel_window A/B test.

Tests vel_window=10 (sim-predicted fix) vs vel_window=40 (baseline) on
EV3 Large axes by running a 720° move and capturing the 200Hz diagnostic
trace. Analyzes the endpoint region for limit-cycle (hunting) behavior.

Usage:
    python tools/vel_window_ab_test.py [--port COMx] [--axis 1]
"""

import argparse
import re
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial not installed. Run: pip install -r tools/requirements.txt")

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import find_board_port

def send_cmd(ser, cmd, wait_s=0.3, verbose=True):
    """Send a command and wait for response."""
    for attempt in range(3):
        try:
            ser.reset_input_buffer()
            ser.write((cmd + "\n").encode())
            break
        except serial.SerialTimeoutException:
            print(f"  WARNING: write timeout on '{cmd}', retry {attempt+1}/3")
            time.sleep(1.0)
    else:
        print(f"  ERROR: failed to send '{cmd}' after 3 attempts")
        return ""
    time.sleep(wait_s)
    resp = ser.read(ser.in_waiting or 1).decode("utf-8", errors="replace")
    if verbose:
        print(f"  > {cmd}")
        if resp.strip():
            print(f"    {resp.strip()}")
    return resp


def wait_for_move_done(ser, timeout_s=20.0):
    """Wait for move to complete by polling 'S' and checking for 'done'."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        ser.reset_input_buffer()
        ser.write(b"S\n")
        time.sleep(0.5)
        resp = ser.read(ser.in_waiting or 1).decode("utf-8", errors="replace")
        # Check all M lines for "done"
        lines = [l.strip() for l in resp.strip().split("\n") if l.strip().startswith("M")]
        if lines and all("done" in l for l in lines):
            return True
        time.sleep(0.5)
    return False


def capture_trace(ser, label):
    """Capture the full trace dump and save to file."""
    ser.reset_input_buffer()
    ser.write(b"d\n")
    time.sleep(0.5)

    lines = []
    t0 = time.time()
    got_header = False

    while time.time() - t0 < 30.0:
        chunk = ser.read(ser.in_waiting or 1).decode("utf-8", errors="replace")
        if chunk:
            lines.append(chunk)
            text = "".join(lines)
            if "TRACE BEGIN" in text:
                got_header = True
            if "TRACE END" in text:
                break
        time.sleep(0.05)

    text = "".join(lines)

    # Parse trace data
    data_lines = []
    header_line = ""
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("TRACE BEGIN"):
            header_line = line
        elif re.match(r"^-?\d+,(-?\d+,){6}-?\d+$", line):
            data_lines.append(line)

    print(f"  [{label}] {len(data_lines)} trace rows captured")
    if header_line:
        print(f"  [{label}] Header: {header_line}")

    return header_line, data_lines, text


def analyze_trace(data_lines, label, tail_s=3.0):
    """Analyze the endpoint region for limit-cycle behavior.

    The trace is 200 Hz (5ms per row). The endpoint region is the last
    `tail_s` seconds of the trace. A limit cycle shows as:
    - duty oscillating (large pp swing, banging between +/-)
    - encoder oscillating around the target
    - what (observer speed) oscillating
    """
    if not data_lines:
        print(f"  [{label}] NO DATA")
        return None

    # Parse all rows
    rows = []
    for line in data_lines:
        parts = line.split(",")
        if len(parts) == 8:
            rows.append({
                "t_ms": int(parts[0]),
                "ref_mdeg": int(parts[1]),
                "enc_mdeg": int(parts[2]),
                "hat_mdeg": int(parts[3]),
                "vref_mdegs": int(parts[4]),
                "what_mdegs": int(parts[5]),
                "duty_milli": int(parts[6]),
                "cur_01ma": int(parts[7]),
            })

    if not rows:
        print(f"  [{label}] No parseable rows")
        return None

    # Find the endpoint region (last tail_s seconds)
    t_end = rows[-1]["t_ms"]
    t_start = t_end - int(tail_s * 1000)
    endpoint = [r for r in rows if r["t_ms"] >= t_start]

    if not endpoint:
        endpoint = rows[-int(len(rows) * 0.2):]  # fallback: last 20%

    n = len(endpoint)
    print(f"  [{label}] Endpoint analysis: {n} rows ({n * 5}ms), t={endpoint[0]['t_ms']}-{endpoint[-1]['t_ms']}ms")

    # Compute metrics
    duties = [r["duty_milli"] for r in endpoint]
    encs = [r["enc_mdeg"] for r in endpoint]
    hats = [r["hat_mdeg"] for r in endpoint]
    whats = [r["what_mdegs"] for r in endpoint]
    refs = [r["ref_mdeg"] for r in endpoint]

    duty_pp = max(duties) - min(duties)
    enc_pp = max(encs) - min(encs)
    hat_pp = max(hats) - min(hats)
    what_pp = max(whats) - min(whats)
    enc_err = [abs(r["enc_mdeg"] - r["ref_mdeg"]) for r in endpoint]
    enc_err_max = max(enc_err)
    enc_err_mean = sum(enc_err) / len(enc_err)

    # Count duty zero-crossings (oscillation indicator)
    duty_mean = sum(duties) / len(duties)
    crossings = 0
    for i in range(1, len(duties)):
        if (duties[i - 1] - duty_mean) * (duties[i] - duty_mean) < 0:
            crossings += 1

    # Duty saturation: how often is duty at max?
    duty_sat_count = sum(1 for d in duties if abs(d) > 900)
    duty_sat_pct = 100.0 * duty_sat_count / n

    # Estimate oscillation frequency from zero crossings
    duration_s = (endpoint[-1]["t_ms"] - endpoint[0]["t_ms"]) / 1000.0
    osc_freq = crossings / (2 * duration_s) if duration_s > 0 else 0

    # Limit cycle detection: duty banging + encoder oscillation
    has_limit_cycle = duty_pp > 800 and enc_pp > 3000 and osc_freq > 2.0

    print(f"  [{label}] Duty: pp={duty_pp}, sat={duty_sat_pct:.0f}%, crossings={crossings}, osc~{osc_freq:.1f}Hz")
    print(f"  [{label}] Enc: pp={enc_pp}mdeg ({enc_pp / 1000.0:.1f}deg), err_max={enc_err_max}mdeg ({enc_err_max / 1000.0:.2f}deg), err_mean={enc_err_mean:.0f}mdeg")
    print(f"  [{label}] Hat: pp={hat_pp}mdeg, What: pp={what_pp}mdeg/s")
    print(f"  [{label}] LIMIT CYCLE: {'YES' if has_limit_cycle else 'NO'}")

    return {
        "label": label,
        "n_rows": len(rows),
        "endpoint_rows": n,
        "duty_pp": duty_pp,
        "duty_sat_pct": duty_sat_pct,
        "enc_pp": enc_pp,
        "hat_pp": hat_pp,
        "what_pp": what_pp,
        "enc_err_max": enc_err_max,
        "enc_err_mean": enc_err_mean,
        "osc_freq": osc_freq,
        "crossings": crossings,
        "has_limit_cycle": has_limit_cycle,
        "final_enc_err": abs(rows[-1]["enc_mdeg"] - rows[-1]["ref_mdeg"]),
        "ref_final": rows[-1]["ref_mdeg"],
        "enc_final": rows[-1]["enc_mdeg"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=None, help="COM port (auto-detect if omitted)")
    ap.add_argument("--axis", type=int, default=1, help="Motor axis (1-4, default 1 = EV3 Large)")
    ap.add_argument("--distance", type=float, default=720.0, help="Move distance in degrees")
    ap.add_argument("--vel", type=float, default=800.0, help="Max velocity (deg/s)")
    ap.add_argument("--accel", type=float, default=1600.0, help="Max accel (deg/s^2)")
    ap.add_argument("--output", default=None, help="Output file for results (default: auto)")
    args = ap.parse_args()

    port = args.port or find_board_port()
    if not port:
        sys.exit("ERROR: no RP2040 board found on any COM port")

    print(f"[vel_window_ab] {port} @ 115200")
    ser = serial.Serial(port, 115200, timeout=1.0, write_timeout=5.0)
    time.sleep(0.5)

    axis = args.axis
    dist = args.distance
    vel = args.vel
    accel = args.accel

    results = []
    all_traces = {}

    # --- Baseline: vel_window=40 (default) ---
    print(f"\n=== BASELINE: vel_window=40 (default) ===")
    send_cmd(ser, "c")  # coast all first
    time.sleep(0.5)
    send_cmd(ser, f"j {axis} 40")
    send_cmd(ser, f"t {axis}")  # arm trace
    time.sleep(0.2)
    send_cmd(ser, f"X {axis} {dist} {vel} {accel}")  # move

    print(f"  Waiting for move to complete...")
    if not wait_for_move_done(ser):
        print("  WARNING: move didn't complete in time")
    time.sleep(2)  # extra settle time

    hdr, rows, raw = capture_trace(ser, f"baseline_w40_ax{axis}")
    results.append(analyze_trace(rows, f"baseline_w40_ax{axis}"))
    all_traces[f"baseline_w40_ax{axis}"] = raw

    print("  Waiting for dump to fully drain...")
    time.sleep(5)  # let the trace dump fully complete

    # --- Test: vel_window=10 ---
    print(f"\n=== TEST: vel_window=10 (sim prediction) ===")
    send_cmd(ser, "c")  # coast all first
    time.sleep(0.5)
    send_cmd(ser, f"j {axis} 10")
    time.sleep(1.0)  # ensure command is processed
    send_cmd(ser, f"t {axis}")  # arm trace
    time.sleep(0.5)
    send_cmd(ser, f"X {axis} -{dist} {vel} {accel}")  # move back

    print(f"  Waiting for move to complete...")
    if not wait_for_move_done(ser):
        print("  WARNING: move didn't complete in time")
    time.sleep(2)  # extra settle time

    hdr, rows, raw = capture_trace(ser, f"test_w10_ax{axis}")
    results.append(analyze_trace(rows, f"test_w10_ax{axis}"))
    all_traces[f"test_w10_ax{axis}"] = raw

    # --- Safety: coast all ---
    print(f"\n=== SAFETY: Coasting all motors ===")
    send_cmd(ser, "c")

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"SUMMARY: vel_window A/B test on axis {axis}")
    print(f"{'='*60}")
    for r in results:
        if r:
            status = "LIMIT CYCLE" if r["has_limit_cycle"] else "CLEAN"
            print(f"  {r['label']:25s}: {status:12s}  duty_pp={r['duty_pp']:5d}  "
                  f"enc_pp={r['enc_pp']:6d}mdeg ({r['enc_pp']/1000.0:.1f}deg)  "
                  f"osc={r['osc_freq']:.1f}Hz  final_err={r['final_enc_err']}mdeg")

    # Determine if vel_window=10 helps
    baseline = next((r for r in results if r and "baseline" in r["label"]), None)
    test = next((r for r in results if r and "test_w10" in r["label"]), None)
    if baseline and test:
        if baseline["has_limit_cycle"] and not test["has_limit_cycle"]:
            print(f"\n  *** SIM PREDICTION CONFIRMED: vel_window=10 eliminates the limit cycle ***")
        elif not baseline["has_limit_cycle"] and not test["has_limit_cycle"]:
            print(f"\n  No limit cycle in either config (baseline may have been clean this run)")
        elif baseline["has_limit_cycle"] and test["has_limit_cycle"]:
            print(f"\n  *** SIM PREDICTION FALSIFIED: vel_window=10 does NOT eliminate the limit cycle ***")
        else:
            print(f"\n  Unexpected: baseline clean, test has limit cycle (vel_window=10 made it worse)")

    # Save traces
    if args.output:
        out_file = args.output
    else:
        out_file = f"bench/results/vel_window_ab_{time.strftime('%Y%m%d_%H%M%S')}.txt"

    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w") as f:
        for label, raw in all_traces.items():
            f.write(f"=== {label} ===\n")
            f.write(raw)
            f.write("\n\n")
    print(f"\n  Traces saved to {out_file}")

    ser.close()
    print("[vel_window_ab] done")


if __name__ == "__main__":
    main()
