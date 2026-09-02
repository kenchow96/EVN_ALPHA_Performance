# Phase 7 Resume — EV3 Medium Motion

**Date**: 2026-09-02  
**Intended Resume**: October 2026

## Safe State

- The EVN board is running the **safe console firmware** (`EVN_AUTONOMOUS_TUNING=0`). All motors are off.
- Commit `707b1c0` contains the winning EV3 Large and EV3 Medium gains promoted to `motion_engine.c`.
- The `Compile Project` task passes with `EVN_AUTONOMOUS_TUNING=0`.
- `build/EVN_ALPHA_Performance.uf2` is a non-autonomous console build with promoted gains.
- Autonomous tuning firmware (run `0x26090223`) was successfully deployed and completed 16/16 cases.
- Board returned to BOOTSEL after autonomous completion.

> **Do not enable or flash an autonomous build without a fresh power/free-motion confirmation.** Before any new matrix, increment `EVN_TUNING_RUN_ID`; reusing `0x26090210` will find the completed M4 records and skip the cases.

---

## Phase 8 Multi-Axis Validation (run 0x26090224) — 2026-09-02

### Test Matrix
- 16 cases covering 4 axes at motor limits (same as v10)
- EV3 Large (axes 0,1): 800 deg/s max, tested at 400/600/800 deg/s
- EV3 Medium (axes 2,3): 1200 deg/s max, tested at 600/900/1100 deg/s
- Test types: absolute, relative, moving setpoint, jumping setpoint
- Alternating directions to avoid zero-motion bug

### Results: 16/16 committed, 16/16 traces

**EV3 Large (axes 0,1): 7-11/12 passes**
- 400 deg/s: 11/12 passes (max track 1.67°, RMS 0.32°)
- 600 deg/s: 10/12 passes (max track 2.30°, RMS 0.55°)
- 800 deg/s: 7-10/12 passes (max track 3.03-3.32°, RMS 0.70-0.85°)

**EV3 Medium (axes 2,3): 8-10/12 passes**
- 600 deg/s: 10/12 passes (max track 1.01-1.14°, RMS 0.48-0.51°)
- 900 deg/s: 9/12 passes (max track 2.00°, RMS 0.60-0.61°)
- 1100 deg/s: 8-9/12 passes (negative direction vibration persists)

### Infrastructure & Safety
- 16/16 committed records, 16/16 trace CRCs
- Battery 7.2-7.3 V; min cell 3.6 V; age <250 µs
- Core 1 period 999-1001 µs; exec max 219 µs; zero missed ticks
- Duty smoothness 0.73-0.93

### Key Findings (consistent with v10)
1. **EV3 Large at 800 deg/s**: Still needs tuning (7-10/12 passes, max track ~3°)
2. **EV3 Medium at 1100 deg/s negative**: Residual vibration (8-9/12 passes)
3. **EV3 Large at 400/600 deg/s**: Good performance (10-11/12 passes)
4. **EV3 Medium at 600/900 deg/s**: Good performance (9-10/12 passes)

### Preserved Evidence (New)
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902_v11.uf2` | 1966080 | (run 0x26090224) |
| `autonomous_multi_20260902_v11_boot.txt` | ~200 | (boot log) |
| `safe_console_handoff_20260902_v3.uf2` | 236544 | (non-autonomous build with promoted gains) |

All decoded under `bench/results/autonomous_multi_20260902_v11/` with `summary.csv`.

### Next Step
Targeted tuning for:
1. EV3 Large at 800 deg/s (increase kp/kv further or adjust accel_scale)
2. EV3 Medium 1100 deg/s negative direction (mechanical resonance investigation)

No physical action needed for offline analysis. Before any new matrix, increment `EVN_TUNING_RUN_ID`; reusing `0x26090210` will find the completed M4 records and skip the cases.

---

## Session End State (2026-09-02)

- **Board state**: Running safe console firmware (`EVN_AUTONOMOUS_TUNING=0`), all motors off
- **Build**: `build/EVN_ALPHA_Performance.uf2` is non-autonomous console build with promoted gains
- **Next run ID**: `0x26090225` (incremented in `hal/hal_tuning_log.h`)
- **Autonomous tuning**: Disabled in `CMakeLists.txt`
- **Ready for next session**: Power cycle board, verify motor freedom, then flash autonomous firmware with new run ID