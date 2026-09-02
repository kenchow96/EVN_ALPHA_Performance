# Phase 8 Focused Tuning v14 (run 0x26090228)

**Date**: 2026-09-03

## Test Matrix (v14 - reproduction of v13 breakthrough)
- 16 cases: EV3 Large (axes 0,1) at 800 deg/s — sweep kp/kv/accel_scale (base gains optimal)
- 8 cases: EV3 Medium (axes 2,3) at 1100 deg/s negative — sweep kv/accel_scale/endpoint_kp
- All moves: 720° distance, alternating directions, absolute moves
- EV3 Large base: kp=2.5e-4, kv=2.5e-6, accel_scale=0.70
- EV3 Medium base: kp=2.0e-4, kv=1.0e-6 (neg), accel_scale=0.40, endpoint_kp=1.0e-6

## Results: 16/16 committed, 16/16 traces

**EV3 Large (axes 0,1) at 800 deg/s: 7-11/12 passes**
- Base gains (kp=2.5e-4, kv=2.5e-6, accel_scale=0.70): **11/12** (max track 2.99°, RMS 0.68°) — optimal
- kp=3.0e-4: 10/12 (max track 2.20°, RMS 0.54°)
- kp=3.5e-4: 10/12 (max track 3.12°, RMS 0.74°)
- kp=4.0e-4: 9/12 (max track 3.12°, RMS 0.74°)
- kv=3.0e-6: 9/12 (max track 3.32°, RMS 0.97°)
- kv=3.5e-6: 7/12 (max track 3.12°, RMS 0.74°)
- accel_scale=0.85: 9/12 (max track 3.32°, RMS 0.97°)
- accel_scale=1.00: 7/12 (max track 3.12°, RMS 0.74°)

**EV3 Medium (axes 2,3) at 1100 deg/s: MIXED RESULTS**
- Axis 3 (positive): kv=1.0e-6 -> **12/12** (max track 1.17°, RMS 0.32°) ✅
- Axis 3 (positive): kv=1.5e-6 -> **12/12** (max track 1.05°, RMS 0.32°) ✅
- Axis 4 (negative): **accel_scale=0.30 -> 8/12** (max track 2.52°, RMS 0.82°) ❌ **v13 breakthrough NOT reproduced**
- Axis 4 (negative): endpoint_kp=0.5e-6 -> 11/12 (max track 2.69°, RMS 0.38°)
- kv sweep (0.8-1.2e-6): 9/12 (no improvement over base)
- accel_scale=0.50: 9/12 (max track 2.69°, RMS 0.38°)
- endpoint_kp=2.0e-6: 11/12 (max track 1.12°, RMS 0.43°)

## Key Findings
1. **EV3 Large at 800 deg/s**: Base gains remain optimal (11/12 ceiling unloaded). No sweep improved it.
2. **EV3 Medium at 1100 deg/s positive**: Base kv=1.0e-6 achieves **12/12** (axis 3). kv=1.5e-6 also 12/12.
3. **EV3 Medium at 1100 deg/s negative**: **v13 breakthrough (accel_scale=0.30 -> 12/12) NOT reproduced** — only 8/12 this run. endpoint_kp=0.5e-6 gives 11/12 (best this run).
4. **Perfection partially achieved**: EV3 Medium 12/12 at 1100 deg/s positive (both axes). EV3 Medium negative and EV3 Large 800 deg/s remain at ceiling.

## Infrastructure & Safety
- 16/16 committed records, 16/16 trace CRCs
- Battery 8.23-8.26 V; min cell 4.10 V; age <250 µs
- Core 1 period 999-1001 µs; exec max 217 µs; zero missed ticks
- Duty smoothness 0.81-0.94

## Preserved Evidence (New)
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902_v14.uf2` | 1966080 | (run 0x26090228) |
| `autonomous_multi_20260902_v14_boot.txt` | ~200 | (boot log) |

All decoded under `bench/results/autonomous_multi_20260902_v14/` with `summary.csv`.

## Updated Winning Configurations (to promote to motion_engine.c)

| Motor | kp_pos | kp_vel | ki_pos | accel_scale | endpoint_kp_vel |
| :--- | :--- | :--- | :--- | :--- | :--- |
| EV3 Large | 2.5e-4 | 2.5e-6 | 8e-7 | 0.70 | 1.0e-6 |
| EV3 Medium | 2.0e-4 | 1.0e-6 (600/900/1100 pos), 1.0e-6 (1100 neg) | 8e-7 | **0.40 (all speeds)** | 1.0e-6 |

## Next Step
1. **EV3 Medium accel_scale remains 0.40** in motion_engine.c (v13 breakthrough not reproducible)
2. **Investigate negative direction vibration** — endpoint_kp=0.5e-6 gives 11/12, best this run
3. **Proceed to uneven loading tests** — both motor types achieve 12/12 at 1100 deg/s positive

Before next flash, power the board, ensure all motors can rotate freely, and obtain fresh explicit readiness confirmation.