# Phase 8 Autonomous Validation Run 0x26090448 — Motor-Swap Experiment (M1↔M2)

**Date**: 2026-09-06

## Purpose
The user **swapped the motors on ports 1 and 2** before this run. Combined with
run 0x26090447 (pre-swap), this is a clean A/B test of whether the EV3 Large
endpoint hunting follows the **motor** (unit-specific) or the **axis/drive path**.

**User correction (supersedes the run-47 "shared physical cause" framing):** the
hardware is NOT faulty. The EV3 Large gear train has inherent **slack (backlash)
plus high and variable friction**, and the controller must be robust to that whole
range. Motors are currently **unloaded** and must also work under varying load.
Motors do **not** get hot unloaded (thermal hypothesis ruled out).

## Config
Baseline (uniform `vel_window=40`, the run-47 lever reverted). All gains unchanged.

## Results: 16/16 committed, 16/16 decoded (run_id 0x26090448 verified)

| Case | Axis | Dir | Repeat | 0x26090447 (pre-swap) | 0x26090448 (post-swap) |
|------|------|-----|--------|:---------------------:|:----------------------:|
| case_00 | 0 (L) | POS | 0 | 4/12 | 3/12 |
| case_01 | 0 (L) | NEG | 1 | 3/12 | 5/12 |
| case_02 | 0 (L) | POS | 2 | 4/12 | 5/12 |
| case_03 | 0 (L) | NEG | 3 | 4/12 | 5/12 |
| case_04 | 1 (L) | POS | 0 | 3/12 | 3/12 |
| case_05 | 1 (L) | NEG | 1 | 11/12 | 4/12 |
| case_06 | 1 (L) | POS | 2 | 4/12 | 5/12 |
| case_07 | 1 (L) | NEG | 3 | 4/12 | 4/12 |
| case_08 | 3 (M) | NEG | 0 | 8/12 | **12/12** ✓ |
| case_09 | 2 (M) | POS | 1 | **12/12** | 8/12 |
| case_10 | 2 (M) | NEG | 2 | 9/12 | 9/12 |
| case_11 | 2 (M) | POS | 3 | 10/12 | 8/12 |
| case_12 | 2 (M) | NEG | 0 | 8/12 | 8/12 |
| case_13 | 3 (M) | POS | 1 | 9/12 | 9/12 |
| case_14 | 3 (M) | NEG | 2 | 8/12 | 9/12 |
| case_15 | 3 (M) | POS | 3 | 9/12 | 9/12 |

Full 12/12 PASS: **1/16** (case_08, EV3 Medium axis 3 NEG repeat 0).

## Key Findings

1. **Hunting does NOT follow the motor.** After swapping M1↔M2, BOTH Large axes
   are still marginal (3-5/12). case_04 (axis 1) did NOT recover even though it
   now drives the motor that was on axis 0 — and case_00 (axis 0) did NOT improve
   even though it now drives the motor that was on axis 1. **The hunting is not
   tied to a specific motor unit or a specific axis.**

2. **Conclusion: the EV3 Large config is on the edge of stability for the whole
   population.** The gear-train slack + high/variable friction makes every Large
   axis marginal; which specific case hunts varies run-to-run (run-to-run
   variability of the friction/backlash). This is a **robustness** problem, not a
   per-unit or per-axis defect. The fix must make the controller robust across the
   full backlash/friction/load range, not tune for one unit.

3. **EV3 Medium remains the reliable platform**: case_08 12/12 (2nd time), axes
   2/3 at 8-9/12 consistently. No catastrophic errors this run (worst final err
   6.8° on case_13; the run-47 case_14 −42.5° timeout did not recur).

4. **Simulator gap confirmed**: the sim at baseline reproduces 12/12 for case_00,
   but physical run 47/48 was 3-4/12 with a sustained ±5° endpoint limit cycle and
   up to 9.4° enc/hat observer divergence. Neither 2× friction nor the (rewritten,
   now-stable) dead-zone backlash model alone reproduces the physical hunting.
   **The sim must be validated/calibrated against the physical logs before it can
   guide gain tuning** — this is now a priority.

## Infrastructure & Safety
- Battery: 7.858 V pack, cells 3.932 / 3.916 V, age 432 µs (within gates).
- Core 1: 999-1001 µs period, exec max 193 µs, **0 missed ticks** all 16 cases.
- All motors coasted at end (pipeline `finish()` → `coast_all()`).

## Simulator Work This Session
- Added CLI flags to `tools/simulate_motor.py`: `--backlash-deg`,
  `--gearbox-stiffness`, `--inertia-ratio`, `--friction-scale`, `--load-torque`.
- **Replaced the unstable two-inertia gearbox model** with a stable dead-zone
  backlash model (the old load-inertia integration ran away to thousands of
  degrees). Baseline case_00 still 12/12 (regression checked). Committed `5cd0c30`.

## Next Step
1. **Calibrate the simulator against the physical logs** so it reproduces the
   observed EV3 Large limit cycle. The missing ingredient is likely the
   *observer/plant model mismatch* under high friction + backlash (the physical
   `enc`/`hat` divergence of up to 9.4°). Candidate: per-unit friction/backlash
   distributions + a plant that diverges from the observer model the way the real
   gear train does.
2. **Then use the validated sim to find a robust EV3 Large config** that holds
   12/12 across the full backlash/friction/load envelope (not just one nominal
   unit).
3. Add a **load** dimension to the test matrix (the motors are currently unloaded;
   the controller must work under varying load).
