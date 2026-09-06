# Phase 8 Autonomous Validation Run 0x26090447 — vel_window Lever FALSIFIED; Both EV3 Large Axes Hunt

**Date**: 2026-09-06

## Purpose
Test the SESSION_LESSONS open-item #1 lever for the systematic axis 0 (M1) NEG
hunting found in runs 0x26090445/46: widen the velocity differentiator window
for **axis 0 only** (`pid.vel_window` 40 → 60 = `PID_SPEED_WINDOW` max), leaving
axes 1–3 at 40 as an internal control (axis 1 / case_04 was 2× consecutive 12/12).

## Change Under Test
- [bench/autonomous_tuning.c](../../bench/autonomous_tuning.c) `AUTO_RUN_MOTION`:
  `evn_motion_set_speed_window(axis, (axis == 0) ? 60 : 40)`.
- **Recording bug found**: `prepare_header()` hardcodes `s_header.speed_window = 40u`,
  so the flash header does NOT reflect the per-axis value. The lever WAS applied
  at runtime; only the label is wrong. (Not fixed — lever reverted, see below.)

## Results: 16/16 committed, 16/16 decoded (run_id 0x26090447 verified)

| Case | Axis | Dir | Repeat | 0x26090446 | 0x26090447 |
|------|------|-----|--------|:--------:|:--------:|
| case_00 | 0 (L) | POS | 0 | 11/12 | **4/12** ✗ |
| case_01 | 0 (L) | NEG | 1 | 5/12 | **3/12** ✗ |
| case_02 | 0 (L) | POS | 2 | 11/12 | **4/12** ✗ |
| case_03 | 0 (L) | NEG | 3 | 11/12 | **4/12** ✗ |
| case_04 | 1 (L) | POS | 0 | **12/12** | **3/12** ✗✗ |
| case_05 | 1 (L) | NEG | 1 | 8/12 | 11/12 ↑ |
| case_06 | 1 (L) | POS | 2 | 11/12 | **4/12** ✗ |
| case_07 | 1 (L) | NEG | 3 | 11/12 | **4/12** ✗ |
| case_08 | 3 (M) | NEG | 0 | 8/12 | 8/12 |
| case_09 | 2 (M) | POS | 1 | 11/12 | **12/12** ✓ |
| case_10 | 2 (M) | NEG | 2 | 9/12 | 9/12 |
| case_11 | 2 (M) | POS | 3 | 11/12 | 10/12 |
| case_12 | 2 (M) | NEG | 0 | 10/12 | 8/12 |
| case_13 | 3 (M) | POS | 1 | 10/12 | 9/12 |
| case_14 | 3 (M) | NEG | 2 | 9/12 | 8/12 (−42.5° final err) |
| case_15 | 3 (M) | POS | 3 | 10/12 | 9/12 |

Full 12/12 PASS: **1/16** (case_09, EV3 Medium axis 2 POS repeat 1 — first 12/12 there).

## Key Findings

1. **The vel_window lever is FALSIFIED.** Axis 0 at vel_window=60 got WORSE
   (4,3,4,4 vs 11,5,11,11 in run 46). The wider window adds velocity-estimate lag,
   which delays the endpoint correction and *enlarges* the limit cycle. Reverted
   to uniform 40.

2. **Both EV3 Large axes collapsed TOGETHER** — including axis 1 (case_04), which
   was left at vel_window=40 and was 2× consecutive 12/12 in runs 45/46. A change
   that only touched axis 0 cannot explain axis 1's 12/12 → 3/12 collapse. **This
   is a shared physical/event cause affecting both Large motors, not a gain or
   window problem.** Medium axes (2,3) were unaffected (case_09 even improved to
   12/12).

3. **Endpoint limit cycle confirmed on trace** (case_00): duty bangs ±1000,
   encoder oscillates 715000→725500 (±5°) around the 720000 target, observer
   speed `what` swings ±160000 mdeg/s. The motor never settles. Same signature as
   the run 45/46 axis 0 NEG hunting, now on POS too.

4. **case_14 (axis 3 NEG r2) −42.5° final error is a TIMEOUT, not a crash**: trace
   ends at t=3795 ms still mid-move (enc −676492 vs target −720000, still moving
   at −256800 mdeg/s, duty only −293). Observer diverged 16° (hat −692413 vs enc
   −676492). Slow/undershooting move cut at the 760-row trace limit.

5. **EV3 Medium is now the more reliable platform**: case_09 first 12/12, axes 2/3
   at 8-11/12 while Large collapsed. The Large/Medium split (Large hunting, Medium
   stable) is the dominant run-47 signature.

## Infrastructure & Safety
- Battery: 7.994 V pack, cells 4.003 / 3.986 V, age 432 µs (within gates; only
  ~0.1 V below run 46's 8.108 V — NOT the cause).
- Core 1: 999-1001 µs period, exec max 186-204 µs, **0 missed ticks** all 16 cases.
- All motors coasted at end (pipeline `finish()` → `coast_all()`).

## Interpretation / Next Step
The simultaneous collapse of BOTH Large axes (one modified, one not) rules out the
vel_window change as the primary cause and points to a **shared physical state
change** between run 46 and run 47: motor/gearbox temperature, mechanical
settling, connector contact, or battery-contact resistance under the high-current
Large-motor load. Medium motors (lower current) were immune.

1. **REVERT confirmed** — vel_window back to uniform 40 (done).
2. **Hardware inspection (HITL)**: check M1/M2 connector seating, swap M1↔M2 at
   the connector to see if the hunting follows the motor or the port; feel for
   gearbox temperature after a run; re-seat the battery leads.
3. **Re-run baseline (vel_window=40) after a cooldown** to test whether the Large
   collapse is thermal/persistent or a one-off. If Large recovers, run 47 was an
   environmental event; if not, something durable changed in the Large drive train.
4. Consider logging per-case battery voltage *sag during the move* (not just the
   pre-move sample) — a Large-motor current spike may be drooping the rail.
