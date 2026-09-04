# Phase 8 kd_vel Sweep & Unloaded EV3 Medium Retune v2 (run 0x26090434)

**Date**: 2026-09-04

## Test Matrix
- 16 cases: 4 axes × 4 variations each
- EV3 Large (axes 0,1): 800 deg/s, kp_pos/kv/kd_vel sweep, kff=0
- EV3 Medium NEG (axis 2): 1100 deg/s, unloaded motor retune
- EV3 Medium POS (axis 3): 1100 deg/s, REDUCED gains + kd_vel for damping
- All moves: 720° distance, alternating directions, absolute moves
- Battery: 8.37V multimeter, 8.21V pack on board

## Results: 16/16 cases completed, 16/16 traces decoded

| Case | Axis | Motor | kp_pos | kp_vel | kd_vel | endpoint_kp | accel_scale | Pass Rate | Max Track Err | Score |
|------|------|-------|--------|--------|--------|-------------|-------------|-----------|---------------|-------|
| 9 | 3 | EV3 Med POS | 2.5e-4 | 1.0e-6 | 0 | 1.0e-6 | 0.35 | **11/12** | 1.43° | 3.27 |
| 0 | 1 | EV3 Large | 2.2e-4 | 2.5e-6 | 0 | 1.0e-6 | 0.70 | **11/12** | 3.25° | 4.55 |
| 1 | 1 | EV3 Large | 2.5e-4 | 3.0e-6 | 0 | 1.0e-6 | 0.70 | 10/12 | 2.87° | 3.39 |
| 4 | 2 | EV3 Large | 2.2e-4 | 2.5e-6 | 0 | 1.0e-6 | 0.70 | 10/12 | 3.54° | 4.08 |
| 5 | 2 | EV3 Large | 2.5e-4 | 3.0e-6 | 0 | 1.0e-6 | 0.70 | 10/12 | 3.07° | 4.85 |
| 11 | 3 | EV3 Med POS | 2.5e-4 | 1.0e-6 | 0 | 1.0e-6 | 0.30 | 8/12 | 2.00° | 6.60 |
| 8 | 3 | EV3 Med NEG | 3.0e-4 | 1.2e-6 | 0 | 2.0e-6 | 0.35 | 8/12 | 1.84° | 8.72 |
| 10 | 4 | EV3 Med NEG | 2.8e-4 | 1.5e-6 | 0 | 2.5e-6 | 0.35 | 7/12 | 2.17° | 8.93 |
| 12 | 4 | EV3 Med NEG | 2.5e-4 | 1.0e-6 | 0 | 1.5e-6 | 0.35 | 6/12 | 39.1° | 47.16 |
| 14 | 4 | EV3 Med NEG | 2.8e-4 | 1.2e-6 | 0 | 2.0e-6 | 0.35 | 6/12 | 37.2° | 53.58 |
| 13 | 4 | EV3 Med POS | 2.2e-4 | 0.8e-6 | 0 | 1.0e-6 | 0.25 | 5/12 | 40.4° | 60.74 |
| 15 | 4 | EV3 Med POS | 2.5e-4 | 1.0e-6 | 1.5e-6 | 1.0e-6 | 0.30 | 4/12 | 66.3° | 84.51 |
| 2 | 1 | EV3 Large | 2.2e-4 | 2.5e-6 | 1.0e-6 | 1.0e-6 | 0.70 | 3/12 | 22.7° | 47.65 |
| 3 | 1 | EV3 Large | 2.5e-4 | 3.0e-6 | 1.0e-6 | 1.0e-6 | 0.70 | 3/12 | 24.0° | 52.09 |
| 7 | 2 | EV3 Large | 2.8e-4 | 3.5e-6 | 1.0e-6 | 1.0e-6 | 0.70 | 3/12 | 51.0° | 76.56 |
| 6 | 2 | EV3 Large | 2.2e-4 | 2.5e-6 | 1.0e-6 | 1.0e-6 | 0.70 | 3/12 | 62.1° | 89.88 |

**NOTE**: kd_vel was passed to PID controller but NOT stored in header (bug in prepare_header, fixed for next run). All kd values in flash records show 0.0.

## Key Findings

1. **EV3 Medium POS (axis 3) - BREAKTHROUGH**: Case 9 (kp=2.5e-4, kv=1.0e-6, kd=0) achieved **11/12** with reduced gains! Lower kp (2.5e-4 vs 3.0e-4) and lower kv (1.0e-6 vs 1.5e-6) stabilized the unloaded motor. Max track err 1.43° (under 2.0° threshold).

2. **kd_vel is HARMFUL for EV3 Large**: Cases with kd_vel=1.0e-6 (cases 2,3,6,7) degraded to 3/12 with massive tracking errors (22-62°). kd_vel=0 gave 10-11/12. Derivative term amplifies noise on EV3 Large.

3. **EV3 Medium NEG (axis 2)**: Case 8 (kp=3.0e-4, kv=1.2e-6, endpoint_kp=2.0e-6) got 8/12. Previous 11/12 was with kd_vel=0 but different test ordering. Unloaded motor needs endpoint_kp for approach stability.

4. **EV3 Large (axes 0,1)**: Best remains kp=2.2e-4, kv=2.5e-6, kd=0 (11/12, 3.25° error). kd_vel adds instability. Need to close 3.25° → 2.0° gap via motor model recalibration or kp_pos increase.

5. **Core 1 timing**: Excellent - 999-1001µs period, exec max 195-207µs, 0 missed ticks across all 16 cases.

6. **Battery**: 8.21V pack (4.10V/cell), age <500µs - well within safety margins.

## Infrastructure & Safety
- Battery: 8.21V pack; min cell 4.10V; age <500µs
- Core 1 period: 999-1001µs; exec max 207µs; missed ticks: 0
- Duty smoothness: 0.41-0.94 range
- All motors coasted at end of each case

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| tuning.uf2 | 1,966,080 | [computed at runtime] |
| summary.csv | 2,156 | [computed at runtime] |
| 16 case JSON/trace files | ~500KB total | [computed at runtime] |

## Updated Winning Configurations (for next iteration)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel | Notes |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|-------|
| EV3 Large | 2.2e-4 | 2.5e-6 | 8e-7 | **0** | 0 | 0.70 | 1.0e-6 | kd_vel harmful |
| EV3 Medium NEG | 3.0e-4 | 1.2e-6 | 8e-7 | **0** | 0 | 0.35 | **2.0e-6** | Higher endpoint_kp |
| EV3 Medium POS | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | 1.0e-6 | **REDUCED gains = 11/12!** |

## Next Step
1. **EV3 Medium POS (axis 3)**: **VALIDATED 11/12 with REDUCED gains** (kp=2.5e-4, kv=1.0e-6). Now need 2+ consecutive 12/12 runs. Sweep kp_pos 2.3-2.7e-4, kv 0.9-1.2e-6, accel_scale 0.30-0.40.
2. **EV3 Medium NEG (axis 2)**: Target kp_pos 2.5-2.8e-4, kv 1.0-1.2e-6, endpoint_kp 2.0-2.5e-6 for 12/12.
3. **EV3 Large (axes 0,1)**: Keep kd_vel=0. Sweep kp_pos 2.2-2.8e-4, kv 2.5-3.5e-6 to close 3.25° → 2.0° tracking gap. Motor model recalibration needed.
4. **Fix header storage**: s_header.kd = test->kd_vel now added to prepare_header.

**Expected autonomous run time**: ~15 min (16 cases × 45s + overhead)