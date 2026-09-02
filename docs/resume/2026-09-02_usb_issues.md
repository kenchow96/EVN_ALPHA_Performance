# Safe Console Handoff & USB CDC Issues

**Date**: 2026-09-02 (continued)

## Safe Console Build with v13 Gains
- Updated `motion_engine.c`: EV3 Medium default `profile_accel_scale = 0.30f` (was 0.40f)
- Built `EVN_AUTONOMOUS_TUNING=0` console firmware successfully
- Attempted to flash via `flash_and_capture.py` and `picotool`

## USB Enumeration Issues Encountered

### Symptoms:
- After `picotool load -f build/EVN_ALPHA_Performance.uf2 -x`, device reboots but COM port becomes inaccessible
- `serial.Serial('COM7', 115200)` fails with `PermissionError(13, 'A device attached to the system is not functioning.', None, 31)`
- `picotool info` reports: "No accessible RP-series devices in BOOTSEL mode were found. RP2040 device at bus 3, address 3 appears to have a USB serial connection, so consider -f (or -F) to force reboot"
- `picotool reboot -F` executes but COM port remains unopenable
- Board appears stuck in a state where USB CDC is present but not functional

### Workarounds attempted:
- Multiple `picotool load -f ... -x` cycles
- `picotool reboot -F` to force application mode
- Power cycle via USB disconnect/reconnect (not yet tried)

### Root cause hypothesis:
The RP2040 USB stack may be wedged after autonomous tuning firmware returns to BOOTSEL and the new console firmware enumerates. The `flash_and_capture.py` tool's COM port detection races with USB re-enumeration. A full power cycle (disconnect USB, wait, reconnect) is likely required to clear the USB PHY state.

## Current Board State (End of Session)
- **Board**: Running unknown firmware state (last flash attempted but USB CDC not accessible)
- **Build**: `build/EVN_ALPHA_Performance.uf2` = non-autonomous console with v13 gains (EV3 Medium accel_scale=0.30)
- **Next run ID**: `0x26090228` (to be incremented in `hal/hal_tuning_log.h`)
- **Autonomous tuning**: Disabled in `CMakeLists.txt` (`EVN_AUTONOMOUS_TUNING=0`)

## Required for Next Session
1. **Full power cycle**: Disconnect USB cable, wait 5s, reconnect
2. **Verify board enumerates** as COM port with working CDC
3. **Flash safe console** with `picotool load -f build/EVN_ALPHA_Performance.uf2 -x`
4. **Confirm console banner** appears: `motion_init: 4 axes (M1/M2=EV3-L, M3/M4=EV3-M)`
5. **Then** proceed to uneven loading test matrix design

## Preserved Evidence (New)
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902_v13.uf2` | 1966080 | (run 0x26090227) |
| `autonomous_multi_20260902_v13_boot.txt` | ~200 | (boot log) |
| `safe_console_handoff_20260902_v5.uf2` | 236544 | (non-autonomous build with v13 gains - built but not verified on board) |

All decoded under `bench/results/autonomous_multi_20260902_v13/` with `summary.csv`.