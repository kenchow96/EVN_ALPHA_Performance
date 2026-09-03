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

## 3. Autonomous Tuning Pipeline

### 3.1 One-Command Automation (Recommended)

**Problem**: Manual flash → wait → extract → decode → summarize is error-prone and slow.

**Solution**: `tools/flash_extract_decode.py` automates the entire pipeline:
1. Builds autonomous firmware (toggles CMakeLists.txt `EVN_AUTONOMOUS_TUNING=1`)
2. Flashes via picotool
3. Waits for BOOTSEL drive (uses PowerShell WMI event with VolumeName filtering)
4. Extracts tuning flash region via `picotool save`
5. Decodes with `decode_tuning_flash.py`
6. Prints summary table
7. Restores console build (`EVN_AUTONOMOUS_TUNING=0`)

```powershell
# Full autonomous run + extraction + decode + summary
python tools/flash_extract_decode.py

# Custom output directory
python tools/flash_extract_decode.py --output-dir bench/results/my_run

# Skip build (use existing UF2)
python tools/flash_extract_decode.py --no-build

# Don't restore console build after
python tools/flash_extract_decode.py --no-restore

# Custom BOOTSEL timeout
python tools/flash_extract_decode.py --timeout 180
```

**Output**: Creates timestamped directory under `bench/results/` with:
- `tuning.uf2` — raw extracted flash
- `summary.csv` — machine-readable results
- `flash_records.json` — full headers + metrics
- Summary table printed to console

### 3.2 Manual BOOTSEL Detection (Fallback)

**Problem**: `picotool info` often fails to detect BOOTSEL even when Windows sees the UF2 drive.

**Solution**: Use PowerShell WMI event subscription with VolumeName filtering for RP2040 specifically.

```powershell
# Terminal 1: Start listener (save as tools/wait_bootsel.ps1)
$Query = "SELECT * FROM Win32_VolumeChangeEvent WHERE EventType = 2"
$action = {
    $DriveLetter = $EventArgs.NewEvent.DriveName
    $vol = Get-WmiObject -Query "SELECT * FROM Win32_LogicalDisk WHERE DeviceID = '$DriveLetter'"
    if ($vol.VolumeName -eq 'RP2350' -or $vol.VolumeName -eq 'RPI-RP2') {
        Write-Host "[BOOTSEL DETECTED] Drive $DriveLetter at $(Get-Date)" -ForegroundColor Green
        $global:BootSelDrive = $DriveLetter
        Unregister-Event -SourceIdentifier "BootSelDriveEvent" -Force
    }
}
Register-CimIndicationEvent -Query $Query -SourceIdentifier "BootSelDriveEvent" -Action $action
Write-Host "Listening for RP2040 BOOTSEL drive... Press Ctrl+C to stop."
$global:BootSelDrive = $null
while ($global:BootSelDrive -eq $null) { Start-Sleep -Milliseconds 500 }
Write-Host "Drive found: $global:BootSelDrive"
```

**Usage**:
```powershell
# Terminal 1: Start listener
powershell -NoProfile -ExecutionPolicy Bypass -File tools/wait_bootsel.ps1

# Terminal 2: Build autonomous (EVN_AUTONOMOUS_TUNING=1) → Compile Project task
# Terminal 2: Flash autonomous
picotool load -f build\EVN_ALPHA_Performance.uf2 -x

# Terminal 1 will print: [BOOTSEL DETECTED] Drive D: at ...
# Drive found: D:
```

**Extract flash** (after drive detected):
```powershell
# Create output directory first!
$dir = "bench\results\autonomous_multi_YYYYMMDD_vXX"
New-Item -ItemType Directory -Path $dir -Force | Out-Null
picotool save -r 0x10F00000 0x10FF0000 -f "$dir\tuning.uf2"
# No -d needed if only one RP2040
```

**Decode**:
```powershell
python tools/decode_tuning_flash.py "$dir\tuning.uf2" --output "$dir"
```

**Restore console build**:
```powershell
# Set EVN_AUTONOMOUS_TUNING=0 in CMakeLists.txt → Compile Project task
# Power cycle board (disconnect USB, wait 5s, reconnect)
# Flash console firmware
picotool load -f build\EVN_ALPHA_Performance.uf2 -x
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

> **Note**: The automation script (`flash_extract_decode.py`) handles this toggle automatically.

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

## 9. Key File Locations

| Purpose | File |
|---------|------|
| Run ID | `hal/hal_tuning_log.h` |
| Autonomous toggle | `CMakeLists.txt` (EVN_AUTONOMOUS_TUNING) |
| Test matrix | `bench/autonomous_tuning.c` (s_cases array) |
| Decode script | `tools/decode_tuning_flash.py` |
| Automation script | `tools/flash_extract_decode.py` |
| BOOTSEL listener | `tools/wait_bootsel.ps1` |
| Results | `bench/results/autonomous_multi_*/summary.csv` |
| Flash records | `bench/results/autonomous_multi_*/flash_records.json` |
| Session logs | `docs/resume/*.md` |

---

## 10. Common Commands

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

# Full autonomous pipeline (build + flash + wait + extract + decode + summary)
python tools/flash_extract_decode.py

# Quick capture from running board
python tools/serial_capture.py --port COM7 --time 5 --send "c" --expect "COAST"
```

---

## 11. Timeout Reductions (2026-09-03)

**Problem**: `flash_and_capture.py` had excessive timeouts (2.0s post-flash sleep, 25s port wait, 0.75s stability, 1.0s settle) that slowed down the flash-capture cycle.

**Solution**: Reduced timeouts based on actual observed recovery timing (BOOTSEL drive appears within 1-2 seconds after autonomous firmware completes).

**Changes in `tools/flash_and_capture.py`**:
```python
# Before
time.sleep(2.0)                    # Post-flash wait
wait_for_port_open(baud, timeout_s=25.0, stable_s=0.75, settle_s=1.0)

# After (reduced)
time.sleep(0.5)                    # Post-flash wait
wait_for_port_open(baud, timeout_s=8.0, stable_s=0.3, settle_s=0.3)
```

**Rationale**:
- Picotool flash + reboot: ~0.5s observed
- BOOTSEL drive detection: ~1-2s after autonomous firmware completes
- COM port re-enumeration: ~1-3s after flash
- Port stability: 0.3s is sufficient (was 0.75s)
- Settle time: 0.3s is sufficient (was 1.0s)
- Polling interval: 0.05s (was 0.1s) for faster detection

**Total timeout reduction**: ~28s → ~9s (68% faster)