# Phase 8 DR Gain Tuning for EV3 Large Robustness (Run 0x2609044C continuation)

**Date**: 2026-09-08 (continuation)

## Test Matrix
- Domain Randomization validation across 16 cases (4 axes × 4 repeats)
- EV3 Large gains sweep: tested 10+ gain combinations with DR (5-20 draws each)
- Focused on delay+backlash combination (identified as primary degradation source)
- Full DR parameter ranges: R ±25%, friction 0.5–2×, backlash 0–2.5°, delay 0–4ms, V_max ±15%, vel noise 0–5000 mdeg/s

## Results

### DR Baseline (Current Gains)
| Config | Nominal | DR Worst | DR Mean | ≥11/12 Rate |
|--------|---------|----------|---------|-------------|
| EV3 Large (4.0e-4, 5.0e-6, 1.0e-6, 0.70) | 12/12 | 2/12 | 7.4/12 | 0-15% |
| EV3 Medium (2.5e-4, 1.0e-6, 2.0e-6, 0.35) | 12/12 | 4/12 | 8.8/12 | 35-75% |

### Gain Sweep Results (EV3 Large, 5 draws each)
| Config | kp_pos | kp_vel | endpoint_kp | accel_scale | Nominal | DR Worst | DR Mean |
|--------|--------|--------|-------------|-------------|---------|----------|---------|
| current | 4.0e-4 | 5.0e-6 | 1.0e-6 | 0.70 | 12/12 | 2/12 | 7.4/12 |
| prop1 | 3.0e-4 | 1.0e-5 | 2.0e-6 | 0.70 | 9/12 | 7/12 | 8.2/12 |
| prop2 | 2.5e-4 | 1.5e-5 | 2.5e-6 | 0.70 | 9/12 | 7/12 | 7.2/12 |
| prop3 | 3.5e-4 | 7.5e-6 | 1.5e-6 | 0.70 | 10/12 | 8/12 | 8.6/12 |
| **prop4** | 3.0e-4 | 7.5e-6 | 2.0e-6 | 0.70 | 9/12 | **8/12** | **10.2/12** |
| prop5 | 2.5e-4 | 1.0e-5 | 3.0e-6 | 0.70 | 9/12 | 6/12 | 8.0/12 |
| **prop8** | 2.5e-4 | 1.0e-5 | 2.5e-6 | 0.50 | 10/12 | **8/12** | **8.6/12** |
| **prop9** | 2.0e-4 | 1.0e-5 | 2.5e-6 | 0.50 | 10/12 | **8/12** | **8.2/12** |
| prop9_accel06 | 2.0e-4 | 1.0e-5 | 2.5e-6 | 0.60 | 10/12 | 8/12 | 8.6/12 |
| prop9_accel07 | 2.0e-4 | 1.0e-5 | 2.5e-6 | 0.70 | 10/12 | 6/12 | 8.4/12 |
| prop12 | 2.5e-4 | 1.0e-5 | 2.5e-6 | 0.70 | 9/12 | 6/12 | 9.0/12 |

### Full DR Validation (10 draws, prop9)
| Config | Direction | DR Worst | DR Mean | ≥11/12 Rate |
|--------|-----------|----------|---------|-------------|
| prop9 (2.0e-4, 1.0e-5, 2.5e-6, 0.50) | POS | 5/12 | 9.1/12 | 20% |
| prop9 (2.0e-4, 1.0e-5, 2.5e-6, 0.50) | NEG | 5/12 | 9.0/12 | 20% |
| **prop9 (combined)** | **both** | **5/12** | **9.1/12** | **20%** |
| prop9_accel06 (2.0e-4, 1.0e-5, 2.5e-6, 0.60) | POS | 8/12 | 9.4/12 | 20% |
| prop9_accel06 (2.0e-4, 1.0e-5, 2.5e-6, 0.60) | NEG | 8/12 | 9.3/12 | 30% |
| **prop9_accel06 (combined)** | **both** | **8/12** | **9.3/12** | **25%** |

### Degradation Source Analysis (delay+backlash = killer combo)
| Fixed DR Params | Current Gains Worst | Prop4 Worst | Prop8/9 Worst |
|----------------|---------------------|-------------|---------------|
| baseline (random) | 2/12 | 2/12 | 5/12 |
| high_friction (2x) | 8/12 | 8/12 | 8/12 |
| high_delay (4ms) | 3/12 | 3/12 | 6/12 |
| high_backlash (2.5°) | 8/12 | 8/12 | 8/12 |
| **delay+backlash (4ms+2.5°)** | **2/12** | **3/12** | **8/12** |
| delay+friction | 7/12 | 7/12 | 7/12 |
| all_max | 7/12 | 7/12 | 7/12 |

**Key Finding**: The **transport delay (4ms) + backlash (2.5°) combination** is the primary degradation source, reducing worst-case from 8/12 to 2/12. Gains with lower kp_pos (2.0-2.5e-4), higher kp_vel (1.0e-5), higher endpoint_kp (2.5e-6), and lower accel_scale (0.50-0.60) achieve worst=8/12 even under this worst-case combination.

## Key Findings

1. **DR Baseline Confirmed**: EV3 Large worst-case 2/12, EV3 Medium worst-case 4/12 with current gains.

2. **Primary Degradation Source Identified**: The combination of **transport delay (4ms) + gearbox backlash (2.5°)** is the "killer combo" — neither alone causes worst-case 2/12, but together they do. This matches the physical observation that EV3 Large gear trains have inherent slack + variable friction.

3. **DR-Robust Gains Found**: 
   - **prop9_accel06**: kp_pos=2.0e-4, kp_vel=1.0e-5, endpoint_kp=2.5e-6, accel_scale=0.60 → DR worst=8/12 (4× improvement over baseline)
   - Trade-off: Nominal performance drops from 12/12 → 10/12 (max track error 2.45° > 2.0° threshold, duty smoothness 0.675 < 0.7)

4. **Gain Design Principles for DR Robustness**:
   - Lower kp_pos: Less aggressive position correction → less overshoot from delayed feedback
   - Higher kp_vel: More velocity damping → suppresses oscillations from delay
   - Higher endpoint_kp: Stronger endpoint correction → overcomes backlash deadzone
   - Lower accel_scale: Slower acceleration → reduces peak velocity and overshoot

5. **Target Not Yet Met**: Promotion criterion requires worst-case ≥11/12 across DR ensemble; best achieved is 8/12. The DR parameter ranges (±25% R, 0.5-2× friction, 0-2.5° backlash, 0-4ms delay, ±15% V_max, 0-5000 mdeg/s noise) may be too wide for fixed gains to achieve ≥11/12 worst-case.

6. **EV3 Medium Already Robust**: EV3 Medium achieves 12/12 in sim with symmetric config across all vel_window values even with 5000 mdeg/s noise — very robust.

## Infrastructure & Safety
- All tests run in simulation only (no hardware deployment)
- Board remains in console firmware (EVN_AUTONOMOUS_TUNING=0)
- USB CDC functional after power cycle

## Preserved Evidence
| Artifact | Description |
|----------|-------------|
| test_*_dr_*.txt | Simulation trace files for DR validation |
| test_*_nom_*.txt | Nominal simulation trace files |

## Next Step
1. **Test EV3 Medium vel_window=10** in sim (currently vel_window=40) — priority 3 from Next Session Priorities
2. **Formalize duty slew metric** in motion_metrics.py — priority 4
3. **Test prop9_accel06 on hardware** via autonomous run 0x2609044D (after updating autonomous_tuning.c with new EV3 Large gains)
4. **Consider narrowing DR ranges** or accepting that fixed gains cannot achieve ≥11/12 worst-case with current ranges
5. **Enable backlash in sim for EV3 Medium axis 3** and sweep — priority 7