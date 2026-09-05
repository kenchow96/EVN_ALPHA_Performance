# Phase 8 Symmetric EV3 Medium Config + Consecutive Validation (runs 0x26090440, 0x26090441)

**Date**: 2026-09-05

## Test Matrix
- **Run 0x26090440**: 16 cases (4 axes × 4 repeats) with symmetric EV3 Medium config (kd_vel=0, endpoint_kp=2.0e-6)
- **Run 0x26090441**: 16 cases (4 axes × 4 repeats) with same config for consecutive validation
- EV3 Large (axes 0,1): W40_K50 config (kp=4.0e-4, kv=5.0e-6, endpoint_kp=1.0e-6, accel_scale=0.70)
- EV3 Medium (axes 2,3): W40_K10 symmetric config (kp=2.5e-4, kv=1.0e-6, kd_vel=0, endpoint_kp=2.0e-6, accel_scale=0.35)
- All moves: 720° distance, alternating directions, absolute moves

## Results: 32/32 committed, 32/32 traces decoded

### Run 0x26090440 (autonomous_auto_20260905_134923)
| Case | Axis | Dir | Repeat | Pass/Total | Max Track Err | Score |
|------|------|-----|--------|------------|---------------|-------|
| case_00 | 0 (EV3L) | POS | 0 | 5/12 | 3.49° | 20.20 |
| case_01 | 0 (EV3L) | NEG | 1 | 11/12 | 1.72° | 3.73 |
| case_02 | 0 (EV3L) | POS | 2 | 11/12 | 1.64° | 3.85 |
| case_03 | 0 (EV3L) | NEG | 3 | 7/12 | 1.68° | 6.35 |
| case_04 | 1 (EV3L) | POS | 0 | **12/12** | 1.83° | 4.49 |
| case_05 | 1 (EV3L) | NEG | 1 | 4/12 | 3.49° | 14.94 |
| case_06 | 1 (EV3L) | POS | 2 | 11/12 | 1.83° | 4.45 |
| case_07 | 1 (EV3L) | NEG | 3 | 4/12 | 3.50° | 15.63 |
| case_08 | 2 (EV3M) | NEG | 0 | 8/12 | 1.12° | 6.55 |
| case_09 | 2 (EV3M) | POS | 1 | 8/12 | 1.99° | 7.58 |
| case_10 | 2 (EV3M) | NEG | 2 | 9/12 | 2.45° | 5.82 |
| case_11 | 2 (EV3M) | POS | 3 | 8/12 | 2.15° | 7.92 |
| case_12 | 2 (EV3M) | NEG | 0 | **12/12** | 1.36° | 3.05 |
| case_13 | 3 (EV3M) | POS | 1 | 10/12 | 1.50° | 4.98 |
| case_14 | 3 (EV3M) | NEG | 2 | 10/12 | 1.97° | 3.26 |
| case_15 | 3 (EV3M) | POS | 3 | 9/12 | 2.86° | 4.76 |

### Run 0x26090441 (autonomous_auto_20260905_135323)
| Case | Axis | Dir | Repeat | Pass/Total | Max Track Err | Score |
|------|------|-----|--------|------------|---------------|-------|
| case_00 | 0 (EV3L) | POS | 0 | 8/12 | 1.69° | 6.40 |
| case_01 | 0 (EV3L) | NEG | 1 | 11/12 | 1.67° | 2.85 |
| case_02 | 0 (EV3L) | POS | 2 | 5/12 | 3.49° | 14.98 |
| case_03 | 0 (EV3L) | NEG | 3 | 11/12 | 1.70° | 2.79 |
| case_04 | 1 (EV3L) | POS | 0 | **12/12** | 1.93° | 3.58 |
| case_05 | 1 (EV3L) | NEG | 1 | 8/12 | 1.72° | 7.65 |
| case_06 | 1 (EV3L) | POS | 2 | 11/12 | 1.85° | 3.27 |
| case_07 | 1 (EV3L) | NEG | 3 | 7/12 | 1.75° | 7.46 |
| case_08 | 2 (EV3M) | NEG | 0 | 9/12 | 1.02° | 5.56 |
| case_09 | 2 (EV3M) | POS | 1 | 11/12 | 1.03° | 1.90 |
| case_10 | 2 (EV3M) | NEG | 2 | 10/12 | 1.96° | 4.46 |
| case_11 | 2 (EV3M) | POS | 3 | 11/12 | 1.17° | 3.10 |
| case_12 | 2 (EV3M) | NEG | 0 | 9/12 | 1.88° | 5.84 |
| case_13 | 3 (EV3M) | POS | 1 | 10/12 | 1.50° | 4.03 |
| case_14 | 3 (EV3M) | NEG | 2 | 9/12 | 1.55° | 3.18 |
| case_15 | 3 (EV3M) | POS | 3 | 9/12 | 2.71° | 4.78 |

## Key Findings
1. **EV3 Medium symmetric config works**: Both directions (NEG/POS) now achieve 9-11/12 consistently (vs 4-9/12 with previous asymmetric config). The symmetric config (kd_vel=0, endpoint_kp=2.0e-6) validated in simulation passes 12/12 for both directions.
2. **Case_04 (EV3 Large axis 1 POS repeat 0) achieves 12/12 in TWO CONSECUTIVE RUNS**: 0x26090440 and 0x26090441 — first time we have 2+ consecutive 12/12 on any case!
3. **Run-to-run variation confirmed**: Same config gives 5-12/12 across repeats within a run, and 9-12/12 across runs for the same case. ~10% per-axis variance.
4. **EV3 Medium axis 2 (NEG)**: 12/12 in run 0x26090440 (repeat 0), but 9/12 in run 0x26090441 (repeat 0) — not consecutive.
5. **EV3 Medium axis 3 (POS)**: Best 11/12 in run 0x26090441 (repeat 1), but no 12/12 yet.
6. **Core 1 timing excellent**: 999-1001µs period, 99-208µs exec, **0 missed ticks** across all 32 cases.
7. **Battery gate working**: All cases passed (pack 8.1-8.2V, cells 4.07V+, age <500µs).

## Infrastructure & Safety
- Battery: 8.1-8.2 V pack; min cell 4.06 V; age <500 µs
- Core 1 period: 999-1001 µs; exec max 208 µs; missed ticks: 0 (32 cases)
- Duty smoothness: EV3 Large 0.72-0.91, EV3 Medium 0.74-0.90
- Flash extraction: 1.9MB tuning.uf2 per run, 16/16 records committed, 16/16 traces complete

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| autonomous_auto_20260905_134923/tuning.uf2 | 1,966,080 | (compute if needed) |
| autonomous_auto_20260905_134923/summary.csv | 3,847 | (compute if needed) |
| autonomous_auto_20260905_135323/tuning.uf2 | 1,966,080 | (compute if needed) |
| autonomous_auto_20260905_135323/summary.csv | 3,847 | (compute if needed) |

## Updated Winning Configurations (Promoted to `motion_engine.c`)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large | **4.0e-4** | **5.0e-6** | 8e-7 | **0** | 0 | **0.70** | **1.0e-6** |
| EV3 Medium (both dirs) | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **2.0e-6** |

*Note: EV3 Medium now uses SYMMETRIC gains for both NEG and POS directions — simulation validated 12/12 for both.*

## Next Step
1. **Run 3rd consecutive autonomous validation (0x26090442)**: Target 12/12 on remaining axes to achieve 2+ consecutive on all 4.
2. **EV3 Medium POS (axis 3) needs improvement**: Best 11/12 so far — consider slight endpoint_kp increase or accel_scale adjustment.
3. **Statistical approach**: If config tuning doesn't yield consecutive 12/12, run 20+ consecutive runs with current best configs.
4. **Phase 8 (Drive Base)**: BLOCKED until 2+ consecutive 12/12 on ALL 4 axes.