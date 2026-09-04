# Phase 8 Hardware Validation (run 0x2609022A)

**Date**: 2026-09-04

## Test Matrix
- 16 cases from autonomous_tuning.c sweep (v12 matrix)
- EV3 Large (axes 0,1): 8 cases at 800°/s, sweeping kp_pos/kv/accel_scale
- EV3 Medium (axes 2,3): 8 cases at 1100°/s negative, sweeping kv/accel_scale/endpoint_kp
- All moves: 720° distance, alternating directions, absolute moves
- Battery pre-check: pack ≥ 6.5V, cells ≥ 3.0V, age ≤ 250ms

## Results: 16/16 committed, 16/16 traces decoded

| Case | Axis | Motor | Direction | Passed/12 | Key Failures |
|------|------|-------|-----------|-----------|--------------|
| 15 (r3) | 4 (3) | EV3 Medium | +720° (pos) | 11/12 | residual_vibration_pp=14.0° |
| 13 (r1) | 4 (3) | EV3 Medium | +720° (pos) | 11/12 | residual_vibration_pp=12.0° (est) |
| 09 (r1) | 3 (2) | EV3 Medium | +720° (pos) | 11/12 | residual_vibration_pp=14.0° (est) |
| 02 (r2) | 1 (1) | EV3 Large | +720° (pos) | 10/12 | max_track_err=2.23°, peak_vel=800.5° |
| 03 (r3) | 1 (1) | EV3 Large | -720° (neg) | 10/12 | max_track_err=2.01°, peak_vel=800.5° |
| 01 (r1) | 0 | EV3 Large | -720° (neg) | 10/12 | max_track_err=2.71° |
| 00 (r0) | 0 | EV3 Large | +720° (pos) | 10/12 | max_track_err=3.05°, peak_vel=800.5° |
| 11 (r3) | 2 (2) | EV3 Medium | -720° (neg) | 9/12 | residual_vibration, overshoot |
| 08 (r0) | 3 (3) | EV3 Medium | -720° (neg) | 9/12 | residual_vibration, overshoot |
| 14 (r2) | 2 (2) | EV3 Medium | -720° (neg) | 9/12 | residual_vibration, overshoot |
| 10 (r2) | 2 (2) | EV3 Medium | -720° (neg) | 8/12 | residual_vibration, overshoot |
| 12 (r0) | 3 (3) | EV3 Medium | -720° (neg) | 8/12 | residual_vibration, overshoot |
| 07 (r3) | 1 (1) | EV3 Large | -720° (neg) | 7/12 | max_track_err, rms_track |
| 04 (r0) | 0 | EV3 Large | +720° (pos) | 7/12 | max_track_err, peak_vel |
| 05 (r1) | 0 | EV3 Large | -720° (neg) | 7/12 | max_track_err, rms_track |
| 06 (r2) | 0 | EV3 Large | +720° (pos) | 5/12 | max_track_err, rms_track, overshoot |

**Best EV3 Large positive**: case_00 (kp=2.5e-4, kv=2.5e-6, accel_scale=0.70) — 10/12
**Best EV3 Large negative**: case_03 (kp=2.5e-4, kv=2.5e-6, accel_scale=1.00) — 10/12
**Best EV3 Medium positive**: case_15 (kp=2.0e-4, kv=1.0e-6, accel_scale=0.40, endpoint_kp=2.0e-6) — 11/12
**Best EV3 Medium negative**: case_08 (kp=2.0e-4, kv=8e-7, accel_scale=0.40) — 9/12

## Key Findings
1. **EV3 Medium positive direction (axis 3/4)**: Achieves 11/12 passes with base gains (kp=2.0e-4, kv=1.0e-6, accel_scale=0.40). Only failure is **residual_vibration_pp_deg ≈ 14°** (threshold 0.5°) — significant post-move oscillation.
2. **EV3 Large positive (axis 0/1)**: Best 10/12 with base gains (kp=2.5e-4, kv=2.5e-6, accel_scale=0.70). Failures: **max_track_err_deg > 2.0°** (3.05°) and **peak_vel slightly over vmax** (800.5° vs 800°).
3. **EV3 Large negative**: Similar to positive, best 10/12 with accel_scale=1.00 (case_03). Still tracking-limited.
4. **EV3 Medium negative**: Best only 9/12 (case_08, kv=8e-7). Worse than positive direction. Simulation showed 12/12 for both directions — hardware gap confirmed.
5. **Core 1 timing excellent**: All 16 cases show 3820 ticks, period 999-1001 us, exec max 200-216 us, **zero missed ticks**. Deterministic 1 kHz loop verified.
6. **Battery healthy**: Pack ~8.2V, cells ~4.1V, age ~440µs (well within 250ms gate).
7. **Sim-to-real gap**: Digital twin predicted 12/12 for all 4 axes; hardware shows max 11/12. Primary gaps: EV3 Medium residual vibration, EV3 Large tracking error.

## Infrastructure & Safety
- Battery: pack 8205-8221 mV; cells 4099-4110 mV; age ~440 µs
- Core 1 period: 999-1001 µs; exec max 200-216 µs; missed ticks: 0
- Duty smoothness: 0.85-0.93 range; no saturation
- All motors coasted at end of each case (auto_coast_ms=4000)

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| tuning.uf2 | 1,966,080 | (pending) |
| summary.csv | ~2 KB | (pending) |
| 16 case JSON + TXT files | ~80 KB total | (pending) |

## Updated Winning Configurations (to promote to motion_engine.c)

| Motor | kp_pos | kp_vel | ki_pos | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|-------------|-----------------|
| EV3 Large | 2.5e-4 | 2.5e-6 | 8e-7 | 0.70 (pos), 1.00 (neg) | 1.0e-6 |
| EV3 Medium | 2.0e-4 | 1.0e-6 | 8e-7 | **0.40 (both)** | **1.0e-6 (pos), needs tuning (neg)** |

## Next Step
1. **Address residual vibration on EV3 Medium**: The 14° p-p residual vibration after move completion suggests insufficient damping. Options: increase friction feedforward, add derivative term (kd_vel), or implement active damping in observer.
2. **Improve EV3 Large tracking**: max_track_err 3.05° > 2.0° threshold. May need higher kp_pos, better feedforward (kff_accel), or observer tuning.
3. **Close EV3 Medium negative gap**: Simulation achieves 12/12; hardware max 9/12. Need system ID on hardware to update digital twin.
4. **Run focused A/B sweep**: Targeted parameter sweep around best configs (kp_pos 2.0-4.0e-4 for Large, kv 0.5-2.0e-6 for Medium neg, endpoint_kp 1-3e-6).
5. **Require 2+ consecutive 12/12 autonomous runs** on hardware before proceeding to Phase 8 (drive base).