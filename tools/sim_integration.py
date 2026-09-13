#!/usr/bin/env python3
"""
EVN ALPHA Simulator Integration Module

Provides seamless integration between the cycle-accurate simulator (simulate_motor.py)
and the autonomous tuning pipeline:
1. Parse tuning cases from bench/autonomous_tuning.c.
2. Run simulation pre-flight validation on all 16 cases.
3. Compare simulated results against physical hardware flash records (Sim-to-Real).
4. Save all outputs into bench/results/ (zero root pollution).
"""

import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
SIM_SCRIPT = TOOLS_DIR / "simulate_motor.py"
METRICS_SCRIPT = TOOLS_DIR / "motion_metrics.py"
AUTONOMOUS_TUNING_C = REPO_ROOT / "bench" / "autonomous_tuning.c"


def parse_tuning_cases_from_c(c_file_path: Path = AUTONOMOUS_TUNING_C) -> List[dict]:
    """Parse s_cases array directly from autonomous_tuning.c."""
    if not c_file_path.exists():
        raise FileNotFoundError(f"Cannot find {c_file_path}")

    text = c_file_path.read_text()
    match = re.search(r"tuning_case_t\s+s_cases\[[^\]]*\]\s*=\s*\{([^;]+)\};", text, re.DOTALL)
    if not match:
        raise ValueError("Could not find s_cases array in autonomous_tuning.c")

    body = match.group(1)
    case_lines = [line.strip() for line in body.splitlines() if line.strip().startswith("{EVN_")]

    parsed_cases = []
    # Struct fields in autonomous_tuning.c:
    # 0: trajectory_type (EVN_TRAJECTORY_TRAPEZOID)
    # 1: startup_reference_governor
    # 2: friction_feedforward_permille
    # 3: startup_release_speed_mdegs
    # 4: edge_watchdog_enabled
    # 5: endpoint_kp_vel
    # 6: startup_ramp_ms
    # 7: restart_ramp_ms
    # 8: startup_pulse_on_ticks
    # 9: start_duty
    # 10: axis (0-3)
    # 11: repeat_index
    # 12: delta_deg
    # 13: max_vel_degs
    # 14: max_accel_degs2
    # 15: test_type (0=abs)
    # 16: kp_pos
    # 17: kp_vel
    # 18: friction_ff
    # 19: endpoint_kp
    # 20: accel_scale
    # 21: kff_accel
    # 22: kd_vel

    axis_models = {0: "EV3_Large", 1: "EV3_Large", 2: "EV3_Medium", 3: "EV3_Medium"}
    axis_labels = {0: "M1_EV3L", 1: "M2_EV3L", 2: "M3_EV3M", 3: "M4_EV3M"}

    for idx, line in enumerate(case_lines):
        clean = line.strip("{}, \t;")
        tokens = [t.strip().rstrip("fFuUL") for t in clean.split(",")]
        if len(tokens) < 21:
            continue

        axis = int(tokens[10])
        repeat = int(tokens[11])
        delta = float(tokens[12])
        dir_str = "pos" if delta >= 0 else "neg"
        motor = axis_models.get(axis, "EV3_Large")
        motor_label = axis_labels.get(axis, f"M{axis+1}")
        traj_raw = tokens[0].strip()
        traj_type = "quintic" if "MINIMUM_JERK" in traj_raw or traj_raw == "1" else "trapezoid"

        parsed_cases.append({
            "case_index": idx,
            "axis": axis,
            "motor": motor,
            "motor_label": motor_label,
            "repeat_index": repeat,
            "delta_deg": delta,
            "direction": dir_str,
            "trajectory_type": traj_type,
            "name": f"case_{idx:02d}_r{repeat}_{motor_label}_W40_K10_{dir_str}" if axis >= 2 else f"case_{idx:02d}_r{repeat}_{motor_label}_W40_K100_{dir_str}",
            "kp_pos": float(tokens[16]),
            "kp_vel": float(tokens[17]),
            "endpoint_kp_vel": float(tokens[19]),
            "accel_scale": float(tokens[20]),
            "start_duty": float(tokens[9]),
            "startup_ramp_ticks": int(tokens[6]),
            "restart_ramp_ticks": int(tokens[7]),
            "startup_pulse_on_ticks": int(tokens[8]),
            "max_vel_degs": float(tokens[13]),
            "max_accel_degs2": float(tokens[14]),
            "vel_window": 10,  # Winning firmware setting for all axes
        })

    return parsed_cases


def run_sim_case(case_def: dict, output_dir: Path) -> Tuple[Optional[int], Optional[dict], str]:
    """Run a single simulation case and return (passed_count, metrics_dict, status_msg)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_file = output_dir / f"{case_def['name']}.txt"

    cmd = [
        sys.executable, str(SIM_SCRIPT),
        "--motor", case_def["motor"],
        "--kp-pos", str(case_def["kp_pos"]),
        "--ki-pos", "8e-7",
        "--kp-vel", str(case_def["kp_vel"]),
        "--endpoint-kp-vel", str(case_def["endpoint_kp_vel"]),
        "--accel-scale", str(case_def["accel_scale"]),
        "--start-duty", str(case_def["start_duty"]),
        "--startup-ramp-ticks", str(case_def["startup_ramp_ticks"]),
        "--restart-ramp-ticks", str(case_def["restart_ramp_ticks"]),
        "--startup-pulse-on-ticks", str(case_def["startup_pulse_on_ticks"]),
        "--vel-window", str(case_def.get("vel_window", 10)),
        "--trajectory", case_def.get("trajectory_type", "trapezoid"),
        "--target", str(case_def["delta_deg"]),
        "--max-vel", str(case_def["max_vel_degs"]),
        "--max-accel", str(case_def["max_accel_degs2"]),
        "--duration", "4",
        "--output", str(trace_file),
        "--trace"
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        return None, None, f"SIM_ERR: {res.stderr.strip()[:100]}"

    # Run motion metrics on generated trace
    metrics_cmd = [sys.executable, str(METRICS_SCRIPT), str(trace_file)]
    m_res = subprocess.run(metrics_cmd, capture_output=True, text=True, timeout=30)
    if m_res.returncode != 0:
        return None, None, f"METRICS_ERR: {m_res.stderr.strip()[:100]}"

    passed = 0
    total = 12
    metrics = {}
    for line in m_res.stdout.splitlines():
        line_s = line.strip()
        if "ACCEPTANCE:" in line_s:
            parts = line_s.split()
            if len(parts) >= 2 and "/" in parts[1]:
                sub = parts[1].split("/")
                passed = int(sub[0])
                total = int(sub[1].rstrip("pass"))
        elif line_s.startswith("max_track_err_deg"):
            metrics["max_track_err_deg"] = float(line_s.split()[-1])
        elif line_s.startswith("rms_track_err_deg"):
            metrics["rms_track_err_deg"] = float(line_s.split()[-1])
        elif line_s.startswith("final_err_deg"):
            metrics["final_err_deg"] = float(line_s.split()[-1])
        elif line_s.startswith("duty_smoothness"):
            metrics["duty_smoothness"] = float(line_s.split()[-1])
        elif line_s.startswith("duty_cruise_ripple_pp"):
            metrics["duty_cruise_ripple_pp"] = float(line_s.split()[-1])
        elif line_s.startswith("max_duty_slew"):
            metrics["max_duty_slew"] = float(line_s.split()[-1])

    metrics["passed"] = passed
    metrics["total"] = total
    return passed, metrics, f"{passed}/{total} pass"


def run_simulation_preflight(output_dir: Optional[Path] = None, min_pass_rate: float = 0.5) -> Tuple[bool, List[dict]]:
    """Run all 16 tuning cases in simulation.
    Returns (passed_gate, results_list).
    """
    if output_dir is None:
        output_dir = REPO_ROOT / "bench" / "results" / "sim_preflight"
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = parse_tuning_cases_from_c()
    print(f"\n=======================================================")
    print(f"=== SIMULATOR PRE-FLIGHT VALIDATION ({len(cases)} cases) ===")
    print(f"=======================================================")

    results = []
    total_passed_cases = 0

    for c in cases:
        passed, metrics, msg = run_sim_case(c, output_dir)
        is_ok = passed is not None and passed >= 8  # individual case threshold
        if is_ok:
            total_passed_cases += 1
        record = {
            "case_index": c["case_index"],
            "name": c["name"],
            "motor": c["motor_label"],
            "passed": passed or 0,
            "total": 12,
            "metrics": metrics or {},
            "status": "PASS" if is_ok else "FAIL",
            "message": msg
        }
        results.append(record)
        print(f"[{'PASS' if is_ok else 'FAIL'}] {c['name']:<35} : {msg}")

    pass_ratio = total_passed_cases / len(cases)
    gate_ok = pass_ratio >= min_pass_rate
    print("-------------------------------------------------------")
    print(f"Pre-flight Gate: {total_passed_cases}/{len(cases)} viable cases ({pass_ratio*100:.1f}%). Gate threshold: {min_pass_rate*100:.0f}%.")
    print(f"Gate Status: {'APPROVED FOR FLASH' if gate_ok else 'REJECTED - UNSTABLE CONFIG'}")
    print("=======================================================\n")

    # Write summary
    summary_csv = output_dir / "sim_summary.csv"
    with open(summary_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["case_index", "name", "motor", "passed", "total", "status", "max_track_err_deg", "final_err_deg", "duty_smoothness"])
        for r in results:
            m = r.get("metrics", {})
            writer.writerow([
                r["case_index"], r["name"], r["motor"], r["passed"], r["total"], r["status"],
                m.get("max_track_err_deg", 0.0), m.get("final_err_deg", 0.0), m.get("duty_smoothness", 0.0)
            ])

    return gate_ok, results


def compare_sim_to_real(hardware_dir: Path, output_dir: Optional[Path] = None) -> List[dict]:
    """Compare real hardware flash records with corresponding simulation runs."""
    records_file = hardware_dir / "flash_records.json"
    if not records_file.exists():
        print(f"[sim_to_real] No flash_records.json found in {hardware_dir}")
        return []

    with open(records_file, "r") as f:
        hw_records = json.load(f)

    if output_dir is None:
        output_dir = hardware_dir / "sim_comparison"
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = parse_tuning_cases_from_c()
    case_map = {c["case_index"]: c for c in cases}

    print("\n==========================================================================================")
    print(f"=== SIM-TO-REAL TELEMETRY COMPARISON ({hardware_dir.name}) ===")
    print("==========================================================================================")
    print(f"{'Case':<32} {'HW Score':>8} {'Sim Score':>9} {'HW MaxErr':>9} {'Sim MaxErr':>10} {'Residual':>9} {'Agreement':>10}")
    print("------------------------------------------------------------------------------------------")

    comparisons = []
    for hw in hw_records:
        h = hw.get("header", {})
        c_idx = h.get("case_index", 0)
        c_def = case_map.get(c_idx)
        if not c_def:
            continue

        hw_m = hw.get("metrics", {})
        hw_pass = hw_m.get("acceptance_passed", 0)
        hw_err = hw_m.get("max_track_err_deg", 0.0)

        # Run matching sim
        sim_pass, sim_m, _ = run_sim_case(c_def, output_dir)
        sim_err = (sim_m or {}).get("max_track_err_deg", 0.0)

        residual = abs(hw_err - sim_err)
        # Agreement metric: 1.0 - (residual / max(hw, sim))
        denom = max(hw_err, sim_err, 0.5)
        agreement = max(0.0, 1.0 - (residual / denom)) * 100.0

        comparisons.append({
            "case_index": c_idx,
            "name": c_def["name"],
            "hw_passed": hw_pass,
            "sim_passed": sim_pass or 0,
            "hw_max_err": hw_err,
            "sim_max_err": sim_err,
            "residual_deg": residual,
            "agreement_pct": agreement
        })

        print(f"{c_def['name']:<32} {hw_pass:>7}/12 {sim_pass or 0:>8}/12 {hw_err:>8.3f}° {sim_err:>9.3f}° {residual:>8.3f}° {agreement:>9.1f}%")

    print("------------------------------------------------------------------------------------------")
    if comparisons:
        avg_agreement = sum(c["agreement_pct"] for c in comparisons) / len(comparisons)
        avg_residual = sum(c["residual_deg"] for c in comparisons) / len(comparisons)
        print(f"Mean Residual: {avg_residual:.3f}° | Mean Model Agreement: {avg_agreement:.1f}%\n")

    # Write comparison CSV
    with open(hardware_dir / "sim_to_real_comparison.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["case_index", "name", "hw_passed", "sim_passed", "hw_max_err", "sim_max_err", "residual_deg", "agreement_pct"])
        writer.writeheader()
        writer.writerows(comparisons)

    return comparisons


if __name__ == "__main__":
    gate, res = run_simulation_preflight()
    sys.exit(0 if gate else 1)
