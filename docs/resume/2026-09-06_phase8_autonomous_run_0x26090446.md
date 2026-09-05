# Phase 8 Autonomous Validation Run 0x26090446 — Axis 0 NEG Hunting is SYSTEMATIC

**Date**: 2026-09-06

## Purpose
Repeat validation to determine whether the run 0x26090445 **axis 0 (EV3 Large) 6/12
regression** was systematic or run-to-run noise. Clean single-session run via the
fixed pipeline.

## Results: 16/16 committed, 16/16 decoded (run_id 0x26090446 verified)

| Case | Axis | Dir | Repeat | 0x26090445 | 0x26090446 |
|------|------|-----|--------|:--------:|:--------:|
| case_00 | 0 (L) | POS | 0 | 11/12 | 11/12 |
| case_01 | 0 (L) | NEG | 1 | **6/12** | **5/12** ← hunts |
| case_02 | 0 (L) | POS | 2 | 6/12 | 11/12 |
| case_03 | 0 (L) | NEG | 3 | 11/12 | 11/12 |
| case_04 | 1 (L) | POS | 0 | **12/12** | **12/12** ✓✓ |
| case_05 | 1 (L) | NEG | 1 | 11/12 | 8/12 |
| case_06 | 1 (L) | POS | 2 | 11/12 | 11/12 |
| case_07 | 1 (L) | NEG | 3 | 11/12 | 11/12 |
| case_08 | 3 (M) | NEG | 0 | 9/12 | 8/12 |
| case_09 | 2 (M) | POS | 1 | 11/12 | 11/12 |
| case_10 | 2 (M) | NEG | 2 | 9/12 | 9/12 |
| case_11 | 2 (M) | POS | 3 | 11/12 | 11/12 |
| case_12 | 2 (M) | NEG | 0 | 10/12 | 10/12 |
| case_13 | 3 (M) | POS | 1 | 10/12 | 10/12 |
| case_14 | 3 (M) | NEG | 2 | 9/12 | 9/12 |
| case_15 | 3 (M) | POS | 3 | **12/12** | 10/12 |

## Key Findings

1. **case_01 (axis 0, NEG, repeat 1) hunting is SYSTEMATIC**: 6/12 → 5/12 across two
   clean runs, with ~3.5° max error and ~3° final error both times. Trace shows an
   endpoint **limit cycle** (duty swinging ±full, encoder oscillating past target).
   This is NOT noise.

2. **Axis 0 vs Axis 1 divergence (KEY INSIGHT)**: Axes 0 and 1 are BOTH EV3 Large
   with **identical gains** (kp=4.0e-4, kv=5.0e-6, endpoint_kp=1.0e-6, accel_scale=0.70),
   yet axis 1 (case_04) is reliably 12/12 while axis 0 (case_01) hunts. **Identical
   gains + different behavior ⇒ the root cause is a per-axis/hardware difference
   (motor 1 vs motor 2), not the gain set.** Gain tuning alone may not fix axis 0.

3. **case_04 (axis 1 POS repeat 0): 2+ consecutive 12/12** (0x26090445 + 0x26090446,
   plus fragmented 0x26090444). This is the most reliable case.

4. **case_02 (axis 0 POS repeat 2) recovered** 6/12 → 11/12 — the POS direction on
   axis 0 is fine; the hunting is specific to the NEG approach on repeat 1.

5. **case_15 (axis 3 POS repeat 3) dropped 12/12 → 10/12** — run-to-run variation,
   but no catastrophic error (stiction fix holding).

## Infrastructure & Safety
- Battery: 8.108 V pack, cells 4.040 / 4.041 V, age 431 µs (within gates)
- Core 1: 999-1001 µs period, 0 missed ticks across all 16 cases
- All motors coasted at end

## Next Step
1. **Characterize axis 0 (M1) vs axis 1 (M2) hardware difference.** Since identical
   gains diverge, inspect: encoder sign/direction config for axis 0, motor connector
   / wiring, and whether M1 has different friction/backlash. Consider a per-axis
   gain or feedforward trim for axis 0 NEG approach.
2. **Candidate lever (from SESSION_LESSONS open item #1)**: the case_01 trace shows
   the "enc climbing faster than ref → duty rail-flip" signature. For axis 0 only,
   try widening `pid.vel_window` (→60) or reducing endpoint aggression. **Validate
   on axis 0 without regressing axis 1** (they currently share the EV3 Large config).
3. Continue toward 2+ consecutive 12/12 on all 4 axes (Phase 8 gate for Drive Base).
   case_04 already at 2+ consecutive; axes 0/2/3 need consistency.
