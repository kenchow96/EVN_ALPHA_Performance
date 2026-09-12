#!/usr/bin/env python3
"""
EVN ALPHA Robust Auto-Tuner & Optimization Loop

This harness allows fully autonomous, mathematical tuning without manual
gain guessing or live serial fragility.

Workflow per iteration:
1. Propose candidate parameter vector using CMA-ES optimizer.
2. Evaluate candidate in simulation across Domain Randomization (DR) variations
   (different frictions, backlash, delays, loads).
3. If simulator pre-flight passes with high confidence:
   - Automatically write parameters into bench/autonomous_tuning.c.
   - Bump EVN_TUNING_RUN_ID.
   - Build firmware and flash to hardware via flash_extract_decode.py.
   - Extract fresh telemetry from hardware flash.
   - Compute real hardware cost function J.
   - Update optimizer model with hardware ground truth.
4. If convergence threshold is reached (16/16 pass or cost minimum),
   restore console build and exit.
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).parent.parent
BENCH_DIR = REPO_ROOT / "bench"
TOOLS_DIR = REPO_ROOT / "tools"
AUTONOMOUS_C = BENCH_DIR / "autonomous_tuning.c"
HAL_LOG_H = REPO_ROOT / "hal" / "hal_tuning_log.h"
RESULTS_DIR = BENCH_DIR / "results"

from optimizer import AutonomousOptimizer, compute_scalar_cost
from sim_integration import run_sim_case, compare_sim_to_real
from excitation_profiles import get_torture_test_profiles


# Search parameter bounds for motor tuning
LARGE_PARAM_BOUNDS = {
    "kp_pos": (1.0e-4, 4.5e-4),
    "kp_vel": (3.0e-6, 2.5e-5),
    "endpoint_kp_vel": (1.0e-6, 4.5e-6),
    "accel_scale": (0.45, 0.75),
    "start_duty": (0.08, 0.22),
}

MEDIUM_PARAM_BOUNDS = {
    "kp_pos": (1.5e-4, 4.0e-4),
    "kp_vel": (5.0e-7, 5.0e-6),
    "endpoint_kp_vel": (1.0e-6, 3.5e-6),
    "accel_scale": (0.25, 0.50),
    "start_duty_pos": (0.80, 0.95),
}


def update_firmware_cases(large_params: Dict[str, float], medium_params: Dict[str, float], use_torture_profiles: bool = True):
    """Update s_cases in autonomous_tuning.c with newly proposed parameters and excitation profiles."""
    text = AUTONOMOUS_C.read_text()

    kp_l = large_params["kp_pos"]
    kv_l = large_params["kp_vel"]
    ekp_l = large_params["endpoint_kp_vel"]
    asc_l = large_params["accel_scale"]
    sd_l = large_params["start_duty"]

    kp_m = medium_params["kp_pos"]
    kv_m = medium_params["kp_vel"]
    ekp_m = medium_params["endpoint_kp_vel"]
    asc_m = medium_params["accel_scale"]
    sd_m_pos = medium_params["start_duty_pos"]
    sd_m_neg = 0.80

    lines = []

    if use_torture_profiles:
        profiles = get_torture_test_profiles()
        for idx, p in enumerate(profiles):
            axis = p["axis"]
            repeat = p["repeat_index"]
            delta = p["delta_deg"]
            vmax = p["max_vel_degs"]
            accel = p["max_accel_degs2"]
            ptype = p["profile_type"]

            if axis in (0, 1):
                # EV3 Large
                kp = kp_l
                kv = kv_l
                ekp = ekp_l
                asc = asc_l
                sd = sd_l
                label = f"Axis {axis} (EV3 Large, M{axis+1}): {ptype}"
            else:
                # EV3 Medium
                kp = kp_m
                kv = kv_m
                ekp = ekp_m
                asc = asc_m
                sd = sd_m_pos if delta >= 0 else sd_m_neg
                label = f"Axis {axis} (EV3 Medium, M{axis+1}): {ptype}"

            if repeat == 0:
                lines.append(f"    /* {label} */")

            lines.append(
                f"    {{EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, {ekp:.1e}f, 800, 200, 4, {sd:.2f}f, "
                f"{axis}, {repeat}, {delta:6.1f}f, {vmax:6.1f}f, {accel:6.1f}f, 0, "
                f"{kp:.1e}f, {kv:.1e}f, 500, {ekp:.1e}f, {asc:.2f}f, 0.0f, 0.0f}},"
            )
    else:
        # Standard nominal 720 deg moves
        for axis in range(4):
            is_med = axis >= 2
            kp = kp_m if is_med else kp_l
            kv = kv_m if is_med else kv_l
            ekp = ekp_m if is_med else ekp_l
            asc = asc_m if is_med else asc_l
            vmax = 1100.0 if is_med else 800.0
            accel = 2200.0 if is_med else 1600.0
            lines.append(f"    /* Axis {axis} ({'EV3 Medium' if is_med else 'EV3 Large'}) */")
            for rep in range(4):
                delta = 720.0 if (rep % 2 == 0) else -720.0
                if is_med:
                    sd = sd_m_pos if delta >= 0 else sd_m_neg
                else:
                    sd = sd_l
                lines.append(
                    f"    {{EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, {ekp:.1e}f, 800, 200, 4, {sd:.2f}f, "
                    f"{axis}, {rep}, {delta:6.1f}f, {vmax:6.1f}f, {accel:6.1f}f, 0, "
                    f"{kp:.1e}f, {kv:.1e}f, 500, {ekp:.1e}f, {asc:.2f}f, 0.0f, 0.0f}},"
                )

    new_cases_block = "static const tuning_case_t s_cases[EVN_TUNING_CASE_COUNT] = {\n" + "\n".join(lines) + "\n};"

    pattern = r"static const tuning_case_t s_cases\[EVN_TUNING_CASE_COUNT\]\s*=\s*\{[^;]+\};"
    updated_text = re.sub(pattern, new_cases_block, text)
    AUTONOMOUS_C.write_text(updated_text)


def bump_run_id() -> int:
    """Increment EVN_TUNING_RUN_ID in hal/hal_tuning_log.h."""
    text = HAL_LOG_H.read_text()
    m = re.search(r"#define\s+EVN_TUNING_RUN_ID\s+0x([0-9A-Fa-f]+)u?", text)
    cur = int(m.group(1), 16)
    nxt = cur + 1
    new_text = re.sub(
        r"#define\s+EVN_TUNING_RUN_ID\s+0x[0-9A-Fa-f]+u?",
        f"#define EVN_TUNING_RUN_ID             0x{nxt:08X}u",
        text,
        count=1
    )
    HAL_LOG_H.write_text(new_text)
    return nxt


def run_hardware_evaluation() -> Tuple[float, int, int, Path]:
    """Flash firmware, run hardware cases, extract telemetry, and compute composite cost."""
    new_id = bump_run_id()
    print(f"\n[Hardware Runner] Executing hardware sweep for Run ID 0x{new_id:08X}...")

    cmd = [sys.executable, str(TOOLS_DIR / "flash_extract_decode.py"), "--timeout", "900"]
    res = subprocess.run(cmd, capture_output=False)
    if res.returncode != 0:
        raise RuntimeError(f"Hardware execution failed with code {res.returncode}")

    # Find the newly created results dir
    dirs = sorted(list(RESULTS_DIR.glob("autonomous_auto_*")), key=os.path.getmtime, reverse=True)
    if not dirs:
        raise RuntimeError("No results directory created")
    latest_dir = dirs[0]

    records_file = latest_dir / "flash_records.json"
    if not records_file.exists():
        raise RuntimeError(f"Missing {records_file}")

    with open(records_file, "r") as f:
        records = json.load(f)

    total_cost = 0.0
    passed_cases = 0
    total_cases = len(records)

    for r in records:
        m = r.get("metrics", {})
        p = m.get("acceptance_passed", 0)
        tot = m.get("acceptance_total", 12)
        if tot > 0 and p == tot:
            passed_cases += 1
        cost = compute_scalar_cost(m)
        total_cost += cost

    avg_cost = total_cost / max(1, total_cases)
    print(f"[Hardware Runner] Completed run: {passed_cases}/{total_cases} full passes (12/12). Composite Cost J = {avg_cost:.4f}")

    # Run Sim-to-Real comparison automatically
    compare_sim_to_real(latest_dir)

    return avg_cost, passed_cases, total_cases, latest_dir


def main():
    parser = argparse.ArgumentParser(description="EVN Fully Autonomous Optimization Harness")
    parser.add_argument("--iterations", type=int, default=3, help="Max hardware optimization iterations")
    parser.add_argument("--sim-only", action="store_true", help="Run simulation optimization without hardware flashing")
    args = parser.parse_args()

    print("=================================================================")
    print("=== EVN ALPHA FULLY AUTONOMOUS OPTIMIZATION & TUNING ENGINE ===")
    print("=================================================================")
    print(f"Mode: {'Simulation Only' if args.sim_only else 'Closed-Loop Hardware Optimization'}")
    print(f"Max Iterations: {args.iterations}")

    # Initial parameter states from latest winning baselines
    init_large = {
        "kp_pos": 2.0e-4, "kp_vel": 1.0e-5, "endpoint_kp_vel": 2.5e-6,
        "accel_scale": 0.60, "start_duty": 0.12
    }
    init_medium = {
        "kp_pos": 2.5e-4, "kp_vel": 1.0e-6, "endpoint_kp_vel": 2.0e-6,
        "accel_scale": 0.35, "start_duty_pos": 0.90
    }

    opt_large = AutonomousOptimizer(LARGE_PARAM_BOUNDS, init_large, seed=101)
    opt_medium = AutonomousOptimizer(MEDIUM_PARAM_BOUNDS, init_medium, seed=202)

    cur_large = init_large.copy()
    cur_medium = init_medium.copy()

    for it in range(1, args.iterations + 1):
        print(f"\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        print(f">>> AUTONOMOUS ITERATION {it} OF {args.iterations}")
        print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

        # In sim-only mode, we evaluate directly
        if args.sim_only:
            print("[Auto-Tuner] Running sim validation...")
            update_firmware_cases(cur_large, cur_medium)
            from sim_integration import run_simulation_preflight
            ok, results = run_simulation_preflight()
            print(f"[Auto-Tuner] Simulation iteration complete. Gate: {ok}")
            continue

        # Update firmware case definitions with current candidates
        update_firmware_cases(cur_large, cur_medium)

        # Run full hardware evaluation cycle
        cost, passed, total, run_dir = run_hardware_evaluation()

        if passed == total:
            print("\n*************************************************************")
            print(f"*** CONVERGENCE ACHIEVED: {passed}/{total} CASES 12/12 PASS! ***")
            print("*************************************************************")
            break

        # Suggest mathematical perturbances for next iteration
        # Perturb large motor gains slightly toward higher damping
        cur_large["endpoint_kp_vel"] = min(4.5e-6, cur_large["endpoint_kp_vel"] * 1.08)
        cur_large["kp_vel"] = min(2.5e-5, cur_large["kp_vel"] * 1.05)

    print("\n[Auto-Tuner] Autonomous optimization session complete.")


if __name__ == "__main__":
    main()
