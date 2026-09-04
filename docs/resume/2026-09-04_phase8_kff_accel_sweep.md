# Phase 8 kff_accel Sweep & Unloaded EV3 Medium Retune (run 0x26090433)

**Date**: 2026-09-04

## Test Matrix
- 16 cases: 4 axes × 4 variations each
- EV3 Large (axes 0,1): 800 deg/s, kff_accel sweep (0, 5e-7, 1e-6, 2e-6)
- EV3 Medium NEG (axis 2): 1100 deg/s, kv/endpoint_kp sweep
- EV3 Medium POS (axis 3): 1100 deg/s, reproduce 12/12 config (kv=1.5e-6) × 4 repeats
- All moves: 720° distance, alternating directions, absolute moves
- Battery: 8.37V multimeter, 8.24V pack on board

## Results: 16/16 cases completed, 16/16 traces decoded

| Case | Axis | Motor | kff_accel | kv | endpoint_kp | Pass Rate | Max Track Err | Score |
|------|------|-------|-----------|-----|-------------|-----------|---------------|-------|
| 0 | 0 | EV3 Large | 0 | 2.5e-6 | 1.0e-6 | **11/12** | 3.31° | 4.52 |
| 1 | 0 | EV3 Large | 5e-7 | 2.5e-6 | 1.0e-6 | 4/12 | 5.50° | 10.56 |
| 2 | 0 | EV3 Large | 1e-6 | 2.5e-6 | 1.0e-6 | 4/12 | 9.37° | 17.10 |
| 3 | 0 | EV3 Large | 2e-6 | 2.5e-6 | 1.0e-6 | 6/12 | 17.66° | 27.72 |
| 4 | 1 | EV3 Large | 0 | 2.5e-6 | 1.0e-6 | **10/12** | 3.60° | 4.57 |
| 5 | 1 | EV3 Large | 5e-7 | 2.5e-6 | 1.0e-6 | 5/12 | 5.40° | 9.03 |
| 6 | 1 | EV3 Large | 1e-6 | 2.5e-6 | 1.0e-6 | 6/12 | 9.37° | 17.10 |
| 7 | 1 | EV3 Large | 2e-6 | 2.5e-6 | 1.0e-6 | 4/12 | 16.86° | 26.06 |
| 8 | 2 | EV3 Med NEG | 0 | 1.0e-6 | 1.0e-6 | 7/12 | 1.50° | 6.89 |
| 9 | 2 | EV3 Med NEG | 0 | 1.2e-6 | 1.0e-6 | 8/12 | 1.16° | 6.20 |
| 10 | 2 | EV3 Med NEG | 0 | 1.0e-6 | 5e-7 | 8/12 | 1.00° | 4.97 |
| 11 | 2 | EV3 Med NEG | 0 | 1.2e-6 | 2.0e-6 | **11/12** | 1.09° | 4.21 |
| 12 | 3 | EV3 Med POS | 0 | 1.5e-6 | 1.0e-6 | **11/12** | 1.87° | 5.73 |
| 13 | 3 | EV3 Med POS | 0 | 1.5e-6 | 1.0e-6 | 10/12 | 1.50° | 3.53 |
| 14 | 2 | EV3 Med NEG | 0 | 2.0e-6 | 1.0e-6 | 10/12 | 2.88° | 6.29 |
| 15 | 3 | EV3 Med POS | 0 | 1.5e-6 | 1.0e-6 | 6/12 | 4.50° | 21.35 |

## Key Findings

1. **kff_accel is HARMFUL for EV3 Large**: kff=0 gives 10-11/12; any kff>0 degrades to 4-6/12 with massive tracking error (9-17°). Acceleration feedforward causes overshoot/oscillation.

2. **EV3 Medium motors now UNLOADED**: Ports 3/4 have NEW motors with NO WHEELS (previously had light load). This changes dynamics significantly - less inertia/friction causes overshoot and run-to-run variation.

3. **EV3 Medium NEG (axis 2)**: Best config = kv=1.2e-6, endpoint_kp=2.0e-6 (11/12, 1.09° error). Previous 12/12 was with loaded motors.

4. **EV3 Medium POS (axis 3)**: Highly variable - 6/12 to 11/12 for IDENTICAL params (kv=1.5e-6). NEG move (case 12) = 11/12; POS moves = 6-10/12. Unloaded motor oscillates on POS approach.

5. **Core 1 timing**: Excellent - 999-1001µs period, exec max 196-213µs, 0 missed ticks across all 16 cases.

6. **Battery**: 8.24V pack (4.11V/cell), age <500µs - well within safety margins.

## Infrastructure & Safety
- Battery: 8.24V pack; min cell 4.09V; age <500µs
- Core 1 period: 999-1001µs; exec max 213µs; missed ticks: 0
- Duty smoothness: 0.69-0.95 range
- All motors coasted at end of each case

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| tuning.uf2 | 1,966,080 | [computed at runtime] |
| summary.csv | 2,156 | [computed at runtime] |
| 16 case JSON/trace files | ~500KB total | [computed at runtime] |

## Updated Winning Configurations (for next iteration)

| Motor | kp_pos | kp_vel | ki_pos | kff_accel | endpoint_kp_vel | accel_scale | Notes |
|-------|--------|--------|--------|-----------|-----------------|-------------|-------|
| EV3 Large | 2.2e-4 | 2.5e-6 | 8e-7 | **0** | 1.0e-6 | 0.70 | kff_accel=0 best |
| EV3 Medium NEG | 3.0e-4 | 1.2e-6 | 8e-7 | 0 | **2.0e-6** | 0.35 | Higher endpoint_kp |
| EV3 Medium POS | 3.0e-4 | **1.0e-6** | 8e-7 | 0 | 1.0e-6 | **0.30** | Lower kv/accel_scale for unloaded |

## Next Step
1. **EV3 Medium (axes 2,3)**: Reduce kp_pos to 2.5e-4, kv to 1.0e-6, accel_scale to 0.30 for unloaded motors. Increase endpoint_kp_vel to 2.0e-6 for NEG motor.
2. **EV3 Large (axes 0,1)**: Keep kff_accel=0. Sweep kp_pos 2.2-2.8e-4, kv 2.5-3.5e-6 to close 3.3° tracking gap.
3. **Add kd_vel derivative term** for EV3 Medium POS to dampen unloaded motor oscillation.
4. Target: 2+ consecutive 12/12 on all 4 axes before Phase 8 (drive base).

**Expected autonomous run time**: ~15 min (16 cases × 45s + overhead)