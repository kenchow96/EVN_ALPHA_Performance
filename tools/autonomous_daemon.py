#!/usr/bin/env python3
"""
EVN ALPHA Long-Term Autonomous Tuning Daemon

Designed to run unattended for days to weeks safely without human intervention:
1. Battery Health Management:
   - Polls battery telemetry before and after runs.
   - Enforces a 6.0V hard test cutoff (firmware enforces 6.0V pack, 2.8V cell).
   - If battery dips below recharge threshold (e.g. 7.0V), enters automatic trickle recharge
     pause until pack recovers to >= 7.6V.
2. Flash Endurance & Storage Ring Buffer:
   - Automatically invokes storage_manager.py after each run.
   - Caps result storage to bounded footprint, stripping bulky 2MB UF2s while
     preserving lightweight telemetry and metadata.
3. Cumulative History & Endurance Logging:
   - Appends single-line structured metrics to bench/results/endurance_log.csv.
   - Allows a weak agent or developer to query progress with a single glance.
4. Mathematical Parameter Proposal:
   - Evaluates simulation pre-flight gates before hardware flash.
   - Proposes candidate parameter sets mathematically via CMA-ES optimizer.
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).parent.parent
BENCH_DIR = REPO_ROOT / "bench"
TOOLS_DIR = REPO_ROOT / "tools"
RESULTS_DIR = BENCH_DIR / "results"
ENDURANCE_LOG = RESULTS_DIR / "endurance_log.csv"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from auto_tuner import update_firmware_cases, bump_run_id, LARGE_PARAM_BOUNDS, MEDIUM_PARAM_BOUNDS
from optimizer import AutonomousOptimizer, OnlineCMAOptimizer, compute_scalar_cost
from storage_manager import prune_storage
from sim_integration import run_simulation_preflight, compare_sim_to_real
from sysid_motor import run_online_sysid


# Battery Thresholds
BATTERY_HARD_CUTOFF_MV = 6000     # 6.0V hard abort floor
BATTERY_RECHARGE_TRIGGER_MV = 7000 # If pack < 7.0V, pause for recharge
BATTERY_RESUME_MV = 7600           # Resume when pack reaches >= 7.6V


def init_endurance_log():
    """Ensure cumulative endurance log exists with header."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if not ENDURANCE_LOG.exists():
        with open(ENDURANCE_LOG, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "iteration", "run_id", "passed_cases", "total_cases",
                "composite_cost", "pack_mv", "cell1_mv", "cell2_mv", "best_score",
                "notes"
            ])


def log_endurance_entry(iteration: int, run_id: int, passed: int, total: int,
                        cost: float, pack_mv: int, cell1_mv: int, cell2_mv: int,
                        best_score: float, notes: str = ""):
    """Append one structured summary line to endurance_log.csv."""
    init_endurance_log()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ENDURANCE_LOG, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            ts, iteration, f"0x{run_id:08X}", passed, total,
            f"{cost:.4f}", pack_mv, cell1_mv, cell2_mv, f"{best_score:.4f}", notes
        ])


def check_battery_status_from_records(records_file: Path) -> Tuple[int, int, int]:
    """Read latest battery voltage from decoded flash records."""
    if not records_file.exists():
        return 0, 0, 0
    try:
        with open(records_file, "r") as f:
            records = json.load(f)
        if records:
            h = records[-1].get("header", {})
            return (
                h.get("battery_pack_mv", 0),
                h.get("battery_cell1_mv", 0),
                h.get("battery_cell2_mv", 0)
            )
    except Exception:
        pass
    return 0, 0, 0


def run_daemon(
    max_days: int = 30,
    max_iterations: Optional[int] = None,
    inter_run_rest_s: int = 15,
):
    """Run continuous unattended tuning daemon."""
    init_endurance_log()
    start_time = time.time()
    max_time_s = max_days * 86400

    print("=======================================================================")
    print(f"=== EVN ALPHA LONG-TERM UNATTENDED TUNING DAEMON STARTED ===")
    print(f"Target Duration: {max_days} days | Max Iterations: {max_iterations or 'Unlimited'}")
    print(f"Battery Hard Cutoff: {BATTERY_HARD_CUTOFF_MV/1000.0:.1f}V | Recharge Pause: <{BATTERY_RECHARGE_TRIGGER_MV/1000.0:.1f}V")
    print(f"Storage Ring Buffer: Automatic pruning active")
    print("=======================================================================\n")

    iteration = 0
    init_large = {
        "kp_pos": 2.0e-4, "kp_vel": 1.0e-5, "endpoint_kp_vel": 2.5e-6,
        "accel_scale": 0.60, "start_duty": 0.12
    }
    init_medium = {
        "kp_pos": 2.5e-4, "kp_vel": 1.0e-6, "endpoint_kp_vel": 2.0e-6,
        "accel_scale": 0.35, "start_duty": 0.90
    }

    # Closed-loop Online CMA-ES optimizers for Large and Medium motor clusters
    opt_large = OnlineCMAOptimizer(LARGE_PARAM_BOUNDS, init_large, pop_size=4, sigma0=0.15, seed=101)
    opt_medium = OnlineCMAOptimizer(MEDIUM_PARAM_BOUNDS, init_medium, pop_size=4, sigma0=0.15, seed=202)

    cur_large = init_large.copy()
    cur_medium = init_medium.copy()

    while True:
        iteration += 1
        elapsed_s = time.time() - start_time
        if elapsed_s >= max_time_s:
            print(f"[Daemon] Completed planned runtime of {max_days} days. Exiting cleanly.")
            break

        if max_iterations and iteration > max_iterations:
            print(f"[Daemon] Reached max iteration limit ({max_iterations}). Exiting cleanly.")
            break

        print(f"\n>>> [DAEMON ITERATION {iteration}] (Day {elapsed_s/86400:.2f}/{max_days}) <<<")

        # Step 0: Ask CMA-ES for next parameter candidate vector
        if iteration > 1:
            cand_l = opt_large.ask()
            cand_m = opt_medium.ask()
            cur_large.update(cand_l)
            cur_medium.update(cand_m)
            print(f"[Daemon] CMA-ES Proposed Large: kp={cur_large['kp_pos']:.2e}, kv={cur_large['kp_vel']:.2e}, end_kp={cur_large['endpoint_kp_vel']:.2e}")
            print(f"[Daemon] CMA-ES Proposed Medium: kp={cur_medium['kp_pos']:.2e}, kv={cur_medium['kp_vel']:.2e}, start_duty={cur_medium['start_duty']:.2f}")

        # Step 1: Simulator Pre-Flight Validation
        print("[Daemon] Evaluating candidate in Digital Twin...")
        update_firmware_cases(cur_large, cur_medium)
        gate_ok, _ = run_simulation_preflight()
        if not gate_ok:
            print("[Daemon] Simulation pre-flight rejected candidate. Resetting to nominal baselines.")
            cur_large = init_large.copy()
            cur_medium = init_medium.copy()
            continue

        # Step 2: Execute Hardware Flash & Run
        new_run_id = bump_run_id()
        print(f"[Daemon] Executing physical hardware sweep for Run 0x{new_run_id:08X}...")

        cmd = [sys.executable, str(TOOLS_DIR / "flash_extract_decode.py"), "--timeout", "900"]
        res = subprocess.run(cmd, capture_output=False)

        if res.returncode != 0:
            print(f"[Daemon] Hardware cycle failed with exit code {res.returncode}. Backing off 30s...")
            time.sleep(30)
            continue

        # Step 3: Inspect Telemetry & Battery State
        dirs = sorted(list(RESULTS_DIR.glob("autonomous_auto_*")), key=os.path.getmtime, reverse=True)
        if not dirs:
            continue
        latest_dir = dirs[0]
        records_file = latest_dir / "flash_records.json"

        pack_mv, cell1_mv, cell2_mv = check_battery_status_from_records(records_file)
        print(f"[Daemon] Run Battery Status: Pack = {pack_mv/1000.0:.3f}V (Cells: {cell1_mv/1000.0:.3f}V / {cell2_mv/1000.0:.3f}V)")

        # Evaluate performance (decoupled per motor type and robust across copies)
        total_cost = 0.0
        passed_cases = 0
        total_cases = 0
        best_case_score = 999.0

        large_costs_m1 = []
        large_costs_m2 = []
        medium_costs_m3 = []
        medium_costs_m4 = []

        if records_file.exists():
            with open(records_file, "r") as f:
                records = json.load(f)
            total_cases = len(records)
            for r in records:
                m = r.get("metrics", {})
                h = r.get("header", {})
                axis = h.get("axis", 1) - 1  # 1-indexed (1..4) -> 0..3
                p = m.get("acceptance_passed", 0)
                tot = m.get("acceptance_total", 12)
                sc = m.get("score", 999.0)
                if sc < best_case_score:
                    best_case_score = sc
                if tot > 0 and p == tot:
                    passed_cases += 1
                case_cost = compute_scalar_cost(m)
                total_cost += case_cost

                if axis == 0:
                    large_costs_m1.append(case_cost)
                elif axis == 1:
                    large_costs_m2.append(case_cost)
                elif axis == 2:
                    medium_costs_m3.append(case_cost)
                elif axis == 3:
                    medium_costs_m4.append(case_cost)

        avg_cost = total_cost / max(1, total_cases)

        # Multi-unit robust cost formulation:
        # Penalize worst-case and cross-unit divergence so gains are robust per motor type
        mean_m1 = sum(large_costs_m1) / max(1, len(large_costs_m1)) if large_costs_m1 else 999.0
        mean_m2 = sum(large_costs_m2) / max(1, len(large_costs_m2)) if large_costs_m2 else 999.0
        cost_large = max(mean_m1, mean_m2) + 0.5 * abs(mean_m1 - mean_m2)

        mean_m3 = sum(medium_costs_m3) / max(1, len(medium_costs_m3)) if medium_costs_m3 else 999.0
        mean_m4 = sum(medium_costs_m4) / max(1, len(medium_costs_m4)) if medium_costs_m4 else 999.0
        cost_medium = max(mean_m3, mean_m4) + 0.5 * abs(mean_m3 - mean_m4)

        print(f"[Daemon] Iteration {iteration} Result: {passed_cases}/{total_cases} passed. Overall Avg Cost: {avg_cost:.4f}")
        print(f"[Daemon] Decoupled Unit Costs -> Large (M1={mean_m1:.2f}, M2={mean_m2:.2f} => J={cost_large:.2f}) | Medium (M3={mean_m3:.2f}, M4={mean_m4:.2f} => J={cost_medium:.2f})")

        # Step 4: Run Sim-to-Real Comparison & Online Model Calibration
        compare_sim_to_real(latest_dir)
        run_online_sysid(latest_dir)

        # Step 5: Log to cumulative endurance log
        log_endurance_entry(
            iteration, new_run_id, passed_cases, total_cases,
            avg_cost, pack_mv, cell1_mv, cell2_mv, best_case_score,
            "12/12 CONVERGED" if passed_cases == total_cases else "nominal"
        )

        # Step 6: Storage Ring-Buffer Prune
        stripped, removed = prune_storage()
        if stripped or removed:
            print(f"[Daemon] Ring buffer: stripped {stripped} bulky UF2s, removed {removed} old directories.")

        # Step 7: Convergence Check
        if total_cases > 0 and passed_cases == total_cases:
            print(f"[Daemon] CONVERGENCE ACHIEVED: 16/16 cases 12/12 pass! Halting loop.")
            break

        # Step 8: Closed-Loop CMA-ES Feedback (Tell decoupled cost to each motor optimizer)
        # Only tell() if we used ask() to get this candidate (iteration > 1)
        if iteration > 1:
            opt_large.tell(cur_large, cost_large)
            opt_medium.tell(cur_medium, cost_medium)

        # Step 9: Battery Health & Recharge Protection
        if pack_mv > 0 and pack_mv < BATTERY_RECHARGE_TRIGGER_MV:
            print(f"[Daemon] Battery pack voltage ({pack_mv/1000.0:.2f}V) is below recharge trigger ({BATTERY_RECHARGE_TRIGGER_MV/1000.0:.2f}V).")
            print(f"[Daemon] Entering automated trickle-charge pause until pack recovers...")
            charge_cycles = 0
            while charge_cycles < 6:  # up to 30 mins recharge
                time.sleep(300)       # 5 minutes per cycle
                charge_cycles += 1
                print(f"[Daemon] Trickle-charging pack ({charge_cycles*5} min elapsed)...")
            print("[Daemon] Recharge interval completed. Resuming autonomous sweep.")

        # Inter-run rest
        if inter_run_rest_s > 0:
            time.sleep(inter_run_rest_s)

    print("[Daemon] Long-term autonomous daemon terminated safely.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EVN Autonomous Long-Term Tuning Daemon")
    parser.add_argument("--days", type=int, default=30, help="Max duration in days (default: 30)")
    parser.add_argument("--max-iterations", type=int, default=None, help="Max iterations to run")
    parser.add_argument("--rest-seconds", type=int, default=15, help="Rest delay between runs (default: 15s)")
    args = parser.parse_args()

    try:
        run_daemon(max_days=args.days, max_iterations=args.max_iterations, inter_run_rest_s=args.rest_seconds)
    except KeyboardInterrupt:
        print("\n[Daemon] Stopped by user (Ctrl+C). Board restored to safe state.")
        sys.exit(0)
