# Phase 8 Motor Model Calibration (run 0x2609043A)

**Date**: 2026-09-04

## Test Matrix
- 16 cases: 4 axes × 4 repeats (EV3 Large M1/M2, EV3 Medium M3/M4, ±720°)
- Configs: v26 winning gains (EV3 Large: kp=4.0e-4, kv=5.0e-6; EV3 Medium: kp=2.5e-4, kv=1.0e-6, endpoint_kp=2.0e-6/2.5e-6)
- Autonomous run: `sysid_20260904_v2`

## Results: 16/16 committed, 16/16 traces decoded
| Case | Axis | Motor | Direction | Pass Rate | Score | Notes |
|------|------|-------|-----------|-----------|-------|-------|
| 04 | 1 | EV3 Large M2 | +720° | **12/12** | 3.41 | First 12/12 on hardware |
| 06 | 1 | EV3 Large M2 | +720° | 11/12 | 3.37 | Repeat |
| 05 | 1 | EV3 Large M2 | -720° | 11/12 | 4.23 | Repeat |
| 07 | 1 | EV3 Large M2 | -720° | 11/12 | 4.37 | Repeat |
| 09 | 2 | EV3 Medium M3 | +720° | 10/12 | 4.87 | Improved |
| 08 | 2 | EV3 Medium M3 | -720° | 8/12 | 6.03 | |
| 10 | 2 | EV3 Medium M3 | -720° | 8/12 | 5.74 | |
| 11 | 2 | EV3 Medium M3 | +720° | 8/12 | 7.35 | |
| 12 | 3 | EV3 Medium M4 | -720° | 4/12 | 44.55 | Poor |
| 13 | 3 | EV3 Medium M4 | +720° | 4/12 | 46.77 | Poor |
| 14 | 3 | EV3 Medium M4 | -720° | 3/12 | 52.72 | Poor |
| 15 | 3 | EV3 Medium M4 | +720° | 3/12 | 53.81 | Poor |
| 00 | 0 | EV3 Large M1 | +720° | 3/12 | 21.79 | |
| 01 | 0 | EV3 Large M1 | -720° | 5/12 | 19.51 | |
| 02 | 0 | EV3 Large M1 | +720° | 4/12 | 18.97 | |
| 03 | 0 | EV3 Large M1 | -720° | 5/12 | 15.22 | |

**Total**: 0/16 PASS (but case_04 achieved 12/12!)

## Key Findings
1. **Critical bug fixed**: `d_current_d_current` was negative (-5095199) in EV3 Medium model — completely wrong current dynamics.
2. **EV3 Medium model updated for unloaded operation**: torque_friction 24593→3000, d_speed_d_voltage 9410→5000, d_current_d_voltage 209263→100000, d_torque_d_acceleration 9355→20000, d_current_d_current -5095199→4000000.
3. **Simulation validation**: EV3 Medium now passes 12/12 in sim for BOTH directions with symmetric gains (kd_vel=0, endpoint_kp_vel=2.0e-6).
4. **Hardware stiction root cause identified**: PID stiction break requires `abs_vel_ref > 5000` (5 deg/s) to activate `startup_duty` ramp. Trapezoidal trajectories start at vref=0, so threshold isn't met until ~5ms later — motor never gets startup boost to overcome static friction. Traces show EV3 Medium stuck at start position with duty 10-30%.
5. **EV3 Large M2 positive achieved 12/12** — first 12/12 on hardware this session.
6. **M3 vs M4 asymmetry**: M3 (axis 2) achieves 8-10/12, M4 (axis 3) only 3-4/12 — possible encoder sign, motor direction, or mechanical difference.

## Infrastructure & Safety
- Battery: 8.2-8.4 V; min cell 3.0 V; age <250 µs (sampled at start of each case)
- Core 1 period: 999-1001 µs; exec max 194-211 µs; missed ticks: 0 across all cases
- Duty smoothness: EV3 Large 0.9-1.0, EV3 Medium 0.4-0.9 (stiction cases poor)

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| tuning.uf2 (sysid_20260904_v2) | 1966080 | [computed at decode] |
| flash_records.json | 66933 | |
| summary.csv | 2368 | |
| 16 trace .txt files | 31-40 KB each | |

## Updated Winning Configurations (to promote to motion_engine.c)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | accel_scale | endpoint_kp_vel |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EV3 Large | 4.0e-4 | 5.0e-6 | 8e-7 | 0 | 0.70 | 1.0e-6 |
| EV3 Medium NEG | 2.5e-4 | 1.0e-6 | 8e-7 | 0 | 0.35 | 2.0e-6 |
| EV3 Medium POS | 2.5e-4 | 1.0e-6 | 8e-7 | 0 | 0.35 | 2.0e-6 |

*Note: EV3 Medium now uses symmetric gains (kd_vel=0) for both directions — matches simulation 12/12 validation.*

## Next Step
1. **Fix stiction break logic in firmware** (`pid.c`): Lower velocity threshold from 5000 to 1000, or add position-error-based activation when `pos_err > deadzone` and `abs_vel_ref < 1000`.
2. **Update autonomous test matrix** (`autonomous_tuning.c`): For EV3 Medium cases (axes 2,3), increase `startup_duty` from 0.65 to 0.80, reduce `startup_release_speed_mdegs` from 10000 to 2000, use symmetric gains (kd_vel=0, endpoint_kp_vel=2.0e-6) for both directions.
3. **Re-run autonomous**: `python tools/flash_extract_decode.py --output-dir bench/results/sysid_20260905` — target 12/12 on all 4 axes.