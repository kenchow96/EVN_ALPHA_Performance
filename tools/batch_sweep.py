#!/usr/bin/env python3
"""
EVN ALPHA Batch Sweep — Parallel Parameter Optimization

Runs massive parallel parameter sweeps on the digital twin simulator.
Identifies top-N candidates by tracking error metrics.
Exports candidates for hardware validation via tune_session.py.
"""

import json
import csv
import argparse
import subprocess
import sys
import time
import math
from dataclasses import dataclass, field
from typing import Optional, Callable
from pathlib import Path
from multiprocessing import Pool, cpu_count
from concurrent.futures import ProcessPoolExecutor, as_completed
import itertools


# ─────────────────────────────────────────────────────────────────────────────
# Parameter Space Definition
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ParamRange:
    """Defines a parameter sweep range"""
    name: str
    min_val: float
    max_val: float
    steps: int
    log_scale: bool = False
    
    def generate(self) -> list[float]:
        if self.log_scale:
            return [self.min_val * (self.max_val / self.min_val) ** (i / (self.steps - 1)) 
                    for i in range(self.steps)]
        else:
            return [self.min_val + (self.max_val - self.min_val) * i / (self.steps - 1) 
                    for i in range(self.steps)]


# Default parameter search spaces (centered around known good values)
DEFAULT_GAIN_SPACES = {
    'EV3_Large': {
        'kp_pos': ParamRange('kp_pos', 1.0e-4, 5.0e-4, 5, log_scale=True),
        'ki_pos': ParamRange('ki_pos', 4.0e-7, 1.6e-6, 4, log_scale=True),
        'kp_vel': ParamRange('kp_vel', 1.0e-6, 5.0e-6, 5, log_scale=True),
        'kd_vel': ParamRange('kd_vel', 0.0, 1.0e-7, 3),
        'kff_accel': ParamRange('kff_accel', 0.0, 1.0e-8, 3),
        'endpoint_kp_vel': ParamRange('endpoint_kp_vel', 0.0, 2.0e-6, 4),
        'vbus_comp': ParamRange('vbus_comp', 7000.0, 8000.0, 3),
        'i_limit': ParamRange('i_limit', 0.15, 0.30, 4),
        'deadzone': ParamRange('deadzone', 200.0, 600.0, 4),
        'min_duty': ParamRange('min_duty', 0.08, 0.20, 4),
        'start_duty': ParamRange('start_duty', 0.08, 0.20, 4),
        'vel_window': ParamRange('vel_window', 20, 80, 4, log_scale=False),
    },
    'EV3_Medium': {
        'kp_pos': ParamRange('kp_pos', 1.0e-4, 4.0e-4, 5, log_scale=True),
        'ki_pos': ParamRange('ki_pos', 4.0e-7, 1.6e-6, 4, log_scale=True),
        'kp_vel': ParamRange('kp_vel', 0.5e-6, 2.0e-6, 5, log_scale=True),
        'kd_vel': ParamRange('kd_vel', 0.0, 1.0e-7, 3),
        'kff_accel': ParamRange('kff_accel', 0.0, 1.0e-8, 3),
        'endpoint_kp_vel': ParamRange('endpoint_kp_vel', 0.0, 2.0e-6, 4),
        'vbus_comp': ParamRange('vbus_comp', 7000.0, 8000.0, 3),
        'i_limit': ParamRange('i_limit', 0.15, 0.30, 4),
        'deadzone': ParamRange('deadzone', 200.0, 600.0, 4),
        'min_duty': ParamRange('min_duty', 0.40, 0.70, 4),
        'start_duty': ParamRange('start_duty', 0.40, 0.70, 4),
        'vel_window': ParamRange('vel_window', 20, 80, 4, log_scale=False),
    },
    'NXT': {
        'kp_pos': ParamRange('kp_pos', 1.0e-4, 5.0e-4, 5, log_scale=True),
        'ki_pos': ParamRange('ki_pos', 4.0e-7, 1.6e-6, 4, log_scale=True),
        'kp_vel': ParamRange('kp_vel', 1.0e-6, 5.0e-6, 5, log_scale=True),
        'kd_vel': ParamRange('kd_vel', 0.0, 1.0e-7, 3),
        'kff_accel': ParamRange('kff_accel', 0.0, 1.0e-8, 3),
        'endpoint_kp_vel': ParamRange('endpoint_kp_vel', 0.0, 2.0e-6, 4),
        'vbus_comp': ParamRange('vbus_comp', 7000.0, 8000.0, 3),
        'i_limit': ParamRange('i_limit', 0.15, 0.30, 4),
        'deadzone': ParamRange('deadzone', 200.0, 600.0, 4),
        'min_duty': ParamRange('min_duty', 0.08, 0.20, 4),
        'start_duty': ParamRange('start_duty', 0.08, 0.20, 4),
        'vel_window': ParamRange('vel_window', 20, 80, 4, log_scale=False),
    }
}


# Trajectory parameter spaces
TRAJECTORY_SPACES = {
    'vel_scale': ParamRange('vel_scale', 0.6, 1.0, 5),
    'accel_scale': ParamRange('accel_scale', 0.2, 1.0, 5),
    'trajectory_type': [0, 1],  # 0=trapezoid, 1=quintic
}

# Feedforward parameter spaces
FF_SPACES = {
    'friction_permille': ParamRange('friction_permille', 300, 1000, 4),
}


# ─────────────────────────────────────────────────────────────────────────────
# Sweep Configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SweepConfig:
    motor: str = 'EV3_Medium'
    target_deg: float = 360.0
    max_vel_degs: float = 1100.0
    max_accel_degs2: float = 2000.0
    duration_s: float = 3.0
    battery_mv: int = 7400
    output_dir: str = 'bench/results/sweeps'
    num_workers: int = 0  # 0 = auto
    max_configs: int = 1000
    random_sample: bool = False
    seed: int = 42


# ─────────────────────────────────────────────────────────────────────────────
# Metric Computation (inline for speed, mirrors motion_metrics.py)
# ─────────────────────────────────────────────────────────────────────────────

def compute_metrics(trace_rows: list[dict]) -> dict:
    """Compute key metrics from trace rows. Returns dict of metric_name -> value."""
    if len(trace_rows) < 10:
        return {}
    
    # Extract arrays
    t = [r['t_ms'] for r in trace_rows]
    ref = [r['ref_mdeg'] / 1000.0 for r in trace_rows]  # deg
    enc = [r['enc_mdeg'] / 1000.0 for r in trace_rows]   # deg
    hat = [r['hat_mdeg'] / 1000.0 for r in trace_rows]   # deg
    vref = [r['vref_mdegs'] / 1000.0 for r in trace_rows]  # deg/s
    what = [r['what_mdegs'] / 1000.0 for r in trace_rows]  # deg/s
    duty = [r['duty_milli'] / 1000.0 for r in trace_rows]
    cur = [r['cur_01ma'] / 10000.0 for r in trace_rows]   # A
    
    n = len(t)
    dt_s = [(t[i+1] - t[i]) / 1000.0 for i in range(n-1)]
    
    # Position error
    pos_err = [ref[i] - enc[i] for i in range(n)]
    pos_err_abs = [abs(e) for e in pos_err]
    
    # Cruise region: after 80% of move time, before 95%
    move_duration = t[-1] - t[0] if t[-1] > t[0] else 1
    cruise_start_idx = int(0.8 * n)
    cruise_end_idx = int(0.95 * n)
    cruise_err = pos_err_abs[cruise_start_idx:cruise_end_idx] if cruise_end_idx > cruise_start_idx else pos_err_abs
    
    # Metrics
    metrics = {}
    metrics['max_track_err_deg'] = max(pos_err_abs) if pos_err_abs else 0
    metrics['rms_track_err_deg'] = math.sqrt(sum(e*e for e in pos_err_abs) / len(pos_err_abs)) if pos_err_abs else 0
    metrics['final_err_deg'] = abs(pos_err[-1]) if pos_err else 0
    metrics['cruise_rms_err_deg'] = math.sqrt(sum(e*e for e in cruise_err) / len(cruise_err)) if cruise_err else 0
    
    # Overshoot
    target_deg = ref[-1] if ref else 0
    max_enc = max(enc) if target_deg >= 0 else min(enc)
    if target_deg >= 0:
        metrics['overshoot_deg'] = max(0.0, max_enc - target_deg)
    else:
        metrics['overshoot_deg'] = max(0.0, target_deg - min(enc))
    
    # Settle time (within 0.5 deg of target, sustained for 100ms)
    settle_threshold = 0.5
    settle_duration_ms = 100
    settled = False
    settle_ms = 0
    for i in range(n):
        if abs(pos_err[i]) <= settle_threshold:
            if not settled:
                settle_start = t[i]
                settled = True
            elif t[i] - settle_start >= settle_duration_ms:
                settle_ms = t[i] - settle_start
                break
        else:
            settled = False
    metrics['settle_ms'] = settle_ms
    
    # Residual vibration (peak-to-peak in last 20% of trace)
    vib_start = int(0.8 * n)
    vib_enc = enc[vib_start:]
    if len(vib_enc) > 1:
        metrics['residual_vibration_pp_deg'] = max(vib_enc) - min(vib_enc)
    else:
        metrics['residual_vibration_pp_deg'] = 0
    
    # Regressive instability (direction reversals in velocity)
    vel_changes = 0
    for i in range(1, n-1):
        if what[i-1] > 0 and what[i+1] < 0:
            vel_changes += 1
        elif what[i-1] < 0 and what[i+1] > 0:
            vel_changes += 1
    metrics['regressive_reversals'] = vel_changes
    
    # Duty saturation
    saturated = sum(1 for d in duty if abs(d) >= 0.99)
    metrics['duty_saturation_frac'] = saturated / n if n > 0 else 0
    
    # Duty smoothness (1 - normalized derivative variance)
    duty_deriv = [abs(duty[i+1] - duty[i]) / dt_s[i] if dt_s[i] > 0 else 0 for i in range(n-1)]
    if duty_deriv:
        metrics['duty_smoothness'] = 1.0 / (1.0 + sum(d*d for d in duty_deriv) / len(duty_deriv))
    else:
        metrics['duty_smoothness'] = 1.0
    
    # Current
    metrics['current_rms_A'] = math.sqrt(sum(c*c for c in cur) / len(cur)) if cur else 0
    metrics['current_peak_A'] = max(abs(c) for c in cur) if cur else 0
    metrics['energy_proxy'] = sum(abs(d)*abs(c) for d,c in zip(duty, cur))
    
    return metrics


def score_config(metrics: dict, weights: Optional[dict] = None) -> float:
    """Composite score for ranking (lower is better)."""
    if not metrics:
        return float('inf')
    
    default_weights = {
        'cruise_rms_err_deg': 10.0,
        'max_track_err_deg': 5.0,
        'final_err_deg': 5.0,
        'overshoot_deg': 3.0,
        'settle_ms': 0.01,
        'residual_vibration_pp_deg': 2.0,
        'regressive_reversals': 10.0,
        'duty_saturation_frac': 5.0,
        'duty_smoothness': -1.0,  # negative weight = higher is better
        'current_rms_A': 1.0,
        'energy_proxy': 0.01,
    }
    
    if weights:
        default_weights.update(weights)
    
    score = 0.0
    for key, weight in default_weights.items():
        val = metrics.get(key, 0)
        if weight >= 0:
            score += weight * val
        else:
            score -= weight * val  # negative weight means we want to maximize
    
    return score


# ─────────────────────────────────────────────────────────────────────────────
# Simulation Worker (runs in separate process)
# ─────────────────────────────────────────────────────────────────────────────

def run_simulation_worker(args: tuple) -> dict:
    """Worker function for parallel simulation."""
    (config_dict, sweep_config) = args
    
    # Import here to avoid multiprocessing issues
    sys.path.insert(0, str(Path(__file__).parent))
    from simulate_motor import Simulator, TrajectoryType
    
    sim = Simulator(sweep_config.motor, sweep_config.models_json)
    
    # Set gains
    sim.set_gains(
        kp_pos=config_dict.get('kp_pos', 2.0e-4),
        ki_pos=config_dict.get('ki_pos', 8.0e-7),
        kp_vel=config_dict.get('kp_vel', 1.0e-6),
        kd_vel=config_dict.get('kd_vel', 0.0),
        kff_accel=config_dict.get('kff_accel', 0.0),
        endpoint_kp_vel=config_dict.get('endpoint_kp_vel', 0.0),
        vbus_comp=config_dict.get('vbus_comp', 7400.0),
        i_limit=config_dict.get('i_limit', 0.20),
        deadzone_mdeg=config_dict.get('deadzone', 400.0),
        min_duty=config_dict.get('min_duty', 0.12),
        start_duty=config_dict.get('start_duty', 0.12),
        startup_release_speed_mdegs=config_dict.get('startup_release_speed_mdegs', 0.0),
        startup_ramp_ticks=config_dict.get('startup_ramp_ticks', 200),
        restart_ramp_ticks=config_dict.get('restart_ramp_ticks', 200),
        startup_pulse_on_ticks=config_dict.get('startup_pulse_on_ticks', 4),
        vel_window=config_dict.get('vel_window', 40)
    )
    
    # Feedforward
    sim.ff_on = config_dict.get('ff_on', True)
    sim.friction_feedforward_permille = config_dict.get('friction_permille', 500)
    
    # Battery
    sim.vbus_mv = sweep_config.battery_mv
    
    # Trajectory
    traj_type = TrajectoryType.TRAPEZOID if config_dict.get('trajectory_type', 0) == 0 else TrajectoryType.MINIMUM_JERK
    vel_scale = config_dict.get('vel_scale', 1.0)
    accel_scale = config_dict.get('accel_scale', 1.0)
    
    sim.set_trajectory(
        target_deg=sweep_config.target_deg,
        max_vel_degs=sweep_config.max_vel_degs,
        max_accel_degs2=sweep_config.max_accel_degs2,
        trajectory_type=traj_type,
        vel_scale=vel_scale,
        accel_scale=accel_scale,
        auto_coast_ms=0
    )
    
    sim.arm_trace()
    
    # Run simulation
    sim.run(sweep_config.duration_s)
    
    # Convert trace to dict format
    trace_dicts = []
    for r in sim.trace:
        trace_dicts.append({
            't_ms': r.t_ms,
            'ref_mdeg': r.ref_mdeg,
            'enc_mdeg': r.enc_mdeg,
            'hat_mdeg': r.hat_mdeg,
            'vref_mdegs': r.vref_mdegs,
            'what_mdegs': r.what_mdegs,
            'duty_milli': r.duty_milli,
            'cur_01ma': r.cur_01ma
        })
    
    # Compute metrics
    metrics = compute_metrics(trace_dicts)
    config_dict['score'] = score_config(metrics)
    config_dict['metrics'] = metrics
    config_dict['trace_rows'] = len(sim.trace)
    
    return config_dict


# ─────────────────────────────────────────────────────────────────────────────
# Sweep Generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_configs(sweep_config: SweepConfig, gain_spaces: dict) -> list[dict]:
    """Generate parameter configurations for sweeping using efficient sampling."""
    motor_spaces = gain_spaces.get(sweep_config.motor, gain_spaces['EV3_Medium'])
    
    # Base config
    base_config = {
        'motor': sweep_config.motor,
        'target_deg': sweep_config.target_deg,
        'max_vel_degs': sweep_config.max_vel_degs,
        'max_accel_degs2': sweep_config.max_accel_degs2,
        'duration_s': sweep_config.duration_s,
        'battery_mv': sweep_config.battery_mv,
        'ff_on': True,
        'trajectory_type': 0,
        'vel_scale': 1.0,
        'accel_scale': 1.0,
    }
    
    # Parameter names in order
    param_names = list(motor_spaces.keys())
    param_names += ['vel_scale', 'accel_scale', 'trajectory_type', 'friction_permille']
    
    # Generate values for each parameter (use only first few for grid, rest random)
    param_ranges = {}
    for name in motor_spaces:
        param_ranges[name] = motor_spaces[name].generate()
    param_ranges['vel_scale'] = TRAJECTORY_SPACES['vel_scale'].generate()
    param_ranges['accel_scale'] = TRAJECTORY_SPACES['accel_scale'].generate()
    param_ranges['trajectory_type'] = TRAJECTORY_SPACES['trajectory_type']
    param_ranges['friction_permille'] = FF_SPACES['friction_permille'].generate()
    
    # Use random sampling to avoid massive cartesian product
    import random
    random.seed(sweep_config.seed)
    
    configs = []
    for _ in range(sweep_config.max_configs):
        config = base_config.copy()
        for name in param_names:
            config[name] = random.choice(param_ranges[name])
        configs.append(config)
    
    return configs


# ─────────────────────────────────────────────────────────────────────────────
# Main Sweep Orchestration
# ─────────────────────────────────────────────────────────────────────────────

def run_sweep(sweep_config: SweepConfig, gain_spaces: dict) -> list[dict]:
    """Run the full parameter sweep."""
    print(f"Generating configurations for {sweep_config.motor}...")
    configs = generate_configs(sweep_config, gain_spaces)
    print(f"Total configs: {len(configs)}")
    
    # Prepare worker args
    worker_args = [(config, sweep_config) for config in configs]
    
    # Determine workers
    num_workers = sweep_config.num_workers if sweep_config.num_workers > 0 else cpu_count()
    print(f"Running on {num_workers} workers...")
    
    results = []
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(run_simulation_worker, args): args[0] for args in worker_args}
        
        for i, future in enumerate(as_completed(futures)):
            try:
                result = future.result(timeout=60)
                results.append(result)
            except Exception as e:
                print(f"Config {i} failed: {e}")
                results.append({'error': str(e), **futures[future]})
            
            if (i + 1) % 50 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                print(f"  Completed {i+1}/{len(configs)} ({rate:.1f} configs/s)")
    
    elapsed = time.time() - start_time
    print(f"Sweep completed in {elapsed:.1f}s ({len(results)} results)")
    
    # Sort by score (lower is better)
    results.sort(key=lambda x: x.get('score', float('inf')))
    
    return results


def save_results(results: list[dict], output_dir: str, sweep_config: SweepConfig):
    """Save sweep results to CSV and JSON."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    base_name = f"sweep_{sweep_config.motor}_{timestamp}"
    
    # CSV summary
    csv_path = Path(output_dir) / f"{base_name}.csv"
    if results:
        # Flatten metrics for CSV
        fieldnames = ['score', 'trace_rows']
        for key in results[0].keys():
            if key not in ['metrics', 'score', 'trace_rows']:
                fieldnames.append(key)
        
        # Add metric fields
        if 'metrics' in results[0] and results[0]['metrics']:
            for mkey in results[0]['metrics'].keys():
                fieldnames.append(f"m_{mkey}")
        
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                row = {k: v for k, v in r.items() if k != 'metrics'}
                if 'metrics' in r and r['metrics']:
                    for mkey, mval in r['metrics'].items():
                        row[f"m_{mkey}"] = mval
                writer.writerow(row)
    
    # JSON full results
    json_path = Path(output_dir) / f"{base_name}.json"
    with open(json_path, 'w') as f:
        json.dump({
            'sweep_config': sweep_config.__dict__,
            'timestamp': timestamp,
            'num_configs': len(results),
            'results': results
        }, f, indent=2)
    
    # Top-N candidates for hardware validation
    top_n = 10
    candidates_path = Path(output_dir) / f"{base_name}_top{top_n}.json"
    with open(candidates_path, 'w') as f:
        json.dump(results[:top_n], f, indent=2)
    
    # CMD format for tune_session.py
    cmd_path = Path(output_dir) / f"{base_name}_cmd.txt"
    with open(cmd_path, 'w') as f:
        for i, r in enumerate(results[:top_n]):
            f.write(f"# Candidate {i+1} (score={r.get('score', 'N/A'):.3f})\n")
            f.write(f"G {r.get('kp_pos', 0):.6g} {r.get('ki_pos', 0):.6g} "
                   f"{r.get('kp_vel', 0):.6g} {r.get('kd_vel', 0):.6g} "
                   f"{r.get('kff_accel', 0):.6g}\n")
            f.write(f"S {r.get('start_duty', 0):.3f} {r.get('min_duty', 0):.3f}\n")
            f.write(f"W {r.get('vel_window', 40)}\n")
            f.write(f"D 0 100\n")  # Dump trace
            f.write(f"c\n")  # Coast
            f.write("\n")
    
    print(f"Results saved:")
    print(f"  CSV: {csv_path}")
    print(f"  JSON: {json_path}")
    print(f"  Top-{top_n}: {candidates_path}")
    print(f"  CMD: {cmd_path}")
    
    return csv_path, json_path, candidates_path, cmd_path


def print_top_results(results: list[dict], top_n: int = 10):
    """Print top N results."""
    print(f"\n=== Top {top_n} Results ===")
    for i, r in enumerate(results[:top_n]):
        m = r.get('metrics', {})
        print(f"\n#{i+1} score={r.get('score', 'N/A'):.3f}")
        print(f"  Gains: kp_pos={r.get('kp_pos', 0):.2e} ki_pos={r.get('ki_pos', 0):.2e} "
              f"kp_vel={r.get('kp_vel', 0):.2e} kd_vel={r.get('kd_vel', 0):.2e} "
              f"kff={r.get('kff_accel', 0):.2e} ep_kv={r.get('endpoint_kp_vel', 0):.2e}")
        print(f"  Limits: i_lim={r.get('i_limit', 0):.3f} dz={r.get('deadzone', 0):.0f} "
              f"min_d={r.get('min_duty', 0):.3f} start_d={r.get('start_duty', 0):.3f} "
              f"win={r.get('vel_window', 40)}")
        print(f"  Traj: v_scale={r.get('vel_scale', 1.0):.2f} a_scale={r.get('accel_scale', 1.0):.2f} "
              f"type={'jerk' if r.get('trajectory_type', 0) else 'trap'} ff_pm={r.get('friction_permille', 500)}")
        print(f"  Metrics: cruise_rms={m.get('cruise_rms_err_deg', 0):.3f}° "
              f"max_err={m.get('max_track_err_deg', 0):.1f}° "
              f"final_err={m.get('final_err_deg', 0):.3f}° "
              f"overshoot={m.get('overshoot_deg', 0):.3f}° "
              f"settle={m.get('settle_ms', 0)}ms "
              f"vib={m.get('residual_vibration_pp_deg', 0):.3f}° "
              f"rev={m.get('regressive_reversals', 0)} "
              f"sat={m.get('duty_saturation_frac', 0):.2f} "
              f"smooth={m.get('duty_smoothness', 0):.3f}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='EVN ALPHA Batch Parameter Sweep')
    parser.add_argument('--motor', choices=['EV3_Large', 'EV3_Medium', 'NXT'],
                        default='EV3_Medium', help='Motor model')
    parser.add_argument('--target', type=float, default=360.0)
    parser.add_argument('--max-vel', type=float, default=1100.0)
    parser.add_argument('--max-accel', type=float, default=2000.0)
    parser.add_argument('--duration', type=float, default=3.0)
    parser.add_argument('--battery', type=int, default=7400)
    parser.add_argument('--output-dir', type=str, default='bench/results/sweeps')
    parser.add_argument('--workers', type=int, default=0, help='0=auto')
    parser.add_argument('--max-configs', type=int, default=500)
    parser.add_argument('--random', action='store_true', help='Random sampling')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--models-json', type=str, default='tools/motor_models.json')
    
    args = parser.parse_args()
    
    sweep_config = SweepConfig(
        motor=args.motor,
        target_deg=args.target,
        max_vel_degs=args.max_vel,
        max_accel_degs2=args.max_accel,
        duration_s=args.duration,
        battery_mv=args.battery,
        output_dir=args.output_dir,
        num_workers=args.workers,
        max_configs=args.max_configs,
        random_sample=args.random,
        seed=args.seed,
    )
    sweep_config.models_json = args.models_json
    
    # Load gain spaces (use defaults for now)
    gain_spaces = DEFAULT_GAIN_SPACES
    
    # Run sweep
    results = run_sweep(sweep_config, gain_spaces)
    
    # Save
    save_results(results, sweep_config.output_dir, sweep_config)
    
    # Print summary
    print_top_results(results, top_n=10)


if __name__ == '__main__':
    main()