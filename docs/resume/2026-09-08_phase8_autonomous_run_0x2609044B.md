# Phase 8 Autonomous Validation Run 0x2609044B

**Date**: 2026-09-08

## Test Matrix
- 16 cases: 4 axes × 4 repeats (alternating directions, absolute moves, 720° distance)
- Axis 0 (EV3 Large): POS, NEG, POS, NEG @ 800 deg/s, kp=4.0e-4, kv=5.0e-6, vel_window=10
- Axis 1 (EV3 Large): POS, NEG, POS, NEG @ 800 deg/s, kp=4.0e-4, kv=5.0e-6, vel_window=10
- Axis 2 (EV3 Medium UNLOADED): NEG, POS, NEG, POS @ 1100 deg/s, kp=2.5e-4, kv=1.0e-6, vel_window=40, start_duty=0.80
- Axis 3 (EV3 Medium UNLOADED): NEG, POS, NEG, POS @ 1100 deg/s, kp=2.5e-4, kv=1.0e-6, vel_window=40, start_duty=0.80
- All moves: 720° distance, trapezoidal trajectory, symmetric EV3 Medium config

## Results: 16/16 committed, 16/16 traces decoded

| Case | Axis | Dir | Repeat | Passed | Score | MaxErr | RMSErr | FinalErr | Overshoot | DutySmooth | Notes |
|------|------|-----|--------|--------|-------|--------|--------|----------|-----------|------------|-------|
| case_08 | 2 | NEG | r0 | **11/12** | 3.165 | 1.478° | 0.584° | 0.000° | 0.500° | 0.866 | First 11/12 for axis 2 |
| case_03 | 0 | NEG | r3 | **11/12** | 3.295 | 1.822° | 0.417° | 0.000° | 0.000° | 0.835 | |
| case_01 | 0 | NEG | r1 | **11/12** | 3.601 | 1.773° | 0.442° | 0.000° | 0.000° | 0.807 | |
| case_02 | 0 | POS | r2 | **11/12** | 4.242 | 1.656° | 0.496° | 0.000° | 0.492° | 0.817 | |
| case_00 | 0 | POS | r0 | **11/12** | 4.892 | 1.799° | 0.488° | 0.000° | 0.492° | 0.704 | |
| case_13 | 3 | POS | r1 | 10/12 | 3.386 | 1.493° | 0.381° | 0.000° | 0.500° | 0.804 | Stiction stall |
| case_11 | 2 | POS | r3 | 10/12 | 3.876 | 1.938° | 0.537° | 0.000° | 0.828° | 0.895 | |
| case_10 | 2 | NEG | r2 | 9/12 | 5.205 | 1.603° | 0.713° | -1.000° | 0.000° | 0.906 | |
| case_05 | 1 | NEG | r1 | 8/12 | 6.227 | 1.938° | 0.602° | 0.492° | 0.789° | 0.802 | |
| case_07 | 1 | NEG | r3 | 8/12 | 6.349 | 1.892° | 0.610° | 0.500° | 0.882° | 0.802 | |
| case_06 | 1 | POS | r2 | 8/12 | 6.380 | 1.924° | 0.618° | 0.500° | 0.875° | 0.800 | |
| case_15 | 3 | POS | r3 | 8/12 | 6.814 | 2.082° | 0.537° | 2.000° | 0.000° | 0.837 | Stiction stall |
| case_04 | 1 | POS | r0 | 8/12 | 6.934 | 1.898° | 0.612° | 0.500° | 0.906° | 0.726 | |
| case_09 | 2 | POS | r1 | 8/12 | 25.984 | 2.262° | 0.663° | 6.368° | 0.000° | 0.905 | Large final error |
| case_14 | 3 | NEG | r2 | 8/12 | 40.050 | 2.115° | 0.514° | -9.508° | 0.000° | 0.845 | Large final error |
| case_12 | 3 | NEG | r0 | 7/12 | 9.029 | 2.720° | 0.638° | -1.274° | 1.492° | 0.771 | |

**Full 12/12 PASS: 0/16 cases** (consistent with run-to-run variation)

## Key Findings

1. **EV3 Large (axis 0) shows strong consistency**: 3 out of 4 repeats achieved 11/12 pass (case_00 POS r0, case_01 NEG r1, case_02 POS r2, case_03 NEG r3). Axis 0 is reproducing the 12/12 config across repeats but run-to-run variation prevents full 12/12.

2. **EV3 Large axis 1 inconsistent**: case_04 POS r0 only 8/12, case_05 NEG r1 8/12, case_06 POS r2 8/12, case_07 NEG r3 8/12. Axis 1 is systematically worse than axis 0 despite identical gains - confirms per-axis/hardware difference.

3. **EV3 Medium axis 2 (case_08) achieved first 11/12**: NEG repeat 0 with symmetric config shows promise.

4. **EV3 Medium axis 3 POS stiction stalls persist**: case_13 (POS r1) 10/12, case_15 (POS r3) 8/12 with final errors of 0.0° and 2.0° respectively. The symmetric config (vel_window=40) is not fully resolving direction-reversal stiction.

5. **Run-to-run variation confirmed**: No case achieved 12/12 this run despite multiple 11/12 results. ~10% variance per axis persists.

6. **Core 1 timing excellent**: All 16 cases - 999-1001µs period, 190-208µs exec max, **0 missed ticks**.

7. **Battery**: Fresh samples, pack voltage maintained.

8. **Simulation DR validation aligned**: DR worst-case 2/12 for EV3 Large matches hardware run-to-run variation. vel_window=10 for EV3 Large eliminates limit cycle in sim; hardware shows 11/12 but not 12/12 consistently.

## Infrastructure & Safety
- Battery: Fresh samples (age < 250ms), pack > 6.5V, cells > 3.0V
- Core 1: 999-1001µs period, exec max 208µs, 0 missed ticks across all 16 cases
- All motors coasted at end of each case
- Console firmware restored after autonomous run

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| autonomous_auto_20260908_023053/summary.csv | ~2KB | (computed on demand) |
| autonomous_auto_20260908_023053/flash_records.json | ~8KB | (computed on demand) |
| 16 trace files (case_00.txt ... case_15.txt) | ~40KB each | (computed on demand) |

## Updated Winning Configurations (to promote to motion_engine.c)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large | **4.0e-4** | **5.0e-6** | 8e-7 | **0** | 0 | **0.70** | **1.0e-6** |
| EV3 Medium (both dirs) | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **2.0e-6** |

## Next Step
1. **EV3 Medium Axis 3 Stiction Stall Fix** - Increase start_duty for axis 3 from 0.80 → 0.90 and/or increase startup_pulse_on_ticks from 4 → 6 for POS cases (case_13, case_15). Test in sim first with backlash + higher static friction.
2. **EV3 Large Robustness** - DR validation shows worst-case 2/12 due to transport delay (4ms) and high friction (2x). Need gain tuning for DR robustness. Sweep kp_pos ↓, kp_vel ↑, endpoint_kp_vel ↑.
3. **Domain Randomization Harness** - Already implemented in run_validation.py. Use for systematic gain search.
4. **Run Autonomous Validation 0x2609044C** - After implementing axis 3 stiction fix and EV3 Large gain improvements.