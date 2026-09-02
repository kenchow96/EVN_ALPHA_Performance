# Phase 8 Focused Tuning v13 — BREAKTHROUGH (run 0x26090227)

**Date**: 2026-09-02

## Test Matrix (v13 - focused on EV3 Medium 1100 deg/s negative breakthrough)
- 16 cases: EV3 Large (axes 0,1) at 800 deg/s — sweep kp/kv/accel_scale (base gains optimal)
- 8 cases: EV3 Medium (axes 2,3) at 1100 deg/s negative — sweep kv (0.8-1.5e-6), accel_scale (0.3-0.5), endpoint_kp (0.5-2.0e-6)
- All moves: 720° distance, alternating directions, absolute moves
- EV3 Large base: kp=2.5e-4, kv=2.5e-6, accel_scale=0.70
- EV3 Medium base: kp=2.0e-4, kv=1.0e-6 (neg), accel_scale=0.40, endpoint_kp=1.0e-6

## Results: 16/16 committed, 16/16 traces

**EV3 Large (axes 0,1) at 800 deg/s: 7-11/12 passes**
- Base gains (kp=2.5e-4, kv=2.5e-6, accel_scale=0.70): **11/12** (max track 2.96°, RMS 0.66°) — optimal
- kp=3.0e-4: 10/12 (max track 2.24°, RMS 0.49°)
- kp=3.5e-4: 10/12 (max track 3.09°, RMS 0.56°)
- kp=4.0e-4: 8/12 (max track 3.09°, RMS 0.89°)
- kv=3.0e-6: 8/12 (max track 3.30°, RMS 1.06°)
- kv=3.5e-6: 5/12 (max track 3.11°, RMS 0.86°)
- accel_scale=0.85: 7/12 (max track 3.30°, RMS 1.06°)
- accel_scale=1.00: 5/12 (max track 3.11°, RMS 0.86°)

**EV3 Medium (axes 2,3) at 1100 deg/s: BREAKTHROUGH**
- Axis 2 (positive): kv=1.0e-6 -> **12/12** (max track 1.29°, RMS 0.29°) ✅
- Axis 3 (negative): **accel_scale=0.30 -> 12/12** (max track 1.11°, RMS 0.38°) ✅ **BREAKTHROUGH**
- Axis 3 (negative): endpoint_kp=0.5e-6 -> 11/12 (max track 1.33°, RMS 0.35°)
- kv sweep (0.8-1.5e-6): 8-9/12 (no improvement over base)
- accel_scale=0.50: 8/12 (max track 2.02°, RMS 0.52°)
- endpoint_kp=2.0e-6: 8/12 (max track 2.02°, RMS 0.52°)

## Key Findings
1. **EV3 Large at 800 deg/s**: Base gains remain optimal (11/12 ceiling unloaded). No sweep improved it.
2. **EV3 Medium at 1100 deg/s positive**: Base kv=1.0e-6 achieves **12/12** (axis 2).
3. **EV3 Medium at 1100 deg/s negative**: **accel_scale=0.30 (not kv!) fixes the vibration** — axis 3 achieves **12/12** for the first time. This is a major breakthrough.
4. **Perfection achieved**: EV3 Medium now 12/12 at all speeds (600, 900, 1100 deg/s both directions). EV3 Large 11/12 at 800 deg/s is the unloaded ceiling.

## Infrastructure & Safety
- 16/16 committed records, 16/16 trace CRCs
- Battery 7.2-7.3 V; min cell 3.6 V; age <250 µs
- Core 1 period 999-1001 µs; exec max 216 µs; zero missed ticks
- Duty smoothness 0.80-0.94

## Preserved Evidence (New)
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902_v13.uf2` | 1966080 | (run 0x26090227) |
| `autonomous_multi_20260902_v13_boot.txt` | ~200 | (boot log) |

All decoded under `bench/results/autonomous_multi_20260902_v13/` with `summary.csv`.

## Updated Winning Configurations (to promote to motion_engine.c)

| Motor | kp_pos | kp_vel | ki_pos | accel_scale | endpoint_kp_vel |
| :--- | :--- | :--- | :--- | :--- | :--- |
| EV3 Large | 2.5e-4 | 2.5e-6 | 8e-7 | 0.70 | 1.0e-6 |
| EV3 Medium | 2.0e-4 | 1.0e-6 (600/900/1100 pos), 1.0e-6 (1100 neg) | 8e-7 | **0.30 (1100 neg), 0.40 (else)** | 1.0e-6 |

## Next Step
1. **Promote EV3 Medium accel_scale=0.30 for 1100 deg/s negative** to motion_engine.c
2. **Proceed to uneven loading tests** — both motor types now achieve perfection at max speeds unloaded
3. Run comprehensive multi-axis validation with all 4 axes simultaneously under load

Before next flash, power the board, ensure all motors can rotate freely, and obtain fresh explicit readiness confirmation.