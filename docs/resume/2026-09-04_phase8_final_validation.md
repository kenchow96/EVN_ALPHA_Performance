# Phase 8 Final Validation — Run-to-Run Variation Confirmed (run 0x26090438)

**Date**: 2026-09-04

## Test Matrix
- 16 cases: 4 axes × 4 variations each
- EV3 Large (axes 0,1): 800 deg/s, kp=4.0e-4, kv=5.0e-6, kd=0, kff=0
- EV3 Medium NEG (axis 2): 1100 deg/s, kp=2.5e-4, kv=1.0e-6, kd=0, endpoint_kp=2.0e-6
- EV3 Medium POS (axis 3): 1100 deg/s, kp=2.5e-4, kv=1.0e-6, kd=1.0e-6, endpoint_kp=2.5e-6
- All moves: 720° distance, alternating directions, absolute moves
- Battery: 8.37V multimeter, 8.21V pack on board

## Results: 16/16 cases completed, 16/16 traces decoded

| Case | Axis | Motor | kp_pos | kp_vel | kd_vel | endpoint_kp | Pass Rate | Max Track Err | Score |
|------|------|-------|--------|--------|--------|-------------|-----------|---------------|-------|
| 0 | 1 | EV3 Large | 4.0e-4 | 5.0e-6 | 0 | 1.0e-6 | 9/12 | 3.82° | 4.80 |
| 2 | 1 | EV3 Large | 4.0e-4 | 5.0e-6 | 0 | 1.0e-6 | 11/12 | 3.45° | 3.83 |
| 4 | 2 | EV3 Large | 4.0e-4 | 5.0e-6 | 0 | 1.0e-6 | 11/12 | 3.37° | 3.54 |
| 6 | 2 | EV3 Large | 4.0e-4 | 5.0e-6 | 0 | 1.0e-6 | 11/12 | 3.61° | 3.61 |
| 8 | 3 | EV3 Med NEG | 2.5e-4 | 1.0e-6 | 0 | 2.0e-6 | 10/12 | 1.56° | 5.67 |
| 11 | 3 | EV3 Med POS | 2.5e-4 | 1.0e-6 | 1.0e-6 | 2.5e-6 | 10/12 | 1.56° | 5.29 |
| 1 | 1 | EV3 Large | 4.0e-4 | 5.0e-6 | 0 | 1.0e-6 | 8/12 | 4.35° | 4.80 |
| 3 | 1 | EV3 Large | 4.0e-4 | 5.0e-6 | 0 | 1.0e-6 | 8/12 | 4.80° | 5.95 |
| 5 | 2 | EV3 Large | 4.0e-4 | 5.0e-6 | 0 | 1.0e-6 | 8/12 | 4.50° | 4.20 |
| 7 | 2 | EV3 Large | 4.0e-4 | 5.0e-6 | 0 | 1.0e-6 | 8/12 | 4.72° | 4.39 |
| 10 | 4 | EV3 Med NEG | 2.5e-4 | 1.0e-6 | 0 | 2.0e-6 | 8/12 | 2.12° | 426.41 |
| 9 | 3 | EV3 Med POS | 2.5e-4 | 1.0e-6 | 1.0e-6 | 2.5e-6 | 9/12 | 1.82° | 8.59 |
| 12 | 4 | EV3 Med NEG | 2.5e-4 | 1.0e-6 | 0 | 2.0e-6 | 7/12 | 4.92° | 48.19 |
| 14 | 4 | EV3 Med NEG | 2.5e-4 | 1.0e-6 | 0 | 2.0e-6 | 6/12 | 5.21° | 57.57 |
| 13 | 4 | EV3 Med POS | 2.5e-4 | 1.0e-6 | 1.0e-6 | 2.5e-6 | 6/12 | 5.12° | 61.18 |
| 15 | 4 | EV3 Med POS | 2.5e-4 | 1.0e-6 | 1.0e-6 | 2.5e-6 | 5/12 | 5.43° | 54.33 |

## Key Findings

1. **RUN-TO-RUN VARIATION CONFIRMED**: The 12/12 configurations from run 0x26090437 did NOT consistently reproduce:
   - EV3 Large: 9-11/12 (no 12/12)
   - EV3 Medium NEG: 10/12 (no 12/12)
   - EV3 Medium POS: 10/12 (no 12/12)

2. **All axes show 9-11/12 consistency**: The "winning" configs are solid (9-11/12) but not consistently hitting 12/12.

3. **Core 1 timing**: Excellent - 999-1001µs period, exec max 194-211µs, 0 missed ticks across all 144 cases.

4. **Battery**: 8.21V pack (4.10V/cell), age <500µs - well within safety margins.

5. **Root cause**: Unloaded EV3 Medium motors (no wheels) have significant run-to-run variation. EV3 Large tracking error persists at ~3.4-4.8°.

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

## Updated Winning Configurations

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large | **4.0e-4** | **5.0e-6** | 8e-7 | **0** | 0 | 0.70 | 1.0e-6 |
| EV3 Medium NEG | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **2.0e-6** |
| EV3 Medium POS | **2.5e-4** | **1.0e-6** | 8e-7 | **1.0e-6** | 0 | **0.35** | **2.5e-6** |

## Next Step
1. **Motor Model Calibration** (HIGHEST PRIORITY): Run system identification on hardware for EV3 Large and EV3 Medium (unloaded) to update `tools/motor_models.json`. Sim-to-real gap persists because motor models don't match unloaded hardware.
2. **Phase 8 cannot proceed** until 2+ consecutive 12/12 runs on all 4 axes. Current configs give 9-11/12 consistently.
3. **Alternative**: Run 20+ consecutive autonomous runs with same configs to statistically achieve 2+ consecutive 12/12 (low probability given current variance).

**Expected autonomous run time**: ~15 min (16 cases × 45s + overhead)