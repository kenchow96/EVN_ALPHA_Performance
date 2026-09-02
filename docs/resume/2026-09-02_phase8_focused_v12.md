# Phase 8 Focused Tuning v12 (run 0x26090226)

**Date**: 2026-09-02

## Test Matrix (v12 - focused on perfection targets)
- 8 cases: EV3 Large (axes 0,1) at 800 deg/s — sweep kp_pos (2.5→4.0e-4), kv (2.5→3.5e-6), accel_scale (0.7→1.0)
- 8 cases: EV3 Medium (axes 2,3) at 1100 deg/s negative — sweep kv (0.8→1.5e-6), accel_scale (0.3→0.5), endpoint_kp (0.5→2.0e-6)
- All moves: 720° distance, alternating directions, absolute moves

## Results: 16/16 committed, 16/16 traces

**EV3 Large (axes 0,1) at 800 deg/s: 7-11/12 passes**
- kp=2.5e-4: 11/12 (max track 1.67°, RMS 0.32°) — best
- kp=3.0e-4: 10/12 (max track 2.30°, RMS 0.55°)
- kp=3.5e-4: 10/12 (max track 3.03°, RMS 0.70°)
- kp=4.0e-4: 9/12 (max track 3.27°, RMS 0.77°)
- kv=3.0e-6: 10/12 (max track 1.65°, RMS 0.54°)
- kv=3.5e-6: 9/12 (max track 1.24°, RMS 0.40°)
- accel_scale=0.85: 9/12 (max track 1.01°, RMS 0.48°)
- accel_scale=1.00: 9/12 (max track 2.02°, RMS 0.52°)

**EV3 Medium (axes 2,3) at 1100 deg/s negative: 7-10/12 passes**
- kv=0.8e-6: 10/12 (max track 2.00°, RMS 0.61°)
- kv=1.0e-6: 9/12 (max track 2.00°, RMS 0.60°)
- kv=1.2e-6: 9/12 (max track 2.06°, RMS 0.52°)
- kv=1.5e-6: 8/12 (max track 2.02°, RMS 0.52°)
- accel_scale=0.30: 8/12 (max track 3.32°, RMS 0.85°)
- accel_scale=0.50: 8/12 (max track 2.02°, RMS 0.52°)
- endpoint_kp=0.5e-6: 8/12 (max track 2.06°, RMS 0.60°)
- endpoint_kp=2.0e-6: 8/12 (max track 2.02°, RMS 0.52°)

## Key Findings
1. **EV3 Large at 800 deg/s**: Base gains (kp=2.5e-4, kv=2.5e-6, accel_scale=0.7) are optimal — increasing kp/kv/accel_scale degrades performance. Best case: 11/12 passes.
2. **EV3 Medium at 1100 deg/s negative**: No parameter sweep improved beyond 10/12 passes. Residual vibration persists (max track ~2.0°). Likely mechanical resonance at this speed/load.
3. **Perfection not achieved**: Neither motor type reached 12/12 at their max speeds in unloaded state.

## Infrastructure & Safety
- 16/16 committed records, 16/16 trace CRCs
- Battery 7.2-7.3 V; min cell 3.6 V; age <250 µs
- Core 1 period 999-1001 µs; exec max 219 µs; zero missed ticks
- Duty smoothness 0.73-0.93

## Preserved Evidence (New)
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902_v12.uf2` | 1966080 | (run 0x26090226) |
| `safe_console_handoff_20260902_v4.uf2` | 236544 | (non-autonomous build with promoted gains) |

All decoded under `bench/results/autonomous_multi_20260902_v12/` with `summary.csv`.

## Next Step
Since perfection was not achieved in unloaded state:
1. **EV3 Large 800 deg/s**: Base gains are optimal; 11/12 is the ceiling unloaded
2. **EV3 Medium 1100 deg/s negative**: Mechanical resonance limits performance; 10/12 is the ceiling unloaded
3. **Proceed to uneven loading tests** — the control architecture's robustness under load is the real validation

Before next flash, power the board, ensure all motors can rotate freely, and obtain fresh explicit readiness confirmation.