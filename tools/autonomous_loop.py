#!/usr/bin/env python3
"""
EVN ALPHA Autonomous Loop — Automated tuning pipeline with safety guards.
Features:
  - Automatically bumps EVN_TUNING_RUN_ID in hal/hal_tuning_log.h before each run
    so firmware executes fresh test cases instead of seeing completed ones.
  - Runs flash_extract_decode.py with stale-flash verification.
  - Monitors convergence: checks for 16/16 12/12 passes or consecutive winning runs.
  - Stops cleanly on failure, convergence, or user interrupt.
"""
import argparse
import csv
import glob
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
RESULTS_DIR = REPO_ROOT / "bench" / "results"
RUN_LOG_PATH = REPO_ROOT / "hal" / "hal_tuning_log.h"
TOOLS_DIR = REPO_ROOT / "tools"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from sim_integration import run_simulation_preflight, compare_sim_to_real


def get_current_run_id():
    """Read current EVN_TUNING_RUN_ID from hal_tuning_log.h."""
    text = RUN_LOG_PATH.read_text()
    m = re.search(r"#define\s+EVN_TUNING_RUN_ID\s+0x([0-9A-Fa-f]+)u?", text)
    if m:
        return int(m.group(1), 16)
    return None


def bump_run_id():
    """Increment EVN_TUNING_RUN_ID by 1 in hal_tuning_log.h."""
    text = RUN_LOG_PATH.read_text()
    m = re.search(r"#define\s+EVN_TUNING_RUN_ID\s+0x([0-9A-Fa-f]+)u?", text)
    if not m:
        raise ValueError("Could not find EVN_TUNING_RUN_ID in hal_tuning_log.h")
    cur_val = int(m.group(1), 16)
    next_val = cur_val + 1
    new_text = re.sub(
        r"#define\s+EVN_TUNING_RUN_ID\s+0x[0-9A-Fa-f]+u?",
        f"#define EVN_TUNING_RUN_ID             0x{next_val:08X}u",
        text,
        count=1
    )
    RUN_LOG_PATH.write_text(new_text)
    print(f"[autonomous_loop] Bumped EVN_TUNING_RUN_ID: 0x{cur_val:08X} -> 0x{next_val:08X}")
    return next_val


def parse_summary_passes(summary_path):
    """Return count of full passes (12/12) and total cases from summary.csv."""
    if not os.path.exists(summary_path):
        return 0, 0
    passes = 0
    total_cases = 0
    with open(summary_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_cases += 1
            try:
                p = int(row.get("passed", 0))
                tot = int(row.get("total", 0))
                if tot > 0 and p == tot:
                    passes += 1
            except (ValueError, TypeError):
                pass
    return passes, total_cases


def find_latest_summary():
    dirs = sorted(glob.glob(f"{RESULTS_DIR}/autonomous_auto_*"), key=os.path.getmtime, reverse=True)
    for d in dirs:
        s = os.path.join(d, "summary.csv")
        if os.path.exists(s):
            return s, d
    return None, None


def main():
    parser = argparse.ArgumentParser(description="EVN Autonomous Tuning Loop")
    parser.add_argument("--max-iterations", type=int, default=1, help="Max iterations to run (default: 1 for controlled validation)")
    parser.add_argument("--timeout", type=int, default=900, help="Pipeline timeout in seconds (default 900)")
    parser.add_argument("--no-sim-gate", action="store_true", help="Skip pre-flight simulation gate check")
    parser.add_argument("--no-sim-compare", action="store_true", help="Skip post-run Sim-to-Real comparison")
    args = parser.parse_args()

    print(f"[autonomous_loop] Starting autonomous loop (max {args.max_iterations} iterations). Press Ctrl+C to stop.")
    iteration = 0

    while iteration < args.max_iterations:
        iteration += 1
        print(f"\n==================================================")
        print(f"=== LOOP ITERATION {iteration} / {args.max_iterations} ===")
        print(f"==================================================")

        # Step 1: Simulator Pre-Flight Validation Gate
        if not args.no_sim_gate:
            print("[autonomous_loop] Running Simulator Pre-Flight Gate...")
            gate_ok, _ = run_simulation_preflight()
            if not gate_ok:
                print("[autonomous_loop] ERROR: Simulator pre-flight gate failed! Proposed gains are unstable. Halting.")
                sys.exit(1)
            print("[autonomous_loop] Simulator pre-flight gate passed successfully.")

        # Step 2: Bump Run ID so firmware sees fresh cases
        new_run_id = bump_run_id()

        # Step 3: Launch pipeline (build + flash + wait bootsel + extract + decode)
        print(f"[autonomous_loop] Launching pipeline for run 0x{new_run_id:08X}...")
        result = subprocess.run(
            [sys.executable, "tools/flash_extract_decode.py", "--timeout", str(args.timeout)],
            capture_output=False
        )

        if result.returncode != 0:
            print(f"[autonomous_loop] ERROR: Pipeline returned non-zero exit code {result.returncode}. Stopping.")
            sys.exit(result.returncode)

        # Step 4: Check results & Sim-to-Real Comparison
        summary, dir_path = find_latest_summary()
        if summary and dir_path:
            passes, total_cases = parse_summary_passes(summary)
            print(f"[autonomous_loop] Iteration {iteration} result: {passes}/{total_cases} cases full 12/12 PASS.")

            if not args.no_sim_compare:
                print(f"[autonomous_loop] Running Sim-to-Real telemetry comparison...")
                compare_sim_to_real(Path(dir_path))

            if total_cases > 0 and passes == total_cases:
                print(f"[autonomous_loop] CONVERGENCE ACHIEVED: 16/16 cases 12/12 passed! Halting loop.")
                break

        if iteration < args.max_iterations:
            print("[autonomous_loop] Pausing 5s before next iteration...")
            time.sleep(5)

    print("[autonomous_loop] Autonomous execution finished.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[autonomous_loop] Stopped by user (Ctrl+C).")
        sys.exit(0)
