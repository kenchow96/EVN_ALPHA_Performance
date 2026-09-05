# Phase 8 Autonomous Validation Run 0x26090442 — 3rd Consecutive Run

**Date**: 2026-09-05

## Test Matrix
- 16 cases: 4 axes × 4 repeats (720° absolute moves, alternating directions)
- EV3 Large (axes 0,1): 800 deg/s max, kp_pos=4.0e-4, kp_vel=5.0e-6, kd_vel=0, endpoint_kp=1.0e-6, accel_scale=0.70
- EV3 Medium UNLOADED (axes 2,3): 1100 deg/s max, kp_pos=2.5e-4, kp_vel=1.0e-6, kd_vel=0, endpoint_kp=2.0e-6, accel_scale=0.35 (symmetric gains)
- Run ID: 0x26090442 (incremented from 0x26090441)

## Results: 16/16 committed, 16/16 traces decoded

| Case | Axis | Motor | Repeat | Dir | Pass | Score | Max Track Err | Final Err | Core1 Ticks | Period | Exec Max | Missed |
|------|------|-------|--------|-----|------|-------|---------------|-----------|-------------|--------|----------|--------|
| case_00 | 0 | EV3 Large | 0 | POS | **12/12** ✅ | 4.11 | 1.705° | 0.0° | 3820 | 1000-1000 | 199 | 0 |
| case_01 | 0 | EV3 Large | 1 | NEG | 11/12 | 2.89 | 1.7° | 0.0° | 3800 | 1000-1000 | 106 | 0 |
| case_02 | 0 | EV3 Large | 2 | POS | 5/12 | 17.27 | 3.492° | -2.062° | 3800 | 1000-1000 | 106 | 0 |
| case_03 | 0 | EV3 Large | 3 | NEG | 11/12 | 3.85 | 1.753° | 0.0° | 3820 | 1000-1000 | 198 | 0 |
| case_04 | 1 | EV3 Large | 0 | POS | 7/12 | 7.89 | 1.868° | -0.945° | 3820 | 999-1001 | 195 | 0 |
| case_05 | 1 | EV3 Large | 1 | NEG | 4/12 | 15.79 | 3.5° | 1.492° | 3820 | 999-1001 | 187 | 0 |
| case_06 | 1 | EV3 Large | 2 | POS | 8/12 | 6.03 | 1.845° | 0.149° | 3820 | 1000-1000 | 199 | 0 |
| case_07 | 1 | EV3 Large | 3 | NEG | 11/12 | 4.67 | 1.907° | 0.0° | 3820 | 1000-1000 | 202 | 0 |
| case_08 | 2 | EV3 Medium | 0 | NEG | 8/12 | 6.99 | 1.993° | -0.993° | 3820 | 1000-1000 | 202 | 0 |
| case_09 | 2 | EV3 Medium | 1 | POS | 10/12 | 3.79 | 2.541° | 0.5° | 3820 | 1000-1000 | 204 | 0 |
| case_10 | 2 | EV3 Medium | 2 | NEG | 9/12 | 7.48 | 2.0° | 0.5° | 3820 | 999-1001 | 200 | 0 |
| case_11 | 2 | EV3 Medium | 3 | POS | 8/12 | 8.51 | 1.992° | -0.992° | 3820 | 999-1001 | 189 | 0 |
| case_12 | 3 | EV3 Medium | 0 | NEG | 9/12 | 5.67 | 1.945° | -1.5° | 3820 | 1000-1000 | 202 | 0 |
| case_13 | 3 | EV3 Medium | 1 | POS | 10/12 | 3.94 | 1.399° | 1.0° | 3820 | 999-1001 | 199 | 0 |
| case_14 | 3 | EV3 Medium | 2 | NEG | 11/12 | 2.91 | 1.367° | 0.0° | 3820 | 1000-1000 | 197 | 0 |
| case_15 | 3 | EV3 Medium | 3 | POS | 9/12 | 486.51 | 1.608° | **121.211°** | 3820 | 1000-1000 | 200 | 0 |

## Key Findings

1. **Case 00 (EV3 Large axis 0 POS repeat 0): 12/12 for 3rd CONSECUTIVE RUN** — Runs 0x26090440, 0x26090441, 0x26090442 all achieved 12/12. This is the first case to achieve 3+ consecutive 12/12!

2. **EV3 Large Axis 0**: Strong on repeat 0 (POS) and repeats 1,3 (NEG) with 11-12/12. Repeat 2 (POS) drops to 5/12 with higher track error (3.492°).

3. **EV3 Large Axis 1**: Highly variable — repeat 0 (POS) 7/12, repeat 1 (NEG) 4/12, repeat 2 (POS) 8/12, repeat 3 (NEG) 11/12. NEG direction at higher repeats performs better.

4. **EV3 Medium Axis 2 (UNLOADED)**: Consistent 8-10/12 across repeats. Best is repeat 1 (POS) at 10/12. No 11/12 or 12/12 in this run.

5. **EV3 Medium Axis 3 (UNLOADED)**: Best is repeat 2 (NEG) at 11/12 (max track err 1.367°). Repeat 3 (POS) has catastrophic final error of 121.211° despite 9/12 passes — indicates late-stage instability.

6. **Core 1 Timing**: Excellent — 999-1001µs period, 106-204µs exec max, **0 missed ticks** across all 16 cases.

7. **Run-to-run variation confirmed**: Even with identical configs, results vary significantly between runs and across repeats.

## Infrastructure & Safety
- Battery: Pack ≥6.5V, cells ≥3.0V, age <250 µs (gate passed for all cases)
- Core 1: 999-1001µs period, 106-204µs exec max, 0 missed ticks (3820 ticks/case)
- All motors coasted at end (autonomous_tuning.c finish() calls coast_all())
- Firmware restored to console build (EVN_AUTONOMOUS_TUNING=0) after extraction

## Preserved Evidence

| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| tuning.uf2 | 1,966,080 | (compute with `Get-FileHash -Algorithm SHA256 bench/results/autonomous_auto_20260905_144505/tuning.uf2`) |
| summary.csv | ~2.5 KB | (compute with `Get-FileHash -Algorithm SHA256 bench/results/autonomous_auto_20260905_144505/summary.csv`) |
| flash_records.json | ~4 KB | (contains 16 committed record headers) |

## Updated Winning Configurations (Promoted to motion_engine.c)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large | **4.0e-4** | **5.0e-6** | 8e-7 | **0** | 0 | **0.70** | **1.0e-6** |
| EV3 Medium (both dirs) | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **2.0e-6** |

> Note: EV3 Medium symmetric config (kd_vel=0, endpoint_kp=2.0e-6) now used for both axes 2 and 3. Simulation validates 12/12 for both directions. Hardware shows 8-11/12 consistent but run-to-run variation prevents consistent 12/12.

## Next Step
1. **Analyze repeat-dependent degradation**: Case 02 (axis 0 POS repeat 2) drops to 5/12, case 05 (axis 1 NEG repeat 1) drops to 4/12 — investigate thermal/encoder drift or observer state accumulation.
2. **EV3 Medium improvement**: Focus on axis 2 (never reached 11/12 in this run) and axis 3 repeat 3 (catastrophic 121° final error). Consider:
   - Slightly increase endpoint_kp_vel for axis 3 POS (2.0e-6 → 2.5e-6)
   - Increase accel_scale for axis 2 (0.35 → 0.40)
   - Investigate case_15 failure mode — is it encoder wrap, observer divergence, or stiction?
3. **Run 4th consecutive validation** (0x26090443) targeting 12/12 on case_04 (axis 1 POS repeat 0) and case_12 (axis 3 NEG repeat 0) to build consecutive streaks.
4. **Consider statistical approach**: If config tuning doesn't yield consecutive 12/12 on all axes, run 20+ consecutive autonomous runs with current best configs.