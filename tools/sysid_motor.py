#!/usr/bin/env python3
"""
EVN ALPHA Online System Identification Module

Calibrates the cycle-accurate simulator (motor_models.json / PlantModel) directly
from decoded physical hardware traces (bench/results/autonomous_auto_*/case_*.txt).

Key parameters identified/updated:
1. plant_friction_scale & static_friction (from breakaway and cruise current/duty)
2. plant_lag_ms (from command-to-motion phase delay)
3. plant_tau_ms (from acceleration / deceleration time constant)
4. Piece-to-piece variation statistics across motors
"""

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

REPO_ROOT = Path(__file__).parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
MODELS_JSON = TOOLS_DIR / "motor_models.json"


def parse_trace_file(filepath: Path) -> Dict[str, np.ndarray]:
    """Parse one hardware trace text file into NumPy arrays."""
    if not filepath.exists():
        return {}

    lines = filepath.read_text().splitlines()
    rows = []
    header_info = {}

    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue
        if line_s.startswith("TRACE BEGIN"):
            # Parse parameters from header
            m = re.search(r"target=([-\d.]+)", line_s)
            if m:
                header_info["target"] = float(m.group(1))
            m = re.search(r"pwm=(\d+)", line_s)
            if m:
                header_info["pwm"] = int(m.group(1))
            continue
        if line_s.startswith("t_ms"):
            continue

        parts = line_s.split(",")
        if len(parts) == 8:
            try:
                # t_ms, ref_mdeg, enc_mdeg, hat_mdeg, vref_mdegs, what_mdegs, duty_milli, cur_01ma
                rows.append([float(p) for p in parts])
            except ValueError:
                continue

    if not rows:
        return {}

    arr = np.array(rows, dtype=float)
    return {
        "t_ms": arr[:, 0],
        "ref_mdeg": arr[:, 1],
        "enc_mdeg": arr[:, 2],
        "hat_mdeg": arr[:, 3],
        "vref_mdegs": arr[:, 4],
        "what_mdegs": arr[:, 5],
        "duty_milli": arr[:, 6],
        "cur_01ma": arr[:, 7],
        "header": header_info,
    }


def estimate_plant_parameters_from_traces(run_dir: Path) -> Dict[str, Dict[str, float]]:
    """Analyze all case traces in a run directory to estimate calibrated plant parameters
    for EV3_Large and EV3_Medium.
    """
    trace_files = list(run_dir.glob("case_*.txt"))
    if not trace_files:
        return {}

    large_traces = []
    medium_traces = []

    for tf in trace_files:
        name = tf.name.lower()
        data = parse_trace_file(tf)
        if not data or len(data["t_ms"]) < 50:
            continue
        if "ev3l" in name or "large" in name:
            large_traces.append(data)
        elif "ev3m" in name or "medium" in name:
            medium_traces.append(data)

    results = {}

    for mtype, traces in [("EV3_Large", large_traces), ("EV3_Medium", medium_traces)]:
        if not traces:
            continue

        tau_estimates = []
        lag_estimates = []
        friction_estimates = []

        for tr in traces:
            t = tr["t_ms"]
            duty = tr["duty_milli"] / 1000.0  # fraction [-1..1]
            what = tr["what_mdegs"] / 1000.0  # deg/s
            cur = tr["cur_01ma"] / 10000.0    # Amps

            # 1. Breakaway & static friction: look at duty right before first significant motion
            moving_idx = np.where(np.abs(what) > 10.0)[0]
            if len(moving_idx) > 0 and moving_idx[0] > 1:
                idx0 = moving_idx[0]
                breakaway_duty = np.abs(duty[idx0 - 1])
                # Scale relative to nominal 0.15 duty
                friction_estimates.append(breakaway_duty)

            # 2. Phase lag: delay from non-zero duty until first encoder acceleration
            active_duty_idx = np.where(np.abs(duty) > 0.05)[0]
            if len(active_duty_idx) > 0 and len(moving_idx) > 0:
                t_duty_start = t[active_duty_idx[0]]
                t_motion_start = t[moving_idx[0]]
                lag_ms = max(0.0, t_motion_start - t_duty_start)
                if lag_ms <= 30.0:  # filter outliers
                    lag_estimates.append(lag_ms)

            # 3. Mechanical time constant tau: response during ramp-up phase
            if len(moving_idx) > 10:
                peak_speed = np.max(np.abs(what))
                if peak_speed > 100.0:
                    t_63 = np.where(np.abs(what) >= 0.632 * peak_speed)[0]
                    if len(t_63) > 0 and t_63[0] > moving_idx[0]:
                        tau = t[t_63[0]] - t[moving_idx[0]]
                        if 20.0 <= tau <= 250.0:
                            tau_estimates.append(tau)

        res = {}
        if tau_estimates:
            res["plant_tau_ms"] = float(np.median(tau_estimates))
        if lag_estimates:
            res["plant_lag_ms"] = float(np.median(lag_estimates))
        if friction_estimates:
            # Typical nominal breakaway duty is ~0.10 for Large, ~0.20 for Medium
            base_duty = 0.10 if mtype == "EV3_Large" else 0.25
            median_duty = float(np.median(friction_estimates))
            res["plant_friction_scale"] = float(np.clip(median_duty / base_duty, 0.7, 2.5))

        if res:
            results[mtype] = res

    return results


def update_models_json(updates: Dict[str, Dict[str, float]], models_path: Path = MODELS_JSON, alpha: float = 0.3) -> bool:
    """Apply an exponential moving average update to motor_models.json so simulator
    parameters converge smoothly to real physical behavior without abrupt jumps.
    """
    if not models_path.exists() or not updates:
        return False

    try:
        with open(models_path, "r") as f:
            data = json.load(f)

        modified = False
        for motor_name, params in updates.items():
            if motor_name not in data:
                continue
            m = data[motor_name]
            for p_name, val in params.items():
                old_val = m.get(p_name, val)
                # Exponential moving average filter: new = (1 - alpha) * old + alpha * current
                smoothed_val = (1.0 - alpha) * float(old_val) + alpha * float(val)
                m[p_name] = round(smoothed_val, 3)
                modified = True
                print(f"[SysID] Updated {motor_name}.{p_name}: {old_val:.2f} -> {m[p_name]:.2f} (sampled: {val:.2f})")

        if modified:
            with open(models_path, "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)
            return True
    except Exception as e:
        print(f"[SysID] Error updating models json: {e}")
        return False

    return False


def run_online_sysid(run_dir: Path, alpha: float = 0.25) -> Dict[str, Dict[str, float]]:
    """Entry point called at the end of each autonomous run to keep the simulator calibrated."""
    print(f"\n[SysID] Running online system identification on {run_dir.name}...")
    estimates = estimate_plant_parameters_from_traces(run_dir)
    if estimates:
        update_models_json(estimates, alpha=alpha)
    else:
        print("[SysID] Insufficient trace data for parameter estimation in this run.")
    return estimates


if __name__ == "__main__":
    import sys
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("bench/results")
    if target_dir.is_dir() and not (target_dir / "case_00_r0_M1_EV3L_W40_K180_pos.txt").exists():
        # Find latest auto run
        runs = sorted(list(target_dir.glob("autonomous_auto_*")), key=lambda p: p.stat().st_mtime, reverse=True)
        if runs:
            target_dir = runs[0]

    run_online_sysid(target_dir)
