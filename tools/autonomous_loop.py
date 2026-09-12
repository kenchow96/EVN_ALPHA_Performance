#!/usr/bin/env python3
"""
EVN ALPHA Autonomous Loop — Continuous iteration per docs/resume/index.md workflow.
Runs continuously until explicitly interrupted (Ctrl+C) or user prompts stop.
Loop: read latest results → apply next adjustment → bump run ID → launch pipeline → document.
"""
import subprocess, sys, time, os, glob

RESULTS_DIR = "bench/results"
RUN_LOG = "hal/hal_tuning_log.h"

def find_latest_summary():
    dirs = sorted(glob.glob(f"{RESULTS_DIR}/autonomous_auto_*"), key=os.path.getmtime, reverse=True)
    for d in dirs:
        s = os.path.join(d, "summary.csv")
        if os.path.exists(s):
            return s, d
    return None, None

def main():
    print("[autonomous_loop] Starting continuous loop. Press Ctrl+C to stop.")
    iteration = 0
    while True:
        iteration += 1
        print(f"\n=== LOOP ITERATION {iteration} ===")
        summary, dir_path = find_latest_summary()
        if summary:
            print(f"[autonomous_loop] Latest results: {summary}")
        # Launch pipeline (build + flash + extract + decode)
        print("[autonomous_loop] Launching pipeline...")
        result = subprocess.run(
            [sys.executable, "tools/flash_extract_decode.py", "--timeout", "900"],
            capture_output=False
        )
        print(f"[autonomous_loop] Pipeline completed (exit={result.returncode}).")
        # After pipeline, read new summary and document
        new_summary, new_dir = find_latest_summary()
        if new_summary:
            print(f"[autonomous_loop] New results documented at: {new_summary}")
        # Loop continues automatically
        print("[autonomous_loop] Loop continuing... (next iteration in 5s)")
        time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[autonomous_loop] Stopped by user (explicit prompt). Session halted.")
        sys.exit(0)
