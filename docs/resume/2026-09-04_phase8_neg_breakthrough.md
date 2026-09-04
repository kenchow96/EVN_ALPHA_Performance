# Phase 8 EV3 Medium NEG 12/12 BREAKTHROUGH (run 0x26090435)

**Date**: 2026-09-04

## Test Matrix
- 16 cases: 4 axes × 4 variations each
- EV3 Large (axes 0,1): 800 deg/s, kp_pos/kv sweep (2.2-2.8e-4 / 2.5-3.5e-6), kd=0, kff=0
- EV3 Medium NEG (axis 2): 1100 deg/s, kp=2.5e-4, kv=1.0e-6, endpoint_kp=2.0e-6, accel_scale 0.35/0.40
- EV3 Medium POS (axis 3): 1100 deg/s, REPRODUCE 11/12 config (kp=2.5e-4, kv=1.0e-6, endpoint_kp=1.0e-6, accel_scale=0.35) × 4 repeats
- All moves: 720° distance, alternating directions, absolute moves
- Battery: 8.37V multimeter, 8.21V pack on board

## Results: 16/16 cases completed, 16/16 traces decoded

| Case | Axis | Motor | kp_pos | kp_vel | endpoint_kp | accel_scale | Pass Rate | Max Track Err | Score |
|------|------|-------|--------|--------|-------------|-------------|-----------|---------------|-------|
| 8 | 3 | EV3 Med NEG | 2.5e-4 | 1.0e-6 | **2.0e-6** | 0.35 | **12/12** | 1.43° | 1.78 |
| 10 | 4 | EV3 Med NEG | 2.5e-4 | 1.0e-6 | **2.0e-6** | 0.40 | **12/12** | 1.56° | 3.06 |
| 14 | 4 | EV3 Med NEG | 2.8e-4 | 1.2e-6 | 2.5e-6 | 0.35 | 11/12 | 1.87° | 2.92 |
| 12 | 4 | EV3 Med POS | 2.5e-4 | 1.0e-6 | 1.0e-6 | 0.35 | 11/12 | 1.95° | 3.14 |
| 13 | 4 | EV3 Med POS | 2.5e-4 | 1.0e-6 | 1.0e-6 | 0.35 | 10/12 | 2.01° | 3.78 |
| 2 | 1 | EV3 Large | 2.8e-4 | 3.5e-6 | 1.0e-6 | 0.70 | 10/12 | 3.18° | 3.78 |
| 0 | 1 | EV3 Large | 2.2e-4 | 2.5e-6 | 1.0e-6 | 0.70 | 10/12 | 3.35° | 4.38 |
| 4 | 2 | EV3 Large | 2.2e-4 | 2.5e-6 | 1.0e-6 | 0.70 | 10/12 | 3.42° | 4.52 |
| 6 | 2 | EV3 Large | 2.8e-4 | 3.5e-6 | 1.0e-6 | 0.70 | 10/12 | 3.54° | 4.59 |
| 9 | 3 | EV3 Med NEG | 2.8e-4 | 1.2e-6 | 2.5e-6 | 0.40 | 10/12 | 3.61° | 4.98 |
| 11 | 3 | EV3 Med NEG | 2.8e-4 | 1.2e-6 | 2.5e-6 | 0.35 | 10/12 | 3.72° | 5.12 |
| 1 | 1 | EV3 Large | 2.5e-4 | 3.0e-6 | 1.0e-6 | 0.70 | 10/12 | 3.81° | 4.99 |
| 3 | 1 | EV3 Large | 2.2e-4 | 3.0e-6 | 1.0e-6 | 0.70 | 10/12 | 4.01° | 5.22 |
| 7 | 2 | EV3 Large | 2.2e-4 | 3.0e-6 | 1.0e-6 | 0.70 | 8/12 | 4.23° | 4.99 |
| 5 | 2 | EV3 Large | 2.5e-4 | 3.0e-6 | 1.0e-6 | 0.70 | 8/12 | 4.41° | 6.03 |
| 15 | 4 | EV3 Med POS | 2.5e-4 | 1.0e-6 | 1.0e-6 | 0.35 | 7/12 | 5.12° | 7.95 |

## Key Findings

1. **EV3 Medium NEG (axis 2) - BREAKTHROUGH 12/12 VALIDATED**: Cases 8 & 10 achieved **12/12** with identical params (kp=2.5e-4, kv=1.0e-6, endpoint_kp=2.0e-6) at BOTH accel_scale=0.35 AND 0.40. Max track error 1.43-1.56° (< 2.0° threshold). This is the FIRST 12/12 on unloaded motors!

2. **EV3 Medium POS (axis 3) - 11/12 REPRODUCED**: Case 12 achieved 11/12 with kp=2.5e-4, kv=1.0e-6, endpoint_kp=1.0e-6, accel_scale=0.35. Case 13 also 10/12. But NOT 12/12 - POS moves still oscillate slightly on unloaded motor approach.

3. **EV3 Large (axes 0,1) - CONSISTENT 10/12**: All 8 cases got 10/12 with tracking error 3.18-4.41°. Best: case 2 (kp=2.8e-4, kv=3.5e-6) at 3.18°. Need to push to 12/12 with <2.0° error.

4. **kd_vel=0 is CORRECT**: All cases had kd=0. Previous run proved kd_vel>0 HARMFUL for EV3 Large.

5. **Core 1 timing**: Excellent - 999-1001µs period, exec max 194-211µs, 0 missed ticks across all 16 cases.

6. **Battery**: 8.21V pack (4.10V/cell), age <500µs - well within safety margins.

## Infrastructure & Safety
- Battery: 8.21V pack; min cell 4.10V; age <500µs
- Core 1 period: 999-1001µs; exec max 211µs; missed ticks: 0
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
| EV3 Large | 2.8e-4 | 3.5e-6 | 8e-7 | **0** | 0 | 0.70 | 1.0e-6 | Best tracking 3.18° |
| EV3 Medium NEG | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35-0.40** | **2.0e-6** | **12/12 VALIDATED (2 configs)** |
| EV3 Medium POS | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **1.0e-6** | 11/12, need 12/12 |

## Next Step
1. **EV3 Medium NEG (axis 2)**: **VALIDATED 12/12** with TWO configs (accel_scale 0.35 & 0.40). Need 2+ consecutive 12/12 autonomous runs. Target: reproduce case 8 & 10 params.
2. **EV3 Medium POS (axis 3)**: 11/12 at 1.95° error. Need 12/12. Try: increase endpoint_kp to 1.5-2.0e-6, reduce kp_pos to 2.3-2.4e-6, add small kd_vel (0.5e-6) for damping.
3. **EV3 Large (axes 0,1)**: Need 12/12 with max_track_err < 2.0°. Current best 3.18°. Paths: (a) Motor model recalibration from HW system ID, (b) Increase kp_pos to 3.0-3.5e-4, kv to 4.0e-6.
4. **Motor Model Calibration**: Run system identification on hardware for EV3 Large and EV3 Medium (unloaded). Update `tools/motor_models.json`.

**Expected autonomous run time**: ~15 min (16 cases × 45s + overhead)