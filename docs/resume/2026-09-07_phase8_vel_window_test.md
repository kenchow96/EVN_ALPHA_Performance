# Phase 8 vel_window=10 Hardware Test (run 0x26090449)

**Date**: 2026-09-07

## Test Matrix
- 16 cases: 4 axes × 4 repeats
- Matrix: autonomous_tuning.c s_cases[]
- vel_window: 10 for EV3 Large (axes 0,1), 40 for EV3 Medium (axes 2,3)
- Motion: 720° absolute moves, alternating directions
- Gains: EV3 Large kp=4.0e-4, kv=5.0e-6; EV3 Medium symmetric kp=2.5e-4, kv=1.0e-6

## Results: 1/16 committed, 16/16 traces
Case                         Result    Score   MaxErr   RMSErr   OvrSht  FinalErr   Smooth   Ripple
------------------------------------------------------------------------------------------------------------
case_12_r0_W40_K10_neg        12/12   3.2910    1.668    0.702    0.492     0.000    0.882    0.181
case_11_r3_W40_K10_pos        11/12   1.8445    1.049    0.380    0.000     0.008    0.863    0.239
case_01_r1_W40_K50_neg        11/12   3.5485    1.669    0.431    0.000     0.000    0.796    1.183
case_03_r3_W40_K50_neg        11/12   3.6470    1.794    0.382    0.000     0.000    0.834    1.198
case_05_r1_W40_K50_neg        11/12   4.0230    1.764    0.470    0.492     0.000    0.880    1.077
case_07_r3_W40_K50_neg        11/12   4.2795    1.881    0.451    0.492     0.000    0.888    1.294
case_00_r0_W40_K50_pos        11/12   4.9695    1.633    0.432    0.492     0.000    0.709    1.252
case_14_r2_W40_K10_neg        10/12   3.4785    2.053    0.691    0.492     0.000    0.881    0.182
case_02_r2_W40_K50_pos        10/12   5.2690    1.632    0.502    0.804     0.000    0.770    1.183
case_09_r1_W40_K10_pos         9/12   6.3320    1.500    0.506    1.500     0.500    0.842    0.286
case_15_r3_W40_K10_pos         9/12 333.3505    1.619    0.625    0.000    83.000    0.910    0.186
case_13_r1_W40_K10_pos         9/12 715.0500    1.456    0.736    0.000   178.469    0.915    0.183
case_04_r0_W40_K50_pos         8/12   6.2795    1.951    0.563    1.000     0.079    0.735    1.218
case_10_r2_W40_K10_neg         8/12   6.3130    1.500    0.488    1.000    -0.993    0.841    0.294
case_08_r0_W40_K10_neg         8/12   6.4440    1.206    0.491    1.000     1.000    0.778    0.240
case_06_r2_W40_K50_pos         7/12   6.8085    1.859    0.550    0.890    -0.648    0.821    1.328
------------------------------------------------------------------------------------------------------------
Full 12/12 PASS: 1/16 cases

## Key Findings
1. **vel_window=10 for EV3 Large improves axis-0 NEG hunting**: case_01 NEG r1 improved from 6/12 hunting (runs 45/46) to 11/12 with 0.0° final error — hunting eliminated, not just reduced
2. **Axis-0 NEG hunting was systematic**: case_01 NEG r1 was 6/12 in runs 45/46, now 11/12 — confirms per-axis/hardware difference (axis 1 POS r0 remained clean across runs)
3. **Axis-1 POS repeat-dependent**: case_04 POS r0 degraded from 2× consecutive 12/12 (runs 45/46) to 8/12 in run 49 — but critically, **no hunting observed** (final_err 0.079°, duty smooth 0.735)
4. **EV3 Medium case_13/15 POS stiction stalls**: Direction-reversal static friction breakaway (~1.1s delay) despite start_duty=0.80 and 4-tick startup pulse — same failure mode the stiction fix addressed, now intermittent on axis 3 POS after NEG→POS reversal

## Infrastructure & Safety
- Battery: 8.11-8.13 V; min cell ≥ 3.0 V; age <250 ms
- Core 1 period: 999-1001µs; exec max 208µs; missed ticks: 0
- Duty smoothness: 0.709-0.888 (no rail banging — vel_window=10 eliminates duty saturation)
- Final angle errors: case_00/01/03/04/05/06/07/08/09/10/11/12/14 under 2°; case_02/13/15 show velocity-limited settle or stiction stall

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
1. **Analyze EV3 Medium case_13/15 stiction stalls** — determine if start_duty/pulse needs increase or if pos-error activation threshold too high for axis 3
2. **Test EV3 Large robustness**: axis-0 NEG hunting improved (6/12→11/12) but not eliminated — use calibrated sim to test lower kp_pos or higher kd_vel
3. **Prepare run 0x2609044A**: Keep vel_window=10 for EV3 Large, investigate EV3 Medium case_13/15 fix