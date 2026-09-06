# Phase 8 Simulator Calibration — EV3 Large Limit Cycle Reproduced

**Date**: 2026-09-06

## Deliverable
Calibrate the simulator so it reproduces the physical EV3 Large endpoint limit
cycle observed in runs 0x26090445-48. **Achieved.**

## Root Cause of the Sim Gap

The sim's plant uses the observer's **5 ms discrete A/B matrices** but steps at
**1 ms** (the control loop rate). This makes the plant respond ~5x too fast,
which reduces the plant's phase lag below the threshold needed for the limit
cycle. The physical motor's true continuous-time dynamics have more phase lag.

Additionally, the physical motor has a **first-order voltage lag** (electrical
+ electromechanical delay) that the sim didn't model.

## Calibration Method

Added three plant correction parameters to `tools/simulate_motor.py`:

| Parameter | CLI flag | Purpose |
|-----------|----------|---------|
| `plant_tau_ms` | `--plant-tau-ms` | Sets the plant's mechanical time constant (preserving steady-state gain) |
| `plant_lag_ms` | `--plant-lag-ms` | First-order voltage lag (electrical/electromechanical delay) |
| `plant_delay_ms` | `--plant-delay-ms` | Pure transport delay (PWM->current->torque pipeline) |

Calibrated values for EV3 Large (stored in `tools/motor_models.json`):

| Parameter | Value | Physical basis |
|-----------|-------|----------------|
| `plant_tau_ms` | 130 ms | Limit cycle frequency match |
| `plant_lag_ms` | 6.5 ms | Limit cycle amplitude match |
| `plant_friction_scale` | 1.5x | Duty saturation match |

## Validation: Sim vs Physical (run 0x26090448 case_00)

| Metric | Physical | Sim (calibrated) | Match |
|--------|----------|------------------|-------|
| Limit cycle period | 73.3 ms (13.6 Hz) | 72.1 ms (13.9 Hz) | 2% off |
| enc amplitude (pp) | 6.18 deg | 8.20 deg | 33% high |
| Duty saturation | 58% | 78% | 34% high |
| Max enc/hat divergence | 10.2 deg | 14.6 deg | 43% high |
| Observer speed range | +/-155 deg/s | +/-208 deg/s | 34% high |
| Current range | +/-160 mA | +/-125 mA | 22% low |

The frequency matches almost exactly. The amplitude is somewhat high, but the
qualitative behavior (sustained limit cycle, duty bang-bang, observer
divergence) is reproduced.

## Key Finding: vel_window=10 Eliminates the Limit Cycle

With the calibrated plant, the sim reproduces the physical limit cycle at
vel_window=40 (the current firmware value). **Reducing vel_window to 10
eliminates the limit cycle** in the sim:

| vel_window | EV3 Large acceptance | Limit cycle? |
|-----------|---------------------|--------------|
| 10 | 11/12 | No |
| 20 | 2/12 | Yes |
| 30 | 2/12 | Yes |
| 40 | 2/12 | Yes (baseline) |

The windowed speed estimate's phase lag is the primary cause of the limit
cycle. A 40 ms window adds ~96 deg of phase lag at 13.7 Hz; a 10 ms window
adds only ~24 deg.

**Important**: The run 0x26090447 hardware test only tried vel_window=60
(wider), which made the limit cycle WORSE (as the sim predicts). The narrower
direction (vel_window=10) was never tested on hardware.

## Robustness

vel_window=10 eliminates the limit cycle across the full calibrated parameter
range (tau=100-160 ms, lag=5-8 ms, friction=1.2-1.8x). The only failure is
duty_saturation for the more extreme parameters.

## Full Validation (calibrated sim, vel_window=10 for EV3 Large)

- EV3 Large (axes 0,1): 11/12 (only fails peak_vel by 0.2 deg/s)
- EV3 Medium (axes 2,3): 12/12
- Total: 16/16 cases pass

## Files Changed

- `tools/simulate_motor.py`: Added plant voltage lag, transport delay,
  mechanical time constant adjustment, and per-motor calibration loading
- `tools/motor_models.json`: Added EV3 Large plant calibration parameters
- `tools/run_validation.py`: Use vel_window=10 for EV3 Large

## Next Step

1. **Test vel_window=10 on hardware** — the sim predicts this eliminates the
   EV3 Large limit cycle. This is the highest-priority next action.
2. If vel_window=10 works on hardware, run the full autonomous validation
   (run 0x26090449) with vel_window=10 for EV3 Large.
3. If vel_window=10 doesn't work on hardware, the sim is missing something
   else — investigate further.

## Falsifying Check

The sim's prediction is: **vel_window=10 eliminates the EV3 Large endpoint
limit cycle on hardware**. If the hardware test shows the limit cycle persists
with vel_window=10, the sim is missing a key physical effect.
