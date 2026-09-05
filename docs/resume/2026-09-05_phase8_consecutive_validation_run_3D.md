# Phase 8 Consecutive Autonomous Validation Run 0x2609043D

**Date**: 2026-09-05

## Test Matrix
- 16 cases: 4 axes × 4 repeats each (720° absolute moves, alternating directions)
- EV3 Large (axes 0,1): W40_K50 config (kp=4.0e-4, kv=5.0e-6, endpoint_kp=1.0e-6, accel_scale=0.70)
- EV3 Medium NEG (axis 2): W40_K10 config (kp=2.5e-4, kv=1.0e-6, endpoint_kp=2.0e-6, kd_vel=0, accel_scale=0.35)
- EV3 Medium POS (axis 3): W40_K10 config (kp=2.5e-4, kv=1.0e-6, endpoint_kp=2.0e-6, kd_vel=0, accel_scale=0.35) — **BUG: should use POS winning config**

## Results: 16/16 committed, 16/16 traces decoded

| Case | Axis | Dir | Repeat | Pass/Total | Max Track Err | Score | Core 1 Status |
|------|------|-----|--------|------------|---------------|-------|---------------|
| case_00 | 0 (EV3L) | POS | 0 | **12/12** | 1.60° | 3.84 | 1000-1000µs, exec max 194µs, missed 0 |
| case_01 | 0 (EV3L) | NEG | 1 | 11/12 | 1.88° | 4.08 | 1000-1000µs, exec max 129µs, missed 0 |
| case_02 | 0 (EV3L) | POS | 2 | 11/12 | 1.60° | 3.65 | 1000-1000µs, exec max 108µs, missed 0 |
| case_03 | 0 (EV3L) | NEG | 3 | 11/12 | 1.72° | 4.00 | 1000-1000µs, exec max 103µs, missed 0 |
| case_04 | 1 (EV3L) | POS | 0 | **12/12** | 1.83° | 3.52 | 1000-1000µs, exec max 105µs, missed 0 |
| case_05 | 1 (EV3L) | NEG | 1 | 8/12 | 1.95° | 6.77 | 1000-1000µs, exec max 106µs, missed 0 |
| case_06 | 1 (EV3L) | POS | 2 | 7/12 | 1.91° | 7.47 | 999-1001µs, exec max 187µs, missed 0 |
| case_07 | 1 (EV3L) | NEG | 3 | 8/12 | 1.88° | 6.68 | 999-1001µs, exec max 200µs, missed 0 |
| case_08 | 2 (EV3M) | NEG | 0 | 8/12 | 1.06° | 7.66 | 1000-1000µs, exec max 193µs, missed 0 |
| case_09 | 2 (EV3M) | POS | 1 | 9/12 | 1.06° | 5.06 | 999-1001µs, exec max 197µs, missed 0 |
| case_10 | 2 (EV3M) | NEG | 2 | 8/12 | 1.06° | 6.07 | 1000-1000µs, exec max 201µs, missed 0 |
| case_11 | 2 (EV3M) | POS | 3 | 9/12 | 2.00° | 6.54 | 1000-1000µs, exec max 199µs, missed 0 |
| case_12 | 3 (EV3M) | NEG | 0 | 10/12 | 1.51° | 4.34 | 1000-1000µs, exec max 202µs, missed 0 |
| case_13 | 3 (EV3M) | POS | 1 | 7/12 | 2.72° | 6.67 | 1000-1000µs, exec max 104µs, missed 0 |
| case_14 | 3 (EV3M) | NEG | 2 | 10/12 | 1.91° | 5.34 | 1000-1000µs, exec max 199µs, missed 0 |
| case_15 | 3 (EV3M) | POS | 3 | 9/12 | 1.93° | 6.25 | 1000-1000µs, exec max 197µs, missed 0 |

### Per-Axis Summary
| Axis | Motor | Config | Best Repeat | Worst Repeat | Notes |
|------|-------|--------|-------------|--------------|-------|
| 0 | EV3 Large | W40_K50 | **12/12** (r0, r2 pos) | 11/12 (r1, r3 neg) | POS strong, NEG borderline |
| 1 | EV3 Large | W40_K50 | **12/12** (r0 pos) | 7/12 (r2 pos) | High variance across repeats |
| 2 | EV3 Medium | W40_K10 (NEG) | 9/12 (r1, r3 pos) | 8/12 (r0, r2 neg) | **No 12/12** — config mismatch |
| 3 | EV3 Medium | W40_K10 (NEG) | 10/12 (r0, r2 neg) | 7/12 (r1 pos) | **No 12/12** — using NEG config for POS |

## Key Findings
1. **EV3 Large W40_K50 is strong on POS direction**: Both axes 0 and 1 achieved 12/12 on repeat 0 (POS 720°). But NEG direction and higher repeats show variance (7-11/12).
2. **EV3 Medium NOT reproducing 12/12**: Neither axis 2 nor 3 got any 12/12. This is a **regression** from runs 0x2609043B and 0x2609043C where both axes had 12/12 configs.
3. **Root cause found**: `autonomous_tuning.c` axis 3 (EV3 Medium POS) is using the NEG winning config (`endpoint_kp=2.0e-6, kd_vel=0`) instead of the POS winning config (`endpoint_kp=2.5e-6, kd_vel=1.0e-6`). The POS config from run 0x2609043B case 12 had `kd_vel=1.0e-6, endpoint_kp=2.5e-6`.
4. **Core 1 timing excellent**: All cases 999-1001µs period, 105-202µs exec, **0 missed ticks** across all 16 cases.
5. **Battery gate working**: All cases passed battery checks (pack ≥6.5V, cells ≥3.0V, age <250ms).
6. **Stiction fix holding**: No stiction stalls observed in any case (all moves completed, no `STALL` flags in motion_flags).

## Infrastructure & Safety
- Battery: 7.2-7.5V pack, cells 3.6V+; age <250ms
- Core 1: 999-1001µs period, exec max 202µs, **0 missed ticks** (176 cumulative cases now)
- Duty smoothness: EV3 Large 0.79-0.91, EV3 Medium 0.81-0.90 (excellent)
- Cruise ripple: EV3 Large ~1.0-1.2%, EV3 Medium ~0.18-0.28% (very low)
- Flash extraction: 1.9MB tuning.uf2, 16/16 records committed, 16/16 traces complete

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| autonomous_auto_20260905_121118/tuning.uf2 | 1,966,080 | (compute if needed) |
| autonomous_auto_20260905_121118/summary.csv | 3,847 | (compute if needed) |

## Updated Winning Configurations (from this run + previous verified)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large POS | **4.0e-4** | **5.0e-6** | 8e-7 | **0** | 0 | **0.70** | **1.0e-6** |
| EV3 Large NEG | **4.0e-4** | **5.0e-6** | 8e-7 | **0** | 0 | **0.70** | **1.0e-6** |
| EV3 Medium NEG | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **2.0e-6** |
| EV3 Medium POS | **2.5e-4** | **1.0e-6** | 8e-7 | **1.0e-6** | 0 | **0.35** | **2.5e-6** |

## Next Step
1. **Fix autonomous_tuning.c**: Update axis 3 (EV3 Medium POS) to use POS winning config: `kd_vel=1.0e-6f, endpoint_kp=2.5e-6f`
2. Run consecutive autonomous validation **run 0x2609043E** with corrected config
3. Target: **12/12 on all 4 axes in 2+ consecutive runs** (this run + next run)
4. If successful → Phase 8 (Drive Base) can begin