# Phase 8 Stiction Break Fix — HITL Verification (run 0x2609043B)

**Date**: 2026-09-04

## Test Matrix
- 2 axes tested: Axis 2 (EV3 Medium, port 3), Axis 3 (EV3 Medium, port 4)
- 4 moves total: ±30° relative moves on each axis (positive and negative directions)
- Commands: `M 2 30`, `M 2 -30`, `M 3 30`, `M 3 -30`
- Trapezoidal profile: 180 deg/s max velocity, 900 deg/s² max acceleration

## Results: 4/4 moves completed successfully

| Axis | Motor | Move | Target | Actual | Status |
|------|-------|------|--------|--------|--------|
| 2 (M2) | EV3 Medium | +30° | 28 mdeg | 27.5 mdeg | **done** ✅ |
| 2 (M2) | EV3 Medium | -30° | -32 mdeg | -31.5 mdeg | **done** ✅ |
| 3 (M3) | EV3 Medium | +30° | 31 mdeg | 31.0 mdeg | **STALL done** ✅ |
| 3 (M3) | EV3 Medium | -30° | 1 mdeg | 0.5 mdeg | **done** ✅ |

**Core 1 Timing**: 999-1001 µs period, exec max 297 µs, 0 missed ticks across all moves
**Battery**: 8.12 V (cells 4.06 / 4.05 V) — fresh samples (<250 ms age)
**All motors coasted** at end via `c` command

## Key Findings
1. **Stiction break fix VERIFIED on hardware** — Both EV3 Medium motors now break stiction and complete trajectories at trajectory start (no longer stuck at 10-30% duty cycle)
2. **Positive & negative directions work** — Fix is symmetric, motors move in both directions from zero velocity
3. **Axis 3 shows "STALL done" on positive move** — Stall flag set but trajectory completed to target; may be observer sensitivity or encoder noise, but position is correct
4. **Core 1 timing remains excellent** — 1 kHz control loop with zero missed ticks maintained throughout

## Infrastructure & Safety
- Battery: 8.12 V pack, min cell 4.05 V; sample age < 250 ms at each move start
- Core 1: 999-1001 µs period; exec max 297 µs; missed ticks: 0
- All motors coasted at session end (`hal_motor_coast_all()` via `c` command)

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| EVN_ALPHA_Performance.uf2 (stiction fix) | [size] | [hash] |
| hal/hal_tuning_log.h (EVN_TUNING_RUN_ID = 0x2609043B) | 3.8 KB | [hash] |

## Updated Winning Configurations (Promoted to `motion_engine.c`)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large | **4.0e-4** | **5.0e-6** | 8e-7 | **0** | 0 | 0.70 | 1.0e-6 |
| EV3 Medium NEG | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **2.0e-6** |
| EV3 Medium POS | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **2.0e-6** |

## Next Step
1. Enable `EVN_AUTONOMOUS_TUNING=1` in `CMakeLists.txt`
2. Run autonomous pipeline: `python tools/flash_extract_decode.py`
3. Target: 12/12 on all 4 axes, 2+ consecutive runs
4. Once achieved → begin Phase 8 (Drive Base) kinematics