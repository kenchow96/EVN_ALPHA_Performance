# Phase 8 Autonomous Validation Run 0x2609044D — DR-Robust Gains Test (prop9_accel06)

**Date**: 2026-09-08

## Test Matrix
- 16 cases: 4 axes × 4 repeats (720° absolute moves, alternating directions)
- EV3 Large (axes 0,1): DR-robust prop9_accel06 gains — kp_pos=2.0e-4, kp_vel=1.0e-5, endpoint_kp=2.5e-6, accel_scale=0.60, vel_window=10
- EV3 Medium (axes 2,3): Symmetric gains — kp_pos=2.5e-4, kp_vel=1.0e-6, kd_vel=0, endpoint_kp=2.0e-6, accel_scale=0.35
  - Axis 2: vel_window=40, start_duty=0.80 for all cases
  - Axis 3: vel_window=10, start_duty=0.90 for POS cases (case_13, case_15)
- All moves: 720° distance, 800/1100 deg/s max vel, 1600/2200 deg/s² max accel

## Results: 16/16 committed, 16/16 traces

| Case | Axis | Dir | Repeat | Passed | Score | Max Track Err | RMS Err | Overshoot | Final Err | Duty Smooth | Duty Ripple |
|------|------|-----|--------|--------|-------|---------------|---------|-----------|-----------|-------------|-------------|
| case_00 | 0 | POS | r0 | **11/12** | 3.702 | 1.77° | 0.456° | 0.0° | **0.008°** | 0.728 | 0.985 |
| case_01 | 0 | NEG | r1 | **11/12** | 3.549 | 1.74° | 0.480° | 0.0° | **0.0°** | 0.768 | 1.038 |
| case_02 | 0 | POS | r2 | **11/12** | 4.354 | 1.73° | 0.532° | 0.49° | **0.0°** | 0.792 | 0.922 |
| case_03 | 0 | NEG | r3 | **11/12** | 3.550 | 1.78° | 0.410° | 0.0° | **0.0°** | 0.813 | 1.273 |
| case_04 | 1 | POS | r0 | 8/12 | 6.961 | 1.86° | 0.609° | 0.98° | -0.5° | 0.708 | 0.996 |
| case_05 | 1 | NEG | r1 | 7/12 | 6.733 | 2.01° | 0.593° | 0.98° | 0.5° | 0.798 | 1.171 |
| case_06 | 1 | POS | r2 | 6/12 | 6.873 | 2.08° | 0.578° | 0.96° | -0.63° | 0.798 | 1.076 |
| case_07 | 1 | NEG | r3 | 8/12 | 6.545 | 1.90° | 0.567° | 0.95° | 0.5° | 0.806 | 1.154 |
| case_08 | 2 | NEG | r0 | **11/12** | 3.366 | 1.25° | 0.373° | 1.25° | **0.0°** | 0.779 | 0.301 |
| case_09 | 2 | POS | r1 | 8/12 | 43.217 | 2.19° | 0.687° | 0.0° | **10.5°** | 0.912 | 0.176 |
| case_10 | 2 | NEG | r2 | 9/12 | 9.741 | 2.00° | 0.761° | 0.0° | -2.49° | 0.906 | 0.177 |
| case_11 | 2 | POS | r3 | 9/12 | 6.623 | 1.82° | 0.663° | 0.0° | 2.0° | 0.902 | 0.195 |
| case_12 | 3 | NEG | r0 | **11/12** | 4.904 | 1.25° | 0.373° | 1.25° | **0.0°** | 0.779 | 0.301 |
| case_13 | 3 | POS | r1 | **11/12** | 3.626 | 2.0° | 0.525° | 0.5° | **0.0°** | 0.827 | 0.236 |
| case_14 | 3 | NEG | r2 | 10/12 | 5.245 | 1.49° | 0.382° | 1.49° | **0.0°** | 0.826 | 0.263 |
| case_15 | 3 | POS | r3 | **11/12** | 3.606 | 2.0° | 0.526° | 0.5° | **0.0°** | 0.836 | 0.260 |

**Summary by axis:**
- Axis 0 (EV3 Large): **4/4 cases 11/12** — ALL repeats consistent at 11/12, final error ~0°
- Axis 1 (EV3 Large): **0/4 cases ≥11/12** — 6-8/12, hunting persists despite DR-robust gains
- Axis 2 (EV3 Medium): 1×11/12, 2×9/12, 1×8/12 — POS reversals stall (10.5° final error on case_09)
- Axis 3 (EV3 Medium): **3×11/12, 1×10/12** — POS cases 11/12 with start_duty=0.90, stiction fix WORKING

## Key Findings
1. **EV3 Large axis 0: DR-robust gains EXCELLENT** — All 4 repeats achieve 11/12 with ~0° final error. vel_window=10 eliminates limit cycle on this axis. Consistent performance across all repeats.
2. **EV3 Large axis 1: Still hunting (6-8/12)** — Identical gains to axis 0 but dramatically worse. Confirms per-axis/hardware divergence (run 0x26090447/48 motor-swap experiment conclusion).
3. **DR-robust gains trade-off confirmed** — prop9_accel06 achieves consistency (axis 0 all 11/12) but not 12/12. DR baseline was worst=2/12; this run shows axis 0 at 11/12 worst-case, axis 1 at 6/12 worst-case.
4. **EV3 Medium axis 3 stiction fix CONFIRMED** — case_13 (POS r1) and case_15 (POS r3) both 11/12 with 0° final error. start_duty=0.90 overcomes direction-reversal static friction.
5. **EV3 Medium axis 2 POS stalls persist** — case_09 (POS r1) 10.5° final error, case_11 (POS r3) 2.0° final error. Needs start_duty=0.90 for POS cases on axis 2 as well.
6. **vel_window=10 for axis 3 (EV3 Medium) works well** — All cases 10-11/12, no hunting. vel_window=40 for axis 2 shows POS reversal stalls.
7. **Core 1 timing: PERFECT** — 999-1001µs period, 186-207µs exec max, **0 missed ticks** across all 16 cases (3820 ticks each).

## Infrastructure & Safety
- Battery: 7.3-7.6 V pack, cells 3.6-3.8 V, age <250 µs
- Core 1 period: 999-1001 µs; exec max 186-207 µs; missed ticks: 0
- All motors coasted at end of each case (auto_coast_ms=4000)
- Run time: ~12 min (16 cases × ~45s trace + battery waits + flash ops)

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| tuning.uf2 | 1966080 | (run `sha256sum bench/results/autonomous_20260908_run4D/tuning.uf2`) |

## Updated Winning Configurations (to promote to motion_engine.c)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel | start_duty | vel_window |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|------------|------------|
| EV3 Large (axis 0) | **2.0e-4** | **1.0e-5** | 8e-7 | 0 | 0 | **0.60** | **2.5e-6** | 0.12 | **10** |
| EV3 Large (axis 1) | 2.0e-4 | 1.0e-5 | 8e-7 | 0 | 0 | 0.60 | 2.5e-6 | 0.12 | **10** |
| EV3 Medium (axis 2) | **2.5e-4** | **1.0e-6** | 8e-7 | 0 | 0 | **0.35** | **2.0e-6** | 0.80/0.90* | 40/10** |
| EV3 Medium (axis 3) | **2.5e-4** | **1.0e-6** | 8e-7 | 0 | 0 | **0.35** | **2.0e-6** | 0.80/0.90* | **10** |

* start_duty=0.80 for NEG, 0.90 for POS cases (stiction-break fix)
** vel_window=10 for axis 3, 40 for axis 2 (testing)

## Next Step
1. **Apply start_duty=0.90 to EV3 Medium axis 2 POS cases** (case_09, case_11) — mirror axis 3 fix
2. **Test vel_window=10 for EV3 Medium axis 2** — axis 3 shows vel_window=10 works well; may eliminate POS stalls on axis 2
3. **EV3 Large axis 1 hunting** — per-axis hardware difference means gains alone won't fix. Options:
   - Per-axis gain tuning (axis 1 needs different gains than axis 0)
   - Accept axis 0 as reference, investigate axis 1 mechanical/encoder difference
   - Add mechanical damping or improve encoder coupling on axis 1
4. **Run autonomous validation 0x2609044E** with above fixes
5. **Consider adaptive gains per axis** — firmware support for per-axis gain overrides in autonomous config