# Session End State & Autonomous Flash Extraction Protocol

**Date**: 2026-09-03 (end of session)

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

---

## Autonomous Flash Extraction Protocol (validated 2026-09-03)

### Problem
Autonomous firmware runs silently (no USB CDC), completes cases, writes flash, reboots to BOOTSEL. `picotool info` often fails to detect BOOTSEL even when Windows sees the UF2 drive.

### Solution: PowerShell WMI Event Subscription
Use PowerShell WMI to detect drive insertion reliably:

```powershell
$Query = "SELECT * FROM Win32_VolumeChangeEvent WHERE EventType = 2"
Register-CimIndicationEvent -Query $Query -SourceIdentifier "DriveInsertedEvent" -Action {
    $DriveLetter = $EventArgs.NewEvent.DriveName
    Write-Host "[INSERTED] Drive $DriveLetter detected at $(Get-Date)" -ForegroundColor Green
}
Write-Host "Listening for drive insertions... Press Ctrl+C to stop."
while ($true) { Start-Sleep -Seconds 1 }
```

### Extraction & Decode
Once drive is detected:
```powershell
# Extract flash (no -d needed if only one RP2040)
picotool save -r 0x10F00000 0x10FF0000 -f output.uf2

# Decode
python tools/decode_tuning_flash.py output.uf2 --output bench/results/...
```

### Full Procedures
Documented in: [`docs/PROCEDURES.md`](../PROCEDURES.md) — includes PowerShell/Python quoting fixes, directory creation, CMake flag management, USB CDC recovery, run ID management, and flash extraction quick reference.

---

## Preserved Evidence (New)
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902_v14.uf2` | 1966080 | (run 0x26090228) |
| `autonomous_multi_20260902_v14_boot.txt` | ~200 | (boot log) |
| `safe_console_handoff_20260903.uf2` | 237568 | (non-autonomous build with v14 gains - built but USB CDC wedged) |

All decoded under `bench/results/autonomous_multi_20260902_v14/` with `summary.csv`.

| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260903_v15.uf2` | 1966080 | (run 0x26090229) |
| `safe_console_handoff_20260903_v2.uf2` | 237568 | (non-autonomous build with v15 gains - built but USB CDC wedged) |

All decoded under `bench/results/autonomous_multi_20260903_v15/` with `summary.csv`.