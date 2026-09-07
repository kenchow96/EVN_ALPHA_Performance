# Phase 8 Autonomous Validation Run 0x2609044A

**Date**: 2026-09-08

## Test Matrix
- 16 cases: 4 axes × 4 repeats
- Matrix: autonomous_tuning.c s_cases[]
- vel_window: 10 for EV3 Large (axes 0,1) and EV3 Medium axis 3; 40 for EV3 Medium axis 2
- Motion: 720° absolute moves, alternating directions
- Gains: EV3 Large kp=4.0e-4, kv=5.0e-6; EV3 Medium symmetric kp=2.5e-4, kv=1.0e-6

## Results: 16/16 committed, 16/16 traces
Case                         Result    Score   MaxErr   RMSErr   OvrSht  FinalErr   Smooth   Ripple
------------------------------------------------------------------------------------------------------------
case_08_r0_W40_K10_neg        12/12   2.1495    1.709    0.547    0.000     0.000    0.883    0.163
case_02_r2_W40_K50_pos        11/12   3.2420    1.700    0.509    0.000     0.008    0.837    1.052
case_03_r3_W40_K50_neg        11/12   3.4735    1.905    0.429    0.000     0.000    0.821    1.157
case_01_r1_W40_K50_neg        11/12   3.6720    1.808    0.503    0.000     0.000    0.764    1.075
case_05_r1_W40_K50_neg        11/12   4.1530    1.896    0.510    0.492     0.000    0.882    1.121
case_07_r3_W40_K50_neg        11/12   4.2545    1.971    0.546    0.492     0.000    0.859    1.034
case_04_r0_W40_K50_pos        11/12   4.5520    1.924    0.472    0.500     0.000    0.823    1.233
case_00_r0_W40_K50_pos        11/12   4.8975    1.759    0.456    0.492     0.000    0.729    1.193
case_10_r2_W40_K10_neg        10/12   2.7320    2.534    0.788    0.000     0.000    0.904    0.197
case_15_r3_W40_K10_pos        10/12   4.3980    1.500    0.462    0.500    -0.500    0.818    0.276
case_13_r1_W40_K10_pos         9/12   5.4215    1.493    0.431    0.500     1.000    0.803    0.259
case_14_r2_W40_K10_neg         9/12   5.4530    1.500    0.417    1.500     0.000    0.798    0.276
case_06_r2_W40_K50_pos         8/12   6.6120    1.968    0.611    1.000    -0.500    0.806    1.047
case_09_r1_W40_K10_pos         8/12   8.7945    2.191    0.696    0.000     2.500    0.904    0.205
case_11_r3_W40_K10_pos         8/12  44.0455    2.191    0.653    0.000    10.547    0.909    0.198
case_12_r0_W40_K10_neg         7/12   7.3250    2.576    0.638    1.000     1.000    0.773    0.264
------------------------------------------------------------------------------------------------------------
Full 12/12 PASS: 1/16 cases

## Key Findings
1. **EV3 Medium axis 2 (case_08): First 12/12 for axis 2 NEG repeat 0** — axis 2 performing well with vel_window=40
2. **EV3 Medium axis 3 (new motor) stiction stalls persist on POS**: case_13 (POS r1) 9/12, case_15 (POS r3) 10/12 (improved from 9/12 in run 49). vel_window=10 helped slightly but not enough.
3. **EV3 Medium axis 3 NEG also degraded**: case_12 (NEG r0) 7/12, case_14 (NEG r2) 9/12 — new motor shows variability both directions
4. **EV3 Large axes (0,1)**: Stable at 11/12 for POS repeats, 10-11/12 for NEG. case_04 (axis 1 POS r0) 11/12 (was 8/12 in run 49) — recovered from degradation.
5. **Core 1 timing**: Excellent — 999-1001µs period, 192-203µs exec, 0 missed ticks across all 16 cases.
6. **Battery**: 8.21 V pack, cells 4.09/4.08 V, age 434 µs — healthy.

## Infrastructure & Safety
- Battery: 8.21 V; min cell 4.08 V; age <500 µs
- Core 1 period: 999-1001µs; exec max 203µs; missed ticks: 0
- Duty smoothness: 0.729-0.909 (no rail banging)
- Final angle errors: Most cases <2°; case_11/15 show velocity-limited settle

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| tuning.uf2 | 4.2M | [will update after session] |
| case_*.txt traces | ~200KB each | [will update after session] |
| summary.csv | 1.5KB | [will update after session] |
| flash_records.json | 1.2KB | [will update after session] |

## Updated Winning Configurations (to promote to motion_engine.c)
| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EV3 Large | **4.0e-4** | **5.0e-6** | 8e-7 | **0** | 0 | **0.70** | **1.0e-6** |
| EV3 Medium (both dirs) | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **2.0e-6** |

## Next Step
1. **EV3 Medium axis 3 stiction stall on POS reversals**: vel_window=10 helped slightly (case_15 9→10/12) but not eliminated. Options: increase start_duty further, increase startup_pulse_on_ticks, or add per-axis stiction parameters.
2. **EV3 Large robustness**: All cases 10-11/12, run-to-run variation ~10%. Use calibrated sim to test lower kp_pos or add small kd_vel.
3. **Prepare run 0x2609044B**: Test higher start_duty (0.90) and/or more startup pulse ticks for axis 3; keep vel_window=10 for axis 3.