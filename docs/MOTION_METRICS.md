# Motion Performance Metrics — EVN ALPHA

Quantitative acceptance for **single-motor** control, measured from the 1 kHz
per-axis trace (`t <n>` / `d` console commands → `tools/motion_metrics.py`).
This is the bar a motor must clear before we build the drivebase on top.
Every metric names the **signal it is computed from** (per Lesson D1).

Scope mapping (your master list → what applies at our level):
- **Single rotary axis**, so *path/geometric* metrics (contouring error, curvature,
  torsion, obstacle clearance, singularity margin) and *C^k/G^k* continuity collapse
  to their 1-D forms: trajectory continuity = no step in position/velocity/accel reference.
- No torque sensor or current shunt in the loop → torque/energy metrics use the
  **observer current estimate** (`î`, 0.1 mA units) and applied voltage as proxies.
- Snap/crackle/pop are only meaningful for sub-µm nanopositioning; we track **jerk**
  (the highest derivative that matters at mm/deg scale on a geared hobby motor).

---

## 1. Trajectory-boundary compliance (reference sanity — from `ref`,`vref`)
| Metric | Definition | Acceptance |
| :--- | :--- | :--- |
| Position boundary | `ref` starts at the start angle, ends exactly at target | exact |
| Velocity boundary | `vref` == 0 at start and end of profile | exact |
| Accel boundary | accel reference returns to 0 at the boundaries (no torque step) | exact |
| Profile continuity | `vref` has no sign discontinuities / steps (C¹) | no jumps |

## 2. Limits reached (from `enc`,`vref` derived velocity/accel)
| Metric | Definition | Acceptance |
| :--- | :--- | :--- |
| Peak velocity `v_max` | max |d(enc)/dt| during move | ≤ commanded `speed` |
| Peak accel `a_max` | max |d²(enc)/dt²| (smoothed) | ≤ commanded `accel` ×1.2 |
| Peak jerk `j_max` | max |d³(enc)/dt³| (smoothed) | bounded; report (no hard cap yet) |

## 3. Tracking fidelity (from `ref` vs `enc`)
| Metric | Definition | Acceptance |
| :--- | :--- | :--- |
| Max tracking error | max |ref − enc| over the move | ≤ 2.0° (target-dependent) |
| RMS tracking error | sqrt(mean((ref−enc)²)) | ≤ 1.0° |
| Final position error | |ref − enc| after settle | ≤ 0.5° (1 encoder count) |
| Overshoot | max(enc − target) past the endpoint | ≤ 0.5° |
| Settling time `t_s` | profile-end → |err| stays < 0.5° | ≤ 300 ms |
| Residual vibration | peak-to-peak `enc` oscillation in the 500 ms after settle | ≤ 0.5° |
| Regressive instability | sign reversals of (enc − target) after settle | 0–2 (bounce allowed, no hunting) |

## 4. Control-effort quality (the "looks/sounds smooth" metrics — from `duty`)
| Metric | Definition | Acceptance |
| :--- | :--- | :--- |
| Duty saturation fraction | share of move with |duty| ≥ 0.98 | ≤ 15% |
| Duty smoothness (1− roughness) | 1 − (rms(Δduty)/ (rms(duty)+ε)) — high = smooth | ≥ 0.7 |
| Duty ripple at cruise | peak-to-peak duty during the constant-velocity phase | report (target ↓ vs baseline) |
| Limit-cycle frequency | dominant freq of duty in cruise/hold (FFT) | report |
| Saturation margin | 1 − max|duty| | ≥ 0.0 (never rail-limited for the whole move) |

## 5. Energy / thermal proxy (from observer `î` + duty)
| Metric | Definition | Acceptance |
| :--- | :--- | :--- |
| RMS current proxy `I_rms` | rms(observer current) over the move | report (thermal trend) |
| Peak current proxy | max |î| | < motor stall current |
| Energy proxy | Σ duty·(enc speed) · dt | report (efficiency trend) |

## 6. Real-time integrity (from Core 1 status)
| Metric | Definition | Acceptance |
| :--- | :--- | :--- |
| Loop rate | Core 1 tick rate | 1000 Hz ±0.1% |
| Period jitter | max |period − 1000 µs| | ≤ 5 µs |
| Exec time | max tick exec | ≤ 500 µs (50% budget) |

---

## How to run
```
# arm, move, dump (session must be running):
python tools/tune_cmd.py "t 1"; python tools/tune_cmd.py "@6 M 1 360"; python tools/tune_cmd.py "@13 d"
python tools/motion_metrics.py            # prints the full table for the last trace
python tools/motion_metrics.py --save bench/results/metrics_M1.json
```

## Baseline (to beat = "visibly better than the EVN Arduino lib")
Recorded per motor in `bench/results/metrics_*.json` and summarised in
`bench/RESULTS.md`. The Arduino reference numbers are captured on the same rig
(`bench/results/arduino_baseline_*.json`) for an apples-to-apples A/B.
