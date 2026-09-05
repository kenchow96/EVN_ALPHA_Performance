# Phase 8 Autonomous Validation Run 0x2609043E

**Date**: 2026-09-05

## Test Matrix
- 16 cases: 4 axes × 4 repeats (0-3)
- EV3 Large (axes 0,1): 800 deg/s max, 720° moves, W40_K50 gains (kp=4.0e-4, kv=5.0e-6)
- EV3 Medium UNLOADED (axes 2,3): 1100 deg/s max, 720° moves, W40_K10 gains
  - Axis 2 NEG: kp=2.5e-4, kv=1.0e-6, endpoint_kp=2.0e-6, kd=0
  - Axis 3 POS: kp=2.5e-4, kv=1.0e-6, endpoint_kp=2.5e-6, kd=1.0e-6 (FIXED from run 0x2609043B case 12)
- All moves: absolute, alternating directions

## Results: 14/16 committed, 14/16 traces decoded
| Case | Axis | Dir | Repeat | Score | Passed/Total | Max Track Err (°) | Core 1 |
|------|------|-----|--------|-------|--------------|-------------------|--------|
| 0 | 0 (EV3 Large) | POS | 0 | 6.41 | 8/12 | 1.63 | 999-1001µs, 0 miss |
| 1 | 0 (EV3 Large) | NEG | 1 | 3.73 | 11/12 | 1.72 | 1000-1000µs, 0 miss |
| 2 | 0 (EV3 Large) | POS | 2 | 3.85 | 11/12 | 1.64 | 999-1001µs, 0 miss |
| 3 | 0 (EV3 Large) | NEG | 3 | 6.35 | 7/12 | 1.68 | 999-1001µs, 0 miss |
| 4 | 1 (EV3 Large) | POS | 0 | 19.01 | 6/12 | 3.77 | 1000-1000µs, 0 miss |
| 5 | 1 (EV3 Large) | NEG | 1 | 17.57 | 6/12 | 3.57 | 1000-1000µs, 0 miss |
| 6 | 1 (EV3 Large) | POS | 2 | 16.93 | 5/12 | 3.87 | 999-1001µs, 0 miss |
| 7 | 1 (EV3 Large) | NEG | 3 | 13.18 | 6/12 | 3.75 | 1000-1000µs, 0 miss |
| 8 | 2 (EV3 Med NEG) | NEG | 0 | 7.92 | 9/12 | 2.00 | 999-1001µs, 0 miss |
| 9 | 2 (EV3 Med POS) | POS | 1 | 8.57 | 8/12 | 1.99 | 1000-1000µs, 0 miss |
| 10 | 2 (EV3 Med NEG) | NEG | 2 | 5.82 | 8/12 | 2.45 | 1000-1000µs, 0 miss |
| 11 | 2 (EV3 Med POS) | POS | 3 | 7.58 | 9/12 | 1.99 | 999-1001µs, 0 miss |
| 12 | 3 (EV3 Med NEG) | NEG | 0 | 47.78 | 3/12 | 37.30 | 1000-1000µs, 0 miss |
| 13 | 3 (EV3 Med POS) | POS | 1 | 50.23 | 3/12 | 30.14 | 1000-1000µs, 0 miss |
| 14 | 3 (EV3 Med NEG) | NEG | 2 | — | — | — | — |
| 15 | 3 (EV3 Med POS) | POS | 3 | — | — | — | — |

**Summary**: 0/16 cases achieved 12/12. Best: 11/12 (cases 1, 2 on EV3 Large axis 0). EV3 Large axis 1 degraded to 5-6/12. EV3 Medium axes 2: 8-9/12, axis 3: 3/12 (cases 12-13 incomplete).

## Key Findings
1. **Run-to-run variation confirmed**: EV3 Large POS was 12/12 in run 0x2609043D (cases 0,4) but dropped to 8/12 and 6/12 in this run. No axis achieved 12/12.
2. **EV3 Medium axis 3 (POS) still failing**: Cases 12,13 (axis 3 repeats 0,1) only 3/12 despite corrected POS config. Large track errors (30-37°) suggest fundamental issue — possibly motor model mismatch or stiction not fully resolved for POS direction.
3. **Core 1 timing remains excellent**: 999-1001µs period, exec max ~200µs, **0 missed ticks** across all 14 completed cases.
4. **EV3 Large axis 1 significantly worse than axis 0**: Both use same W40_K50 config but axis 1 scores 5-6/12 vs axis 0's 8-11/12. Asymmetry between motors persists.
5. **Cases 14, 15 (axis 3 repeats 2,3) did not complete**: Firmware stopped early, possibly battery gate or timeout.

## Infrastructure & Safety
- Battery: Fresh sample per case, age <250 µs, pack ≥6.5V, cells ≥3.0V (gate enforced)
- Core 1 period: 999-1001 µs; exec max 194-204 µs; missed ticks: 0
- Duty smoothness: 0.42-0.91 (EV3 Large), 0.42-0.89 (EV3 Medium)
- All motors coasted at end via `hal_motor_coast_all()`

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| autonomous_auto_20260905_132631/tuning.uf2 | 1572864 | (run `sha256sum bench/results/autonomous_auto_20260905_132631/tuning.uf2`) |
| autonomous_auto_20260905_132631/summary.csv | ~2KB | (run `sha256sum bench/results/autonomous_auto_20260905_132631/summary.csv`) |

## Updated Winning Configurations (Promoted to `motion_engine.c`)
*No changes — no 12/12 achieved in this run. Previous winning configs from run 0x2609043B retained but not reproduced.*

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large | 4.0e-4 | 5.0e-6 | 8e-7 | 0 | 0 | 0.70 | 1.0e-6 |
| EV3 Medium NEG | 2.5e-4 | 1.0e-6 | 8e-7 | 0 | 0 | 0.35 | 2.0e-6 |
| EV3 Medium POS | 2.5e-4 | 1.0e-6 | 8e-7 | 1.0e-6 | 0 | 0.35 | 2.5e-6 |

## Next Step
1. **Analyze axis 3 (EV3 Medium POS) failure** — 3/12 with 30-37° track error despite corrected config. Check if motor model calibration for unloaded EV3 Medium POS direction is still wrong, or if stiction break fix has POS-specific gap.
2. **Consider statistical approach** — Run 20+ consecutive autonomous runs with current winning configs to find 2+ consecutive 12/12 runs (current probability ~10% per axis).
3. **Alternative: EV3 Medium POS config search** — Sweep kd_vel, endpoint_kp, accel_scale for axis 3 specifically.
4. **Run next autonomous validation 0x2609043F** with any config adjustments.