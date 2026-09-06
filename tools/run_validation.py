#!/usr/bin/env python3
"""Run all 16 validation cases from autonomous_tuning.c"""

import subprocess
import sys

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

results = []
for motor, kp_pos, ki_pos, kp_vel, endpoint_kp_vel, accel_scale, start_duty, startup_ramp, restart_ramp, startup_pulse, target, max_vel, max_accel, name in cases:
    print(f'Running {name}...', end=' ', flush=True)
    
    # Run simulation
    vel_window = EV3_LARGE_VEL_WINDOW if motor == 'EV3_Large' else EV3_MEDIUM_VEL_WINDOW
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
        '--max-vel', str(max_vel),
        '--max-accel', str(max_accel),
        '--duration', '4',
        '--output', f'validation_{name}.txt',
        '--trace'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f'FAILED (sim): {result.stderr[:100]}')
        results.append((name, 'SIM_FAILED', None))
        continue
    
    # Run metrics
    cmd = [sys.executable, 'tools/motion_metrics.py', f'validation_{name}.txt']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f'FAILED (metrics): {result.stderr[:100]}')
        results.append((name, 'METRICS_FAILED', None))
        continue
    
    # Parse acceptance
    output = result.stdout
    if 'ACCEPTANCE:' in output:
        accept_line = [l for l in output.split('\n') if 'ACCEPTANCE:' in l][0]
        print(accept_line)
        results.append((name, 'PASS', accept_line))
    else:
        print('UNKNOWN')
        results.append((name, 'UNKNOWN', None))

print()
print('=== SUMMARY ===')
for name, status, accept in results:
    line = name + ': ' + status
    if accept:
        line += ' ' + accept
    print(line)

# Count passes
passed = sum(1 for _, status, _ in results if status == 'PASS')
print(f'\nTotal: {passed}/16 passed')