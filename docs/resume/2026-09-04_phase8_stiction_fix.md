# Phase 8 Stiction Break Fix (run 0x2609043B)

**Date**: 2026-09-04

## Test Matrix
- Fix stiction break logic in PID controller
- Update EV3 Medium parameters for symmetric gains
- Simulation validation of new logic
- Firmware flash and board verification

## Results
- ✅ Code changes committed (pid.c, simulate_motor.py, autonomous_tuning.c)
- ✅ Firmware compiled successfully
- ✅ Firmware flashed to board (board in BOOTSEL mode)
- ✅ Board responding to console commands

## Key Findings
1. **Root Cause Confirmed**: PID stiction break required `abs_vel_ref > 5000` (5 deg/s) to activate `startup_duty` ramp. Trapezoidal trajectories start at vref=0, so threshold wasn't met until ~5ms later — motor never got startup boost to overcome static friction.

2. **Fix Applied**:
   - **Firmware (pid.c)**: Lowered stiction break velocity threshold from 5000 to 1000 (1 deg/s). Added position-error-based activation (`pos_err_starting`) when `pos_err > deadzone` and `abs_vel_ref < 1000` and `abs_speed < 1000` and `displacement < 100`.
   - **Simulation (simulate_motor.py)**: Synced with firmware logic.
   - **Autonomous Tuning (autonomous_tuning.c)**: Updated EV3 Medium cases (axes 2,3):
     - `startup_duty`: 0.65 → 0.80
     - `startup_release_speed_mdegs`: 10000 → 2000
     - `endpoint_kp_vel`: 2.5e-6 (POS) / 2.0e-6 (NEG) → 2.0e-6 (both, symmetric)
     - `kd_vel`: 1.0e-6 (POS) / 0.0 (NEG) → 0.0 (both, symmetric)

3. **Falsifying Check**: Simulation with new logic runs correctly. Hardware test pending (user not available for HITL).

## Infrastructure & Safety
- Board: Console firmware (`EVN_AUTONOMOUS_TUNING=0`), USB CDC functional
- Motors: M1/M2 = EV3 Large, M3/M4 = EV3 Medium UNLOADED (new motor on port 4 per user)
- Build: `build/EVN_ALPHA_Performance.uf2` = non-autonomous console with stiction fix
- Next Run ID: `0x2609043B` (in `hal/hal_tuning_log.h`)

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `build/EVN_ALPHA_Performance.uf2` | [size] | [hash] |

## Updated Winning Configurations (to promote to motion_engine.c)
| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EV3 Large | 4.0e-4 | 5.0e-6 | 8e-7 | 0 | 0 | 0.70 | 1.0e-6 |
| EV3 Medium NEG | 2.5e-4 | 1.0e-6 | 8e-7 | **0** | 0 | 0.35 | **2.0e-6** |
| EV3 Medium POS | 2.5e-4 | 1.0e-6 | 8e-7 | **0** | 0 | 0.35 | **2.0e-6** |

## Next Step
1. **HITL Test**: User to confirm board powered on, run motor test on EV3 Medium (axes 2,3) to verify stiction break activates at trajectory start
2. **Autonomous Run**: Enable `EVN_AUTONOMOUS_TUNING=1`, run autonomous tuning with updated EV3 Medium parameters → target 12/12 on all 4 axes
3. **2+ Consecutive Runs**: Need 2+ consecutive 12/12 runs on all axes before Phase 8 (Drive Base) can proceed
4. **Simulation Loop**: Run sim/real/update sim loop until perfect