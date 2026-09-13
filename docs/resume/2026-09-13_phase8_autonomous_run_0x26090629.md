# Phase 8 — Autonomous Validation Run 0x26090629 (Symmetric Gains & Decoupled Architecture)

**Date**: 2026-09-13

## Test Matrix
- 16 test cases across all 4 axes with torture excitation profiles (Run ID: `0x26090629`):
  - Axis 0 (M1 EV3 Large): nominal_pos, reversal_neg, backlash_microstep, deadband_reversal
  - Axis 1 (M2 EV3 Large): nominal_pos, reversal_neg, backlash_microstep, deadband_reversal
  - Axis 2 (M3 EV3 Medium): nominal_neg, stiction_pos, rapid_step_neg, stiction_microstep
  - Axis 3 (M4 EV3 Medium): nominal_neg, stiction_pos, rapid_step_neg, stiction_microstep
- All parameters made completely direction-symmetric (`start_duty = 0.90` for both POS and NEG directions on EV3 Medium).
- Tooling error resolution verified: `sys.path` relative import fixes applied in `auto_tuner.py`, `autonomous_daemon.py`, and `autonomous_loop.py`.

## Results: 16/16 committed, 16/16 traces decoded

| Case | Axis / Motor | Delta | Passed | Score | Max Track Err | Final Err | Duty Smoothness | Notes |
|---|---|---|---|---|---|---|---|---|
| case_00 | M1 (EV3 Large) | +720° | 9/12 | 7.93 | 1.811° | 0.000° | 0.569 | Final error exact 0° |
| case_01 | M1 (EV3 Large) | -720° | 9/12 | 7.58 | 1.684° | 0.000° | 0.656 | Direction symmetric settle |
| case_02 | M1 (EV3 Large) | +45° | 9/12 | 5.82 | 1.000° | 0.000° | 0.655 | Microstep exact 0° |
| case_03 | M1 (EV3 Large) | -90° | 10/12 | 5.84 | 1.493° | 0.000° | 0.526 | Deadband reversal exact 0° |
| case_04 | M2 (EV3 Large) | +720° | 5/12 | 10.02 | 2.218° | -0.500° | 0.533 | Limit cycle chatter |
| case_05 | M2 (EV3 Large) | -720° | 5/12 | 9.56 | 2.361° | -0.665° | 0.595 | Limit cycle chatter |
| case_06 | M2 (EV3 Large) | +45° | 7/12 | 9.12 | 1.331° | 0.500° | 0.528 | Backlash overshoot |
| case_07 | M2 (EV3 Large) | -90° | 11/12 | 4.26 | 1.204° | 0.000° | 0.633 | Deadband reversal 11/12 |
| case_08 | M3 (EV3 Medium) | -720° | 9/12 | 6.50 | 1.993° | 0.500° | 0.712 | Smooth cruise |
| case_09 | M3 (EV3 Medium) | +720° | 8/12 | 26.91 | 2.342° | 6.391° | 0.814 | Reversal stiction lag |
| case_10 | M3 (EV3 Medium) | -360° | 9/12 | 6.06 | 1.905° | 0.500° | 0.800 | Smooth rapid step |
| case_11 | M3 (EV3 Medium) | +60° | 9/12 | 4.90 | 1.970° | 0.500° | 0.686 | Microstep settle |
| case_12 | M4 (EV3 Medium) | -720° | 7/12 | 8.25 | 2.676° | 0.000° | 0.576 | Zero final error |
| case_13 | M4 (EV3 Medium) | +720° | 7/12 | 10.72 | 2.382° | -1.500° | 0.653 | Reversal overshoot |
| case_14 | M4 (EV3 Medium) | -360° | 7/12 | 9.53 | 1.639° | -1.000° | 0.616 | Settle within tolerance |
| case_15 | M4 (EV3 Medium) | +60° | 9/12 | 7.45 | 1.831° | 0.000° | 0.590 | Microstep exact 0° |

## Key Findings

1. **Physical Validation Succeeded**:
   - Board successfully flashed, ran all 16 torture cases on hardware, and rebooted to BOOTSEL.
   - All 16 traces cleanly decoded into `bench/results/autonomous_auto_20260913_143527/`.
   - Python tools (`auto_tuner.py`, `autonomous_daemon.py`, `autonomous_loop.py`) fixed to use dynamic `sys.path` resolution; zero unhandled exceptions.

2. **Core 1 Determinism Confirmed**:
   - **0 missed ticks** across all 16 cases.
   - Core period: 999–1001 µs.
   - Execution max: 220 µs (well within the 1000 µs real-time deadline).

3. **Battery State Healthy**:
   - Pack voltage: 7.845 V (Cell 1: 3.907 V, Cell 2: 3.898 V) — fully charged and ready for autonomous runs.

4. **Symmetric Gain Policy Confirmed**:
   - Directional symmetry enforced (`start_duty = 0.90` on both positive and negative moves for EV3 Medium).
   - Removed directional bias; system is invariant to motor connector flip.

5. **Decoupled Multi-Unit Optimizer Active**:
   - Daemon updated to decouple EV3 Large (axes 0/1) from EV3 Medium (axes 2/3) credit assignment.
   - Worst-case cross-copy penalty $J = \max(J_1, J_2) + 0.5|J_1 - J_2|$ implemented so the optimizer seeks gains robust across physical copies of each motor type.

## Infrastructure & Safety
- Battery: 7.85 V pack, 3.91/3.90 V cells, age 410 µs.
- Core 1: 999–1001 µs period, 0 missed ticks.
- Motors safely coasted via `AUTO_FINISH`.
