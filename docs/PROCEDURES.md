# EVN ALPHA Session Procedures

Documented 2026-09-03 to avoid repeating persistent issues.

---

## 1. PowerShell + Python JSON Quoting Issue

**Problem**: `python -c "..."` with JSON parsing fails in PowerShell due to quote escaping.

**Solution**: Write Python scripts to files first, then execute.

```powershell
# BAD - fails with quote escaping
python -c "import json; data=json.load(open('file.json')); print(data['key'])"

# GOOD - write to file first
@"
import json
with open('file.json', 'r') as f:
    data = json.load(f)
print(data['key'])
"@ | Set-Content check.py -Encoding utf8
python check.py
Remove-Item check.py
```

---

## 2. Missing Output Directory for Flash Extraction

**Problem**: `picotool save` fails silently if output directory doesn't exist.

**Solution**: Always create directory before extraction.

```powershell
$outputDir = "bench\results\autonomous_multi_20260903_v15"
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir | Out-Null }
picotool save -r 0x10F00000 0x10FF0000 -f "$outputDir\tuning.uf2"
```

---

## 3. BOOTSEL Detection Protocol (Validated 2026-09-03)

**Problem**: `picotool info` often fails to detect BOOTSEL even when Windows sees the UF2 drive.

**Solution**: Use PowerShell WMI event subscription to detect drive insertion.

```powershell
# Start listener BEFORE flashing autonomous firmware
$Query = "SELECT * FROM Win32_VolumeChangeEvent WHERE EventType = 2"
Register-CimIndicationEvent -Query $Query -SourceIdentifier "DriveInsertedEvent" -Action {
    $DriveLetter = $EventArgs.NewEvent.DriveName
    Write-Host "[INSERTED] Drive $DriveLetter detected at $(Get-Date)" -ForegroundColor Green
}
Write-Host "Listening for drive insertions... Press Ctrl+C to stop."
while ($true) { Start-Sleep -Seconds 1 }
```

**Then flash autonomous firmware**. When it completes, the listener will print the drive letter (e.g., `D:`).

**Extract flash**:
```powershell
picotool save -r 0x10F00000 0x10FF0000 -f "bench\results\...\tuning.uf2"
# No -d needed if only one RP2040
```

**Decode**:
```powershell
python tools/decode_tuning_flash.py "bench\results\...\tuning.uf2" --output "bench\results\..."
```

---

## 4. CMakeLists.txt EVN_AUTONOMOUS_TUNING Flag

**Problem**: Forgetting to toggle between console (0) and autonomous (1) builds.

**Procedure**:
- **Autonomous run**: `EVN_AUTONOMOUS_TUNING=1` → flash → wait ~10 min → board returns to BOOTSEL
- **Console build**: `EVN_AUTONOMOUS_TUNING=0` → flash → verify console banner

```cmake
# Autonomous
target_compile_definitions(EVN_ALPHA_Performance PRIVATE
    EVN_AUTONOMOUS_TUNING=1
    ...
)

# Console
target_compile_definitions(EVN_ALPHA_Performance PRIVATE
    EVN_AUTONOMOUS_TUNING=0
    ...
)
```

---

## 5. USB CDC Wedged State After Autonomous Run

**Problem**: After autonomous firmware completes and reboots to BOOTSEL, the subsequent console firmware often has wedged USB CDC (PermissionError 13).

**Solution**: Full power cycle required.

```powershell
# Required steps for next session:
1. Disconnect USB cable
2. Wait 5 seconds
3. Reconnect USB cable
4. Verify COM port enumerates with working CDC
5. Flash console firmware
6. Confirm console banner: "motion_init: 4 axes (M1/M2=EV3-L, M3/M4=EV3-M)"
```

---

## 6. Run ID Management

**Procedure**: Increment `EVN_TUNING_RUN_ID` in `hal/hal_tuning_log.h` before each autonomous run.

```c
#define EVN_TUNING_RUN_ID             0x26090229u  // Increment for each run
```

Reusing a run ID causes the firmware to skip completed cases.

---

## 7. Battery Gate Verification

**Before any motor test**: Verify fresh battery sample (age ≤ 250ms), pack ≥ 6.5V, each cell ≥ 3.0V.

The autonomous firmware enforces this, but manual verification is required for HITL tests.

---

## 8. Motor Safety - Always Coast at End

**Rule**: At the end of EVERY motor test, leave all motors in COAST state.

```c
hal_motor_coast_all();
// or
for (int i = 0; i < 4; i++) evn_motion_coast(i);
```

Never leave motors driven or braked when a test ends.

---

## 9. Flash Extraction Quick Reference

```powershell
# 1. Create output directory
$dir = "bench\results\autonomous_multi_YYYYMMDD_vXX"
New-Item -ItemType Directory -Path $dir -Force | Out-Null

# 2. Start PowerShell listener (in separate terminal)
# $Query = "SELECT * FROM Win32_VolumeChangeEvent WHERE EventType = 2"
# Register-CimIndicationEvent ...

# 3. Build autonomous (EVN_AUTONOMOUS_TUNING=1)
# Compile Project task

# 4. Flash autonomous
picotool load -f build\EVN_ALPHA_Performance.uf2 -x

# 5. Wait for listener to report drive (e.g., D:)
# 6. Extract flash
picotool save -r 0x10F00000 0x10FF0000 -f "$dir\tuning.uf2"

# 7. Decode
python tools/decode_tuning_flash.py "$dir\tuning.uf2" --output "$dir"

# 8. Build console (EVN_AUTONOMOUS_TUNING=0)
# Compile Project task

# 9. Power cycle board (disconnect USB, wait 5s, reconnect)

# 10. Flash console
picotool load -f build\EVN_ALPHA_Performance.uf2 -x

# 11. Verify console banner
```

---

## 10. Key File Locations

| Purpose | File |
|---------|------|
| Run ID | `hal/hal_tuning_log.h` |
| Autonomous toggle | `CMakeLists.txt` (EVN_AUTONOMOUS_TUNING) |
| Test matrix | `bench/autonomous_tuning.c` (s_cases array) |
| Decode script | `tools/decode_tuning_flash.py` |
| Results | `bench/results/autonomous_multi_*/summary.csv` |
| Flash records | `bench/results/autonomous_multi_*/flash_records.json` |
| Session log | `docs/RESUME.md` |

---

## 11. Common Commands

```powershell
# Check board state
picotool info

# Force reboot to BOOTSEL
picotool reboot -F

# List COM ports
python -c "import serial.tools.list_ports; [print(p) for p in serial.tools.list_ports.comports()]"

# Check git status
git status

# View diff
git diff motion/motion_engine.c
```