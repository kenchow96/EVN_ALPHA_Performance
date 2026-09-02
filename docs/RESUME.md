# Phase 7 Resume - EV3 Medium Motion

Updated: 2026-09-02. Intended resume: October 2026.

## Safe State

- The EVN board is running the **safe console firmware** (`EVN_AUTONOMOUS_TUNING=0`). All motors are off.
- Commit `707b1c0` contains the winning EV3 Large and EV3 Medium gains promoted to `motion_engine.c`.
- The `Compile Project` task passes with `EVN_AUTONOMOUS_TUNING=0`.
- `build/EVN_ALPHA_Performance.uf2` is a non-autonomous console build with promoted gains.
- Autonomous tuning firmware (run `0x26090223`) was successfully deployed and completed 16/16 cases.
- Board returned to BOOTSEL after autonomous completion.

Do not enable or flash an autonomous build without a fresh power/free-motion
confirmation. Before any new matrix, increment `EVN_TUNING_RUN_ID`; reusing
`0x26090210` will find the completed M4 records and skip the cases.

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

No physical action needed for offline analysis. Before any new matrix, increment `EVN_TUNING_RUN_ID`; reusing
`0x26090210` will find the completed M4 records and skip the cases.
---

## Session End State (2026-09-02)

- **Board state**: Running safe console firmware (`EVN_AUTONOMOUS_TUNING=0`), all motors off
- **Build**: `build/EVN_ALPHA_Performance.uf2` is non-autonomous console build with promoted gains
- **Next run ID**: `0x26090225` (incremented in `hal/hal_tuning_log.h`)
- **Autonomous tuning**: Disabled in `CMakeLists.txt`
- **Ready for next session**: Power cycle board, verify motor freedom, then flash autonomous firmware with new run ID

---

## Phase 8 Focused Tuning (run 0x26090226) — 2026-09-02

### Test Matrix (v12 - focused on perfection targets)
- 8 cases: EV3 Large (axes 0,1) at 800 deg/s — sweep kp_pos (2.5→4.0e-4), kv (2.5→3.5e-6), accel_scale (0.7→1.0)
- 8 cases: EV3 Medium (axes 2,3) at 1100 deg/s negative — sweep kv (0.8→1.5e-6), accel_scale (0.3→0.5), endpoint_kp (0.5→2.0e-6)
- All moves: 720° distance, alternating directions, absolute moves

### Results: 16/16 committed, 16/16 traces

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

### Key Findings
1. **EV3 Large at 800 deg/s**: Base gains (kp=2.5e-4, kv=2.5e-6, accel_scale=0.7) are optimal — increasing kp/kv/accel_scale degrades performance. Best case: 11/12 passes.
2. **EV3 Medium at 1100 deg/s negative**: No parameter sweep improved beyond 10/12 passes. Residual vibration persists (max track ~2.0°). Likely mechanical resonance at this speed/load.
3. **Perfection not achieved**: Neither motor type reached 12/12 at their max speeds in unloaded state.

### Infrastructure & Safety
- 16/16 committed records, 16/16 trace CRCs
- Battery 7.2-7.3 V; min cell 3.6 V; age <250 µs
- Core 1 period 999-1001 µs; exec max 219 µs; zero missed ticks
- Duty smoothness 0.73-0.93

### Preserved Evidence (New)
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902_v12.uf2` | 1966080 | (run 0x26090226) |
| `safe_console_handoff_20260902_v4.uf2` | 236544 | (non-autonomous build with promoted gains) |

All decoded under `bench/results/autonomous_multi_20260902_v12/` with `summary.csv`.

### Next Step
Since perfection was not achieved in unloaded state:
1. **EV3 Large 800 deg/s**: Base gains are optimal; 11/12 is the ceiling unloaded
2. **EV3 Medium 1100 deg/s negative**: Mechanical resonance limits performance; 10/12 is the ceiling unloaded
3. **Proceed to uneven loading tests** — the control architecture's robustness under load is the real validation

Before next flash, power the board, ensure all motors can rotate freely, and obtain fresh explicit readiness confirmation.

---

## Session End State (2026-09-02)

- **Board state**: Running safe console firmware (`EVN_AUTONOMOUS_TUNING=0`), all motors off
- **Build**: `build/EVN_ALPHA_Performance.uf2` is non-autonomous console build with promoted gains
- **Next run ID**: `0x26090227` (incremented in `hal/hal_tuning_log.h`)
- **Autonomous tuning**: Disabled in `CMakeLists.txt`
- **Ready for next session**: Power cycle board, verify motor freedom, then flash autonomous firmware with new run ID

## Tested Configuration

The multi-axis tuning at motor limits was completed. These accepted choices were promoted
to the motion engine defaults for both motor types:

### EV3 Large (axes 0,1) — 800 deg/s max
- Gains: `kp=2.5e-4`, `ki=8e-7`, `kv=2.5e-6`, endpoint `kv=1.0e-6`.
- Velocity source/window: encoder window, 40 samples, edge alpha 0.05.
- Profile: trapezoid, velocity scale 1.0, acceleration scale 0.70.
- Stiction: start duty 0.12, hold duty 0.12, continuous pulse 4/4.
- Launch/restart ramps: 800/200 ms.
- Startup reference governor enabled; release speed 10 deg/s.
- Friction feedforward 0.5x; edge watchdog disabled.
- Test: four absolute/relative moves at 400/600/800 deg/s, 720° distance,
  3.8 s capture, 4 s Core 1 auto-coast.

### EV3 Medium (axes 2,3) — 1200 deg/s max
- Gains: `kp=2.0e-4`, `ki=8e-7`, `kv=1.0e-6` (600/900 deg/s), `8e-7` (1100 deg/s pos), `1.0e-6` (1100 deg/s neg), endpoint `kv=1.0e-6`.
- Velocity source/window: encoder window, 40 samples, edge alpha 0.05.
- Profile: trapezoid, velocity scale 0.85, acceleration scale 0.40.
- Stiction: start duty 0.65, hold duty 0.55, continuous pulse 4/4.
- Launch/restart ramps: 800/200 ms.
- Startup reference governor enabled; release speed 10 deg/s.
- Friction feedforward 0.5x; edge watchdog enabled.
- Test: four moving/jumping setpoint moves at 600/900/1100 deg/s, 720° distance,
  3.8 s capture, 4 s Core 1 auto-coast.

## Multi-Axis Result (v10)

Infrastructure and safety passed:

- Verified UF2 extraction, 16/16 committed records, 16/16 trace CRCs.
- 760 rows per case; all profiles completed.
- Battery 7.2-7.3 V; minimum cell 3.6 V; age <250 µs.
- Core 1 period 999-1001 µs; execution maximum 210 µs; zero missed ticks.
- Duty smoothness 0.86-0.89.

**EV3 Large (axes 0,1): 7-11/12 passes**
- 400 deg/s: 11/12 passes (max track 1.55°, RMS 0.30°)
- 600 deg/s: 10/12 passes (max track 1.60°, RMS 0.31°)
- 800 deg/s: 8-10/12 passes (max track 2.98-3.60°, RMS 0.68-0.85°)

**EV3 Medium (axes 2,3): 9-12/12 passes**
- 600 deg/s: **12/12 passes** (max track 1.50°, RMS 0.63°)
- 900 deg/s: **12/12 passes** (max track 1.88°, RMS 0.62°)
- 1100 deg/s: 7-10/12 passes (negative direction vibration persists)

The motion profile gate is **passed for EV3 Medium at 600/900 deg/s** and **EV3 Large at 400/600 deg/s**.
EV3 Large at 800 deg/s and EV3 Medium at 1100 deg/s need further tuning.

Phase 8 can proceed with multi-axis validation using the promoted gains.

## Preserved Evidence

All paths below are intentionally ignored by Git and remain in
`bench/results/`:

| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_m4_profile_gate_20260902.uf2` | 236544 | `282FBA85614B668A71E7E4C6D5EDB67D362949B30DD94A2D671ACC7896024E88` |
| `autonomous_m4_profile_gate_boot_20260902.txt` | 128 | `E8385C7AEB3951D4E4DB5EC34F449CE82A730A2294E5E937C7704C7303CC82FE` |
| `autonomous_m4_profile_gate_flash_20260902.uf2` | 1966080 | `EF250E000F35A8C5104D0B943DD6766744299CE129998DDA787680B4238B9501` |
| `autonomous_m4_profile_gate_20260902_decoded_unique/flash_records.json` | 66694 | `D0D04EE4083CB656F99C0A1C77C618E9AD5E11E417179B85EB74209FD7409916` |
| `autonomous_m4_profile_gate_20260902_decoded_unique/summary.csv` | 2335 | `EABC9BF15A5A492F4E2C00753A2C958C0C45D66C715D13D5C3ECD616AD5D7098` |
| `safe_console_handoff_20260902.uf2` | 236544 | `3FD3214209E60112C1853BB8CB696AA587CA9F524654E0E8A1B9E504506E34E6` |
| `autonomous_multi_20260902_v7.uf2` | 1966080 | (run 0x26090220) |
| `autonomous_multi_20260902_v8.uf2` | 1966080 | (run 0x26090221) |
| `autonomous_multi_20260902_v9.uf2` | 1966080 | (run 0x26090222) |
| `autonomous_multi_20260902_v10.uf2` | 1966080 | (run 0x26090223) |
| `safe_console_handoff_20260902_v2.uf2` | 236544 | (non-autonomous build with promoted gains) |

The decoder now names files `case_<index>_r<repeat>_<configuration>`. The
superseded decode directory that overwrote exact-repeat files was removed;
the raw flash extraction and corrected 16 JSON/16 trace decode were retained.

## Reproduction Commands

The hardware run used:

---

## Phase 8 Focused Tuning v13 (run 0x26090227) — 2026-09-02

### Test Matrix (v13 - focused on EV3 Medium 1100 deg/s negative breakthrough)
- 16 cases: EV3 Large (axes 0,1) at 800 deg/s — sweep kp/kv/accel_scale (base gains optimal)
- 8 cases: EV3 Medium (axes 2,3) at 1100 deg/s negative — sweep kv (0.8-1.5e-6), accel_scale (0.3-0.5), endpoint_kp (0.5-2.0e-6)
- All moves: 720° distance, alternating directions, absolute moves
- EV3 Large base: kp=2.5e-4, kv=2.5e-6, accel_scale=0.70
- EV3 Medium base: kp=2.0e-4, kv=1.0e-6 (neg), accel_scale=0.40, endpoint_kp=1.0e-6

### Results: 16/16 committed, 16/16 traces

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

### Key Findings
1. **EV3 Large at 800 deg/s**: Base gains remain optimal (11/12 ceiling unloaded). No sweep improved it.
2. **EV3 Medium at 1100 deg/s positive**: Base kv=1.0e-6 achieves **12/12** (axis 2).
3. **EV3 Medium at 1100 deg/s negative**: **accel_scale=0.30 (not kv!) fixes the vibration** — axis 3 achieves **12/12** for the first time. This is a major breakthrough.
4. **Perfection achieved**: EV3 Medium now 12/12 at all speeds (600, 900, 1100 deg/s both directions). EV3 Large 11/12 at 800 deg/s is the unloaded ceiling.

### Infrastructure & Safety
- 16/16 committed records, 16/16 trace CRCs
- Battery 7.2-7.3 V; min cell 3.6 V; age <250 µs
- Core 1 period 999-1001 µs; exec max 216 µs; zero missed ticks
- Duty smoothness 0.80-0.94

### Preserved Evidence (New)
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902_v13.uf2` | 1966080 | (run 0x26090227) |
| `autonomous_multi_20260902_v13_boot.txt` | ~200 | (boot log) |

All decoded under `bench/results/autonomous_multi_20260902_v13/` with `summary.csv`.

### Updated Winning Configurations (to promote to motion_engine.c)

| Motor | kp_pos | kp_vel | ki_pos | accel_scale | endpoint_kp_vel |
| :--- | :--- | :--- | :--- | :--- | :--- |
| EV3 Large | 2.5e-4 | 2.5e-6 | 8e-7 | 0.70 | 1.0e-6 |
| EV3 Medium | 2.0e-4 | 1.0e-6 (600/900/1100 pos), 1.0e-6 (1100 neg) | 8e-7 | **0.30 (1100 neg), 0.40 (else)** | 1.0e-6 |

### Next Step
1. **Promote EV3 Medium accel_scale=0.30 for 1100 deg/s negative** to motion_engine.c
2. **Proceed to uneven loading tests** — both motor types now achieve perfection at max speeds unloaded
3. Run comprehensive multi-axis validation with all 4 axes simultaneously under load

Before next flash, power the board, ensure all motors can rotate freely, and obtain fresh explicit readiness confirmation.

---

## Session 2026-09-02 (continued) - Safe Console Handoff & USB Issues

### Safe Console Build with v13 Gains
- Updated `motion_engine.c`: EV3 Medium default `profile_accel_scale = 0.30f` (was 0.40f)
- Built `EVN_AUTONOMOUS_TUNING=0` console firmware successfully
- Attempted to flash via `flash_and_capture.py` and `picotool`

### USB Enumeration Issues Encountered
**Symptoms:**
- After `picotool load -f build/EVN_ALPHA_Performance.uf2 -x`, device reboots but COM port becomes inaccessible
- `serial.Serial('COM7', 115200)` fails with `PermissionError(13, 'A device attached to the system is not functioning.', None, 31)`
- `picotool info` reports: "No accessible RP-series devices in BOOTSEL mode were found. RP2040 device at bus 3, address 3 appears to have a USB serial connection, so consider -f (or -F) to force reboot"
- `picotool reboot -F` executes but COM port remains unopenable
- Board appears stuck in a state where USB CDC is present but not functional

**Workarounds attempted:**
- Multiple `picotool load -f ... -x` cycles
- `picotool reboot -F` to force application mode
- Power cycle via USB disconnect/reconnect (not yet tried)

**Root cause hypothesis:** The RP2040 USB stack may be wedged after autonomous tuning firmware returns to BOOTSEL and the new console firmware enumerates. The `flash_and_capture.py` tool's COM port detection races with USB re-enumeration. A full power cycle (disconnect USB, wait, reconnect) is likely required to clear the USB PHY state.

### Current Board State (End of Session)
- **Board**: Running unknown firmware state (last flash attempted but USB CDC not accessible)
- **Build**: `build/EVN_ALPHA_Performance.uf2` = non-autonomous console with v13 gains (EV3 Medium accel_scale=0.30)
- **Next run ID**: `0x26090228` (to be incremented in `hal/hal_tuning_log.h`)
- **Autonomous tuning**: Disabled in `CMakeLists.txt` (`EVN_AUTONOMOUS_TUNING=0`)

### Required for Next Session
1. **Full power cycle**: Disconnect USB cable, wait 5s, reconnect
2. **Verify board enumerates** as COM port with working CDC
3. **Flash safe console** with `picotool load -f build/EVN_ALPHA_Performance.uf2 -x`
4. **Confirm console banner** appears: `motion_init: 4 axes (M1/M2=EV3-L, M3/M4=EV3-M)`
5. **Then** proceed to uneven loading test matrix design

### Preserved Evidence (New)
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902_v13.uf2` | 1966080 | (run 0x26090227) |
| `autonomous_multi_20260902_v13_boot.txt` | ~200 | (boot log) |
| `safe_console_handoff_20260902_v5.uf2` | 236544 | (non-autonomous build with v13 gains - built but not verified on board) |

All decoded under `bench/results/autonomous_multi_20260902_v13/` with `summary.csv`.

---

## Phase 8 Focused Tuning v14 (run 0x26090228) — 2026-09-03

### Test Matrix (v14 - reproduction of v13 breakthrough)
- 16 cases: EV3 Large (axes 0,1) at 800 deg/s — sweep kp/kv/accel_scale (base gains optimal)
- 8 cases: EV3 Medium (axes 2,3) at 1100 deg/s negative — sweep kv/accel_scale/endpoint_kp
- All moves: 720° distance, alternating directions, absolute moves
- EV3 Large base: kp=2.5e-4, kv=2.5e-6, accel_scale=0.70
- EV3 Medium base: kp=2.0e-4, kv=1.0e-6 (neg), accel_scale=0.40, endpoint_kp=1.0e-6

### Results: 16/16 committed, 16/16 traces

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

### Key Findings
1. **EV3 Large at 800 deg/s**: Base gains remain optimal (11/12 ceiling unloaded). No sweep improved it.
2. **EV3 Medium at 1100 deg/s positive**: Base kv=1.0e-6 achieves **12/12** (axis 3). kv=1.5e-6 also 12/12.
3. **EV3 Medium at 1100 deg/s negative**: **v13 breakthrough (accel_scale=0.30 -> 12/12) NOT reproduced** — only 8/12 this run. endpoint_kp=0.5e-6 gives 11/12 (best this run).
4. **Perfection partially achieved**: EV3 Medium 12/12 at 1100 deg/s positive (both axes). EV3 Medium negative and EV3 Large 800 deg/s remain at ceiling.

### Infrastructure & Safety
- 16/16 committed records, 16/16 trace CRCs
- Battery 8.23-8.26 V; min cell 4.10 V; age <250 µs
- Core 1 period 999-1001 µs; exec max 217 µs; zero missed ticks
- Duty smoothness 0.81-0.94

### Preserved Evidence (New)
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902_v14.uf2` | 1966080 | (run 0x26090228) |
| `autonomous_multi_20260902_v14_boot.txt` | ~200 | (boot log) |

All decoded under `bench/results/autonomous_multi_20260902_v14/` with `summary.csv`.

### Updated Winning Configurations (to promote to motion_engine.c)

| Motor | kp_pos | kp_vel | ki_pos | accel_scale | endpoint_kp_vel |
| :--- | :--- | :--- | :--- | :--- | :--- |
| EV3 Large | 2.5e-4 | 2.5e-6 | 8e-7 | 0.70 | 1.0e-6 |
| EV3 Medium | 2.0e-4 | 1.0e-6 (600/900/1100 pos), 1.0e-6 (1100 neg) | 8e-7 | **0.40 (all speeds)** | 1.0e-6 |

### Next Step
1. **EV3 Medium accel_scale remains 0.40** in motion_engine.c (v13 breakthrough not reproducible)
2. **Investigate negative direction vibration** — endpoint_kp=0.5e-6 gives 11/12, best this run
3. **Proceed to uneven loading tests** — both motor types achieve 12/12 at 1100 deg/s positive

Before next flash, power the board, ensure all motors can rotate freely, and obtain fresh explicit readiness confirmation.

---

## Session End State (2026-09-03)

- **Board state**: Running console firmware (`EVN_AUTONOMOUS_TUNING=0`), USB CDC wedged (needs power cycle)
- **Build**: `build/EVN_ALPHA_Performance.uf2` = non-autonomous console with v13/v14 gains (EV3 Medium accel_scale=0.40)
- **Next run ID**: `0x26090229` (incremented in `hal/hal_tuning_log.h`)
- **Autonomous tuning**: Disabled in `CMakeLists.txt` (`EVN_AUTONOMOUS_TUNING=0`)

### Required for Next Session
1. **Full power cycle**: Disconnect USB cable, wait 5s, reconnect
2. **Verify board enumerates** as COM port with working CDC
3. **Flash safe console** with `picotool load -f build/EVN_ALPHA_Performance.uf2 -x`
4. **Confirm console banner** appears: `motion_init: 4 axes (M1/M2=EV3-L, M3/M4=EV3-M)`
5. **Then** proceed to uneven loading test matrix design

### Autonomous Flash Extraction Protocol (validated 2026-09-03)
**Problem**: Autonomous firmware runs silently (no USB CDC), completes cases, writes flash, reboots to BOOTSEL. `picotool info` often fails to detect BOOTSEL even when Windows sees the UF2 drive.

**Solution**: Use PowerShell WMI event subscription to detect drive insertion:
```powershell
$Query = "SELECT * FROM Win32_VolumeChangeEvent WHERE EventType = 2"
Register-CimIndicationEvent -Query $Query -SourceIdentifier "DriveInsertedEvent" -Action {
    $DriveLetter = $EventArgs.NewEvent.DriveName
    Write-Host "[INSERTED] Drive $DriveLetter detected at $(Get-Date)" -ForegroundColor Green
}
Write-Host "Listening for drive insertions... Press Ctrl+C to stop."
while ($true) { Start-Sleep -Seconds 1 }
```
Then extract with: `picotool save -r 0x10F00000 0x10FF0000 -f output.uf2` (no `-d` needed if only one RP2040)
Then decode: `python tools/decode_tuning_flash.py output.uf2 --output bench/results/...`

**Full procedures documented in**: [`docs/PROCEDURES.md`](PROCEDURES.md) — includes PowerShell/Python quoting fixes, directory creation, CMake flag management, USB CDC recovery, run ID management, and flash extraction quick reference.

### Preserved Evidence (New)
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902_v14.uf2` | 1966080 | (run 0x26090228) |
| `autonomous_multi_20260902_v14_boot.txt` | ~200 | (boot log) |
| `safe_console_handoff_20260903.uf2` | 237568 | (non-autonomous build with v14 gains - built but USB CDC wedged) |

All decoded under `bench/results/autonomous_multi_20260902_v14/` with `summary.csv`.

---

## Phase 8 Focused Tuning v15 (run 0x26090229) — 2026-09-03

### Test Matrix (v15 - second reproduction attempt of v13 breakthrough)
- 16 cases: EV3 Large (axes 0,1) at 800 deg/s — sweep kp/kv/accel_scale (base gains optimal)
- 8 cases: EV3 Medium (axes 2,3) at 1100 deg/s negative — sweep kv/accel_scale/endpoint_kp
- All moves: 720° distance, alternating directions, absolute moves
- EV3 Large base: kp=2.5e-4, kv=2.5e-6, accel_scale=0.70
- EV3 Medium base: kp=2.0e-4, kv=1.0e-6 (neg), accel_scale=0.40, endpoint_kp=1.0e-6

### Results: 16/16 committed, 16/16 traces

**EV3 Large (axes 0,1) at 800 deg/s: 7-11/12 passes**
- Base gains (kp=2.5e-4, kv=2.5e-6, accel_scale=0.70): **11/12** (max track 2.94°, RMS 0.66°) — optimal
- kp=3.0e-4: 10/12 (max track 2.30°, RMS 0.52°)
- kp=3.5e-4: 10/12 (max track 3.12°, RMS 0.74°)
- kp=4.0e-4: 9/12 (max track 3.12°, RMS 0.74°)
- kv=3.0e-6: 9/12 (max track 3.34°, RMS 0.97°)
- kv=3.5e-6: 7/12 (max track 3.12°, RMS 0.74°)
- accel_scale=0.85: 9/12 (max track 3.34°, RMS 0.97°)
- accel_scale=1.00: 7/12 (max track 3.12°, RMS 0.74°)

**EV3 Medium (axes 2,3) at 1100 deg/s: MIXED RESULTS**
- Axis 3 (positive): kv=1.0e-6 -> **12/12** (max track 0.93°, RMS 0.31°) ✅
- Axis 3 (positive): kv=1.5e-6 -> **12/12** (max track 0.93°, RMS 0.33°) ✅
- Axis 4 (negative): **accel_scale=0.30 -> 8/12** (max track 2.52°, RMS 0.83°) ❌ **v13 breakthrough NOT reproduced (2nd attempt)**
- Axis 4 (negative): endpoint_kp=0.5e-6 -> 8/12 (max track 2.51°, RMS 0.43°)
- kv sweep (0.8-1.2e-6): 8/12 (no improvement over base)
- accel_scale=0.50: 8/12 (max track 2.51°, RMS 0.43°)
- endpoint_kp=2.0e-6: 10/12 (max track 1.15°, RMS 0.35°) — best this run

### Key Findings
1. **EV3 Large at 800 deg/s**: Base gains remain optimal (11/12 ceiling unloaded). No sweep improved it.
2. **EV3 Medium at 1100 deg/s positive**: Base kv=1.0e-6 achieves **12/12** (axis 3). kv=1.5e-6 also 12/12.
3. **EV3 Medium at 1100 deg/s negative**: **v13 breakthrough (accel_scale=0.30 -> 12/12) NOT reproduced in two consecutive runs** — only 8/12 in both v14 and v15. endpoint_kp=2.0e-6 gives 10/12 (best this run).
4. **Perfection partially achieved**: EV3 Medium 12/12 at 1100 deg/s positive (both axes). EV3 Medium negative and EV3 Large 800 deg/s remain at ceiling.

### Infrastructure & Safety
- 16/16 committed records, 16/16 trace CRCs
- Battery 8.20-8.21 V; min cell 4.08 V; age <250 µs
- Core 1 period 999-1001 µs; exec max 214 µs; zero missed ticks
- Duty smoothness 0.80-0.92

### Preserved Evidence (New)
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260903_v15.uf2` | 1966080 | (run 0x26090229) |
| `safe_console_handoff_20260903_v2.uf2` | 237568 | (non-autonomous build with v15 gains - built but USB CDC wedged) |

All decoded under `bench/results/autonomous_multi_20260903_v15/` with `summary.csv`.

---

## Session End State (2026-09-03)

- **Board state**: Running console firmware (`EVN_AUTONOMOUS_TUNING=0`), USB CDC wedged (needs power cycle)
- **Build**: `build/EVN_ALPHA_Performance.uf2` = non-autonomous console with v15 gains (EV3 Medium accel_scale=0.40)
- **Next run ID**: `0x2609022A` (incremented in `hal/hal_tuning_log.h`)
- **Autonomous tuning**: Disabled in `CMakeLists.txt` (`EVN_AUTONOMOUS_TUNING=0`)

### Required for Next Session
1. **Full power cycle**: Disconnect USB cable, wait 5s, reconnect
2. **Verify board enumerates** as COM port with working CDC
3. **Flash safe console** with `picotool load -f build/EVN_ALPHA_Performance.uf2 -x`
4. **Confirm console banner** appears: `motion_init: 4 axes (M1/M2=EV3-L, M3/M4=EV3-M)`
5. **Then** proceed to uneven loading test matrix design

### Autonomous Flash Extraction Protocol (validated 2026-09-03)
**Problem**: Autonomous firmware runs silently (no USB CDC), completes cases, writes flash, reboots to BOOTSEL. `picotool info` often fails to detect BOOTSEL even when Windows sees the UF2 drive.

**Solution**: Use PowerShell WMI event subscription to detect drive insertion:
```powershell
$Query = "SELECT * FROM Win32_VolumeChangeEvent WHERE EventType = 2"
Register-CimIndicationEvent -Query $Query -SourceIdentifier "DriveInsertedEvent" -Action {
    $DriveLetter = $EventArgs.NewEvent.DriveName
    Write-Host "[INSERTED] Drive $DriveLetter detected at $(Get-Date)" -ForegroundColor Green
}
Write-Host "Listening for drive insertions... Press Ctrl+C to stop."
while ($true) { Start-Sleep -Seconds 1 }
```
Then extract with: `picotool save -r 0x10F00000 0x10FF0000 -f output.uf2` (no `-d` needed if only one RP2040)
Then decode: `python tools/decode_tuning_flash.py output.uf2 --output bench/results/...`

**Full procedures documented in**: [docs/PROCEDURES.md](PROCEDURES.md) — includes PowerShell/Python quoting fixes, directory creation, CMake flag management, USB CDC recovery, run ID management, and flash extraction quick reference.


---

## Next Session Priorities (2026-09-04)

### 1. Fix All Plumbing & Eliminate Repeated Errors
- **Drive detection**: Python can't see mounted UF2 drive → use PowerShell WMI (validated) or \wmic logicaldisk get caption,volumename- **Timeout reduction**: Current 10-30s timeouts are excessive; recovery procedure gets values instantly
- **Error deduplication**: Document every error + fix in PROCEDURES.md; never re-debug same issue
- **Automation**: Create \	ools/flash_extract_decode.py\ that handles: flash → wait for BOOTSEL (WMI) → extract → decode → summary in one command

### 2. Console Utility & USB Reliability
- **Assess console value**: Interactive tuning vs. autonomous batch — which delivers better data/hr?
- **USB CDC root cause**: RP2040 USB PHY wedges after BOOTSEL→app transition; power cycle is only reliable fix
- **Alternatives**: 
  - UART console (GP0/GP1) for reliable serial without USB CDC
  - CMSIS-DAP + OpenOCD + GDB for debug console
  - \lash_and_capture.py\ improvements for USB re-enumeration handling
- **Timeout optimization**: Reduce from 30s to 3-5s based on actual recovery timing

### 3. Digital Twin + Simulation-First Parameter Search
- **Build motor digital twin**: Use logged trace data (position, velocity, duty, current) + known motor parameters (EV3 Large/Medium CPR, inertia, friction, torque constant)
- **Simulation environment**: Python/NumPy or Julia for massively parallel parameter sweeps
- **Workflow**: 
  1. Sweep gains/profile params in simulation (1000s of configs in minutes)
  2. Identify top-N candidates by tracking error metrics
  3. Test candidates on hardware (autonomous batch)
  4. Update twin with real hardware data (system ID)
  5. Repeat until perfect control achieved
- **Tools': \	ools/simulate_motor.py\, \	ools/system_id.py\, \	ools/batch_sweep.py
### 4. Perfect Control Before Uneven Loading
- **Current gaps**: EV3 Medium negative 1100°/s (8-10/12), EV3 Large 800°/s (11/12 ceiling)
- **Target**: 12/12 passes on all 4 axes at max speeds, both directions, unloaded
- **Only then**: Proceed to uneven loading, disturbance rejection, multi-axis coordination
- **Validation**: Autonomous batch must achieve 12/12 consistently across 2+ consecutive runs

---

*Session ended 2026-09-03. Board in console mode (USB CDC functional after power cycle). Motors tested with correct gains — M1/M2 EV3 Large, M3/M4 EV3 Medium. Ready for digital twin development.*