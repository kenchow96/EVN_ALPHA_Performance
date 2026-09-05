# Phase 8 Autonomous Validation Run 0x26090445 — Clean Run via Fixed Pipeline

**Date**: 2026-09-06

## Context: Pipeline Bug Fixed This Session

This run was the first to use the **fixed** `flash_extract_decode.py`. Root cause of
the prior "stale data" scare (run 0x26090444 appeared to decode as 0x26090443):

- After `picotool load -x`, the **stale BOOTSEL drive was still mounted**, so
  `wait_for_bootsel_drive()` returned immediately and extracted the *previous*
  run's flash before the new run executed.
- **Fix**: added `wait_for_bootsel_absent()` — after flashing, the pipeline now
  waits for the BOOTSEL drive to *disappear* (confirming the app booted) before
  waiting for it to *reappear* (run finished). Verified working: "BOOTSEL drive
  gone after 0.3s (app booted)".
- Diagnostic breadcrumb (`s_dbg`) confirmed `hal_tuning_log_begin()` and
  `evn_core1_pause()` both succeed; the autonomous firmware was never the problem.
  Run 0x26090444 had in fact completed in flash — it was just extracted too early.

## Test Matrix
- 16 cases: 4 axes × 4 repeats each
- EV3 Large (axes 0,1): 800 deg/s, kp=4.0e-4, kv=5.0e-6, endpoint_kp=1.0e-6, accel_scale=0.70
- EV3 Medium (axes 2,3): 1100 deg/s, kp=2.5e-4, kv=1.0e-6, kd_vel=0, endpoint_kp=2.0e-6, accel_scale=0.35 (SYMMETRIC)
- All moves: 720° absolute, alternating directions (POS/NEG/POS/NEG)

## Results: 16/16 cases committed, 16/16 traces decoded (run_id 0x26090445 verified)

| Case | Axis | Dir | Repeat | Passed | Score | MaxErr | FinalErr | Notes |
|------|------|-----|--------|--------|-------|--------|----------|-------|
| case_15 | 3 (M) | POS | 3 | **12/12** | 2.06 | 1.713° | 0.0° | Former catastrophic 121° case — now 12/12 |
| case_04 | 1 (L) | POS | 0 | **12/12** | 3.35 | 1.757° | 0.0° | 12/12 again (also 12/12 in fragmented 0x26090444) |
| case_09 | 2 (M) | POS | 1 | 11/12 | 1.84 | 1.142° | 0.008° | |
| case_11 | 2 (M) | POS | 3 | 11/12 | 2.09 | 1.311° | 0.008° | |
| case_05 | 0 (L) | NEG | 1 | 11/12 | 3.16 | 1.749° | 0.0° | |
| case_06 | 1 (L) | POS | 2 | 11/12 | 3.20 | 1.780° | 0.0° | |
| case_00 | 0 (L) | POS | 0 | 11/12 | 3.88 | 1.680° | 0.0° | |
| case_03 | 0 (L) | NEG | 3 | 11/12 | 4.07 | 1.753° | 0.0° | |
| case_07 | 1 (L) | NEG | 3 | 11/12 | 4.21 | 1.720° | 0.0° | |
| case_13 | 3 (M) | POS | 1 | 10/12 | 2.22 | 1.772° | 0.0° | |
| case_12 | 2 (M) | NEG | 0 | 10/12 | 4.64 | 1.966° | -0.5° | |
| case_14 | 3 (M) | NEG | 2 | 9/12 | 5.23 | 1.553° | -1.0° | |
| case_08 | 3 (M) | NEG | 0 | 9/12 | 5.66 | 1.500° | -0.5° | Was 12/12 in 0x26090443 |
| case_10 | 2 (M) | NEG | 2 | 9/12 | 7.80 | 2.000° | 0.5° | Was 12/12 in fragmented 0x26090444 |
| case_01 | 0 (L) | NEG | 1 | **6/12** | 17.48 | 3.493° | **3.0°** | **REGRESSION** |
| case_02 | 0 (L) | POS | 2 | **6/12** | 18.47 | 3.492° | **3.0°** | **REGRESSION** |

## Key Findings

1. **Axis 0 (EV3 Large) regression**: case_01 and case_02 dropped to 6/12 with
   ~3.0° final error and ~3.0° overshoot. Previously 8-11/12. Both are mid-sequence
   repeats (r1, r2). Hypothesis: thermal drift / mechanical, OR run-to-run variation.
   The autonomous cases use fixed per-case gains (kp=4.0e-4, kv=5.0e-6) independent
   of the motion_engine.c defaults, so the audit-remediation gain promotion did NOT
   cause this. Needs investigation (see Next Step).

2. **case_15 (axis 3 POS repeat 3) now 12/12**: the former catastrophic 121°-error
   case is fully fixed and consistent (stiction-break fix holding).

3. **case_04 (axis 1 POS repeat 0) 12/12**: consistent with fragmented 0x26090444.

4. **No axis yet has 2+ consecutive 12/12** across clean runs. Run-to-run variation
   (~10%) persists. case_08 went 12/12 (0x26090443) → 9/12 (0x26090445).

## Infrastructure & Safety
- Battery: 8.127 V pack, cells 4.054 / 4.040 V, age 434 µs (within 250 ms gate)
- Core 1: 999-1001 µs period, exec max 195-205 µs, **0 missed ticks** across all 16 cases
- All motors coasted at end (autonomous finish + console firmware)

## Winning Configurations (unchanged)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large | 4.0e-4 | 5.0e-6 | 8e-7 | 0 | 0 | 0.70 | 1.0e-6 |
| EV3 Medium (both dirs) | 2.5e-4 | 1.0e-6 | 8e-7 | 0 | 0 | 0.35 | 2.0e-6 |

## Next Step
1. **Investigate axis 0 (EV3 Large) 6/12 regression** — read the case_01/case_02
   traces (`bench/results/autonomous_auto_20260906_065753/case_01_*.txt`) to see
   whether the 3° error is stiction (not reaching target) or overshoot/oscillation.
   Check for thermal/repeat correlation (both are mid-sequence repeats).
2. **Re-run validation (0x26090446)** to determine if the axis 0 regression is
   repeatable or run-to-run noise. If it repeats, bisect against the last known-good
   axis-0 run.
3. Continue toward 2+ consecutive 12/12 on all 4 axes (Phase 8 gate for Drive Base).
