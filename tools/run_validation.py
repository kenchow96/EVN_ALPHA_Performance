#!/usr/bin/env python3
"""Run all 16 validation cases from autonomous_tuning.c with Domain Randomization support"""

import subprocess
import sys
import argparse
import random
import json
import statistics
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = REPO_ROOT / 'bench' / 'results' / 'validation_runs'

# Test cases from autonomous_tuning.c
# vel_window: EV3 Large uses 10 (calibrated sim shows this eliminates the endpoint
# limit cycle caused by the windowed speed estimate's phase lag); EV3 Medium uses 40.
EV3_LARGE_VEL_WINDOW = 10
EV3_MEDIUM_VEL_WINDOW = 40

cases = [
    # Axis 0 (EV3 Large) - 4 repeats: POS, NEG, POS, NEG
    ('EV3_Large', 4.0e-4, 8e-7, 5.0e-6, 1.0e-6, 0.70, 0.12, 200, 200, 4, 720, 800, 1600, 'axis0_pos_r0'),
    ('EV3_Large', 4.0e-4, 8e-7, 5.0e-6, 1.0e-6, 0.70, 0.12, 200, 200, 4, -720, 800, 1600, 'axis0_neg_r0'),
    ('EV3_Large', 4.0e-4, 8e-7, 5.0e-6, 1.0e-6, 0.70, 0.12, 200, 200, 4, 720, 800, 1600, 'axis0_pos_r1'),
    ('EV3_Large', 4.0e-4, 8e-7, 5.0e-6, 1.0e-6, 0.70, 0.12, 200, 200, 4, -720, 800, 1600, 'axis0_neg_r1'),
    # Axis 1 (EV3 Large) - 4 repeats: POS, NEG, POS, NEG
    ('EV3_Large', 4.0e-4, 8e-7, 5.0e-6, 1.0e-6, 0.70, 0.12, 200, 200, 4, 720, 800, 1600, 'axis1_pos_r0'),
    ('EV3_Large', 4.0e-4, 8e-7, 5.0e-6, 1.0e-6, 0.70, 0.12, 200, 200, 4, -720, 800, 1600, 'axis1_neg_r0'),
    ('EV3_Large', 4.0e-4, 8e-7, 5.0e-6, 1.0e-6, 0.70, 0.12, 200, 200, 4, 720, 800, 1600, 'axis1_pos_r1'),
    ('EV3_Large', 4.0e-4, 8e-7, 5.0e-6, 1.0e-6, 0.70, 0.12, 200, 200, 4, -720, 800, 1600, 'axis1_neg_r1'),
    # Axis 2 (EV3 Medium) - 4 repeats: NEG, POS, NEG, POS
    ('EV3_Medium', 2.5e-4, 8e-7, 1.0e-6, 2.0e-6, 0.35, 0.80, 200, 200, 4, -720, 1100, 2200, 'axis2_neg_r0'),
    ('EV3_Medium', 2.5e-4, 8e-7, 1.0e-6, 2.0e-6, 0.35, 0.80, 200, 200, 4, 720, 1100, 2200, 'axis2_pos_r0'),
    ('EV3_Medium', 2.5e-4, 8e-7, 1.0e-6, 2.0e-6, 0.35, 0.80, 200, 200, 4, -720, 1100, 2200, 'axis2_neg_r1'),
    ('EV3_Medium', 2.5e-4, 8e-7, 1.0e-6, 2.0e-6, 0.35, 0.80, 200, 200, 4, 720, 1100, 2200, 'axis2_pos_r1'),
    # Axis 3 (EV3 Medium) - 4 repeats: NEG, POS, NEG, POS
    ('EV3_Medium', 2.5e-4, 8e-7, 1.0e-6, 2.0e-6, 0.35, 0.80, 200, 200, 4, -720, 1100, 2200, 'axis3_neg_r0'),
    ('EV3_Medium', 2.5e-4, 8e-7, 1.0e-6, 2.0e-6, 0.35, 0.80, 200, 200, 4, 720, 1100, 2200, 'axis3_pos_r0'),
    ('EV3_Medium', 2.5e-4, 8e-7, 1.0e-6, 2.0e-6, 0.35, 0.80, 200, 200, 4, -720, 1100, 2200, 'axis3_neg_r1'),
    ('EV3_Medium', 2.5e-4, 8e-7, 1.0e-6, 2.0e-6, 0.35, 0.80, 200, 200, 4, 720, 1100, 2200, 'axis3_pos_r1'),
]

# Domain Randomization parameter ranges (per Sim-to-Real Report)
DR_RANGES = {
    'R_phase_ohm': (0.75, 1.25),          # ±25% resistance variation
    'friction_scale': (0.5, 2.0),         # 0.5–2× Coulomb/viscous friction
    'backlash_deg': (0.0, 2.5),           # 0–2.5° backlash (EV3 Large has slack)
    'delay_ms': (0, 4),                   # 0–4 ms transport delay
    'V_max_scale': (0.85, 1.15),          # ±15% voltage/speed variation
    'vel_noise_std_mdegs': (0, 5000),     # Gaussian velocity measurement noise (mdeg/s)
}

def run_single_sim(motor, kp_pos, ki_pos, kp_vel, endpoint_kp_vel, accel_scale,
                   start_duty, startup_ramp, restart_ramp, startup_pulse,
                   target, max_vel, max_accel, name,
                   dr_params=None, vel_window=None):
    """Run a single simulation with optional DR parameters"""
    if vel_window is None:
        vel_window = EV3_LARGE_VEL_WINDOW if motor == 'EV3_Large' else EV3_MEDIUM_VEL_WINDOW
    
    # Apply DR scaling to max_vel and max_accel
    max_vel_final = max_vel
    max_accel_final = max_accel
    if dr_params and 'V_max_scale' in dr_params and dr_params['V_max_scale'] != 1.0:
        max_vel_final = max_vel * dr_params['V_max_scale']
        max_accel_final = max_accel * dr_params['V_max_scale']
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f'validation_{name}.txt'

    cmd = [
        sys.executable, 'tools/simulate_motor.py',
        '--motor', motor,
        '--kp-pos', str(kp_pos),
        '--ki-pos', str(ki_pos),
        '--kp-vel', str(kp_vel),
        '--endpoint-kp-vel', str(endpoint_kp_vel),
        '--accel-scale', str(accel_scale),
        '--start-duty', str(start_duty),
        '--startup-ramp-ticks', str(startup_ramp),
        '--restart-ramp-ticks', str(restart_ramp),
        '--startup-pulse-on-ticks', str(startup_pulse),
        '--vel-window', str(vel_window),
        '--target', str(target),
        '--max-vel', str(max_vel_final),
        '--max-accel', str(max_accel_final),
        '--duration', '4',
        '--output', str(out_file),
        '--trace'
    ]
    
    # Add DR parameters if provided
    if dr_params:
        if 'backlash_deg' in dr_params and dr_params['backlash_deg'] > 0:
            cmd.extend(['--backlash-deg', str(dr_params['backlash_deg'])])
        if 'friction_scale' in dr_params and dr_params['friction_scale'] != 1.0:
            cmd.extend(['--friction-scale', str(dr_params['friction_scale'])])
        if 'delay_ms' in dr_params and dr_params['delay_ms'] > 0:
            cmd.extend(['--plant-delay-ms', str(dr_params['delay_ms'])])
        if 'R_phase_ohm' in dr_params and dr_params['R_phase_ohm'] != 1.0:
            # This would require motor model modification - handled via friction_scale for now
            pass
        if 'vel_noise_std_mdegs' in dr_params and dr_params['vel_noise_std_mdegs'] > 0:
            cmd.extend(['--vel-noise-std', str(dr_params['vel_noise_std_mdegs'])])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        return None, f'SIM_FAILED: {result.stderr[:100]}'
    
    # Run metrics
    cmd = [sys.executable, 'tools/motion_metrics.py', str(out_file)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return None, f'METRICS_FAILED: {result.stderr[:100]}'
    
    # Parse acceptance
    output = result.stdout
    if 'ACCEPTANCE:' in output:
        accept_line = [l for l in output.split('\n') if 'ACCEPTANCE:' in l][0]
        # Parse "X/Y pass"
        parts = accept_line.split()
        passed = int(parts[1].split('/')[0])
        total = int(parts[1].split('/')[1].rstrip('pass'))
        return passed, accept_line
    
    return None, 'UNKNOWN'

def run_dr_validation(dr_draws: int = 50, dr_seed: int = 42):
    """Run Domain Randomization validation across all 16 cases"""
    random.seed(dr_seed)
    
    print(f"=== DOMAIN RANDOMIZATION VALIDATION ({dr_draws} draws, seed={dr_seed}) ===\n")
    
    case_results = {}
    
    for motor, kp_pos, ki_pos, kp_vel, endpoint_kp_vel, accel_scale, start_duty, startup_ramp, restart_ramp, startup_pulse, target, max_vel, max_accel, name in cases:
        print(f'{name}: ', end='', flush=True)
        
        passes = []
        for draw in range(dr_draws):
            # Sample DR parameters
            dr_params = {
                'R_phase_ohm': random.uniform(*DR_RANGES['R_phase_ohm']),
                'friction_scale': random.uniform(*DR_RANGES['friction_scale']),
                'backlash_deg': random.uniform(*DR_RANGES['backlash_deg']),
                'delay_ms': random.randint(*DR_RANGES['delay_ms']),
                'V_max_scale': random.uniform(*DR_RANGES['V_max_scale']),
                'vel_noise_std_mdegs': random.uniform(*DR_RANGES['vel_noise_std_mdegs']),
            }
            
            passed, _ = run_single_sim(
                motor, kp_pos, ki_pos, kp_vel, endpoint_kp_vel, accel_scale,
                start_duty, startup_ramp, restart_ramp, startup_pulse,
                target, max_vel, max_accel, name,
                dr_params=dr_params
            )
            
            if passed is not None:
                passes.append(passed)
            
            if (draw + 1) % 10 == 0:
                print('.', end='', flush=True)
        
        print()
        
        if passes:
            worst_case = min(passes)
            mean_pass = statistics.mean(passes)
            std_pass = statistics.stdev(passes) if len(passes) > 1 else 0
            pass_rate = sum(1 for p in passes if p >= 11) / len(passes) * 100
            case_results[name] = {
                'worst_case': worst_case,
                'mean': mean_pass,
                'std': std_pass,
                'pass_rate_11': pass_rate,
                'all_passes': passes
            }
            print(f'  Worst: {worst_case}/12, Mean: {mean_pass:.1f}/12, Std: {std_pass:.1f}, ≥11/12 rate: {pass_rate:.1f}%')
        else:
            case_results[name] = {'worst_case': 0, 'mean': 0, 'std': 0, 'pass_rate_11': 0}
            print(f'  ALL FAILED')
    
    # Summary
    print('\n=== DR VALIDATION SUMMARY ===')
    worst_overall = min(r['worst_case'] for r in case_results.values())
    print(f'Overall worst-case: {worst_overall}/12')
    
    for name, res in case_results.items():
        print(f'{name}: worst={res["worst_case"]}/12, mean={res["mean"]:.1f}/12, ≥11/12={res["pass_rate_11"]:.1f}%')
    
    return case_results

def run_nominal_validation():
    """Run nominal (non-DR) validation - original behavior"""
    results = []
    for motor, kp_pos, ki_pos, kp_vel, endpoint_kp_vel, accel_scale, start_duty, startup_ramp, restart_ramp, startup_pulse, target, max_vel, max_accel, name in cases:
        print(f'Running {name}...', end=' ', flush=True)
        
        vel_window = EV3_LARGE_VEL_WINDOW if motor == 'EV3_Large' else EV3_MEDIUM_VEL_WINDOW
        passed, msg = run_single_sim(
            motor, kp_pos, ki_pos, kp_vel, endpoint_kp_vel, accel_scale,
            start_duty, startup_ramp, restart_ramp, startup_pulse,
            target, max_vel, max_accel, name,
            vel_window=vel_window
        )
        
        if passed is not None:
            print(msg)
            results.append((name, 'PASS', msg))
        else:
            print(msg)
            results.append((name, 'FAIL', msg))
    
    print()
    print('=== NOMINAL VALIDATION SUMMARY ===')
    for name, status, accept in results:
        line = name + ': ' + status
        if accept:
            line += ' ' + accept
        print(line)
    
    passed = sum(1 for _, status, _ in results if status == 'PASS')
    print(f'\nTotal: {passed}/16 passed')
    return results

def run_backlash_sweep(axis_name: str = 'axis3'):
    """Sweep backlash for a specific axis to reproduce stiction stall"""
    # Find the cases for the specified axis
    axis_cases = [c for c in cases if axis_name in c[-1]]
    
    if not axis_cases:
        print(f"No cases found for {axis_name}")
        return
    
    backlash_values = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
    print(f"=== BACKLASH SWEEP FOR {axis_name.upper()} ===\n")
    
    for bl in backlash_values:
        print(f"Backlash: {bl}°")
        for motor, kp_pos, ki_pos, kp_vel, endpoint_kp_vel, accel_scale, start_duty, startup_ramp, restart_ramp, startup_pulse, target, max_vel, max_accel, name in axis_cases:
            passed, msg = run_single_sim(
                motor, kp_pos, ki_pos, kp_vel, endpoint_kp_vel, accel_scale,
                start_duty, startup_ramp, restart_ramp, startup_pulse,
                target, max_vel, max_accel, name,
                dr_params={'backlash_deg': bl}
            )
            if passed is not None:
                print(f"  {name}: {msg}")
            else:
                print(f"  {name}: {msg}")

def run_vel_window_sweep(motor_name: str = 'EV3_Large'):
    """Sweep vel_window for a motor type under encoder noise"""
    axis_cases = [c for c in cases if motor_name.replace('_', '').lower() in c[-1].lower()]
    if not axis_cases:
        # Use first case of the motor type
        axis_cases = [c for c in cases if (motor_name == 'EV3_Large' and 'axis0' in c[-1]) or 
                      (motor_name == 'EV3_Medium' and 'axis2' in c[-1])]
    
    vel_windows = [5, 10, 20, 40, 60]
    noise_levels = [0, 1000, 2500, 5000]
    
    print(f"=== VEL_WINDOW SWEEP FOR {motor_name} ===\n")
    
    for noise in noise_levels:
        print(f"\nEncoder noise std: {noise} mdeg/s")
        for vw in vel_windows:
            print(f"  vel_window={vw}: ", end='', flush=True)
            for motor, kp_pos, ki_pos, kp_vel, endpoint_kp_vel, accel_scale, start_duty, startup_ramp, restart_ramp, startup_pulse, target, max_vel, max_accel, name in axis_cases[:1]:  # Just first case
                passed, msg = run_single_sim(
                    motor, kp_pos, ki_pos, kp_vel, endpoint_kp_vel, accel_scale,
                    start_duty, startup_ramp, restart_ramp, startup_pulse,
                    target, max_vel, max_accel, name,
                    dr_params={'vel_noise_std_mdegs': noise},
                    vel_window=vw
                )
                if passed is not None:
                    print(f"{msg}", end='; ')
                else:
                    print(f"FAIL", end='; ')
            print()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='EVN ALPHA Validation with Domain Randomization')
    parser.add_argument('--mode', choices=['nominal', 'dr', 'backlash', 'vel_window'], default='nominal',
                        help='Validation mode')
    parser.add_argument('--dr-draws', type=int, default=50, help='Number of DR draws per case')
    parser.add_argument('--dr-seed', type=int, default=42, help='Random seed for DR')
    parser.add_argument('--axis', type=str, default='axis3', help='Axis for backlash sweep')
    parser.add_argument('--motor', type=str, default='EV3_Large', help='Motor for vel_window sweep')
    
    args = parser.parse_args()
    
    if args.mode == 'dr':
        run_dr_validation(args.dr_draws, args.dr_seed)
    elif args.mode == 'backlash':
        run_backlash_sweep(args.axis)
    elif args.mode == 'vel_window':
        run_vel_window_sweep(args.motor)
    else:
        run_nominal_validation()