# EVN ALPHA Session Procedures

Documented to avoid repeating persistent issues. Organized by category for quick reference.

---

## 1. Board Detection & Power Management

### 1.1 BOOTSEL Detection (Primary: Polling)

**Tool**: `tools/check_bootsel.ps1` — simple polling check, fast and reliable.

```powershell
# Quick check if board is in BOOTSEL mode (UF2 drive mounted)
powershell -NoProfile -ExecutionPolicy Bypass -File tools/check_bootsel.ps1
# Returns: drive letter (e.g., "D:") if found, empty if not
```

**Usage**: Run this FIRST before any flash/deploy. If it returns a drive letter, the board is already in BOOTSEL mode — assume user has set everything up and proceed. Only ask user to confirm power if check returns nothing.

### 1.2 BOOTSEL Detection (Secondary: Event Subscription)

**Tool**: `tools/wait_bootsel.ps1` — WMI event subscription for state-change detection.

```powershell
# Terminal 1: Start listener BEFORE any other scripts run
powershell -NoProfile -ExecutionPolicy Bypass -File tools/wait_bootsel.ps1
```

**Important**: This is timing-dependent and unreliable as a primary method. Only use as fallback. Must be initialized **before** any flash/operation so it has time to capture the event.

### 1.3 What to Avoid

- **Do not use** `picotool info` for BOOTSEL detection — it often fails even when Windows sees the UF2 drive.

### 1.4 Board Powered Check

If neither `check_bootsel.ps1` nor `wait_bootsel.ps1` detects the board, ask the user to confirm the board is powered on and connected via USB.

---

## 2. Autonomous Tuning Pipeline

### 2.1 One-Command Automation (Recommended)

**Tool**: `tools/flash_extract_decode.py` — automates the entire pipeline.

```powershell
# Full autonomous run + extraction + decode + summary (≈15 min)
python tools/flash_extract_decode.py

# Custom output directory
python tools/flash_extract_decode.py --output-dir bench/results/my_run

# Skip build (use existing UF2)
python tools/flash_extract_decode.py --no-build

# Don't restore console build after
python tools/flash_extract_decode.py --no-restore

# Custom BOOTSEL timeout (default: 180s = 3 min for 16-case run)
python tools/flash_extract_decode.py --timeout 180
```

**Pipeline Steps**:
1. Toggles `CMakeLists.txt` `EVN_AUTONOMOUS_TUNING=1`
2. Builds via `Compile Project` task (ninja)
3. Flashes via picotool (`-fx` for reboot)
4. **Waits for BOOTSEL using `check_bootsel.ps1` polling (primary)**
5. Extracts tuning flash region via `picotool save`
6. Decodes with `decode_tuning_flash.py`
7. Prints summary table
8. Restores console build (`EVN_AUTONOMOUS_TUNING=0`)

**Output**: Creates timestamped directory under `bench/results/` with:
- `tuning.uf2` — raw extracted flash
- `summary.csv` — machine-readable results
- `flash_records.json` — full headers + metrics
- Summary table printed to console

**Time Estimate**: 16 cases × ~45s ≈ 12 min + flash/extract overhead ≈ **15 min total**. Pass `--timeout 180` (3 min buffer) to `flash_extract_decode.py`.

### 2.2 Manual BOOTSEL Detection (Fallback)

If automation fails, use the manual procedure:

```powershell
# Terminal 1: Start listener (fallback)
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

## 3. CMakeLists.txt EVN_AUTONOMOUS_TUNING Flag

**Problem**: Forgetting to toggle between console (0) and autonomous (1) builds.

**Procedure**:
- **Autonomous run**: `EVN_AUTONOMOUS_TUNING=1` → flash → wait ~15 min → board returns to BOOTSEL
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

## 4. USB CDC Wedged State After Autonomous Run

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

**Investigation**: Not yet confirmed that USB PHY is actually wedging. Check `serial_capture.py` for timing assumptions — the issue may be port enumeration timing rather than PHY state.

---

## 5. Run ID Management

**Procedure**: Increment `EVN_TUNING_RUN_ID` in `hal/hal_tuning_log.h` before each autonomous run.

```c
#define EVN_TUNING_RUN_ID             0x2609042Bu  // Increment for each run
```

**Run ID Format**: `0xYYMMDDNN` where:
- `YY` = year (26 = 2026)
- `MM` = month (09 = September)
- `DD` = day (04 = 4th)
- `NN` = sequence number for that day (2A, 2B, 2C...)

Reusing a run ID causes the firmware to skip completed cases.

---

## 6. Battery Gate Verification

Before every automated motor run, require and log a fresh battery sample:
- Age ≤ 250 ms
- Pack voltage ≥ 6.5 V
- Each cell ≥ 3.0 V

The firmware enforces this automatically and aborts if conditions not met.

---

## 7. PowerShell + Python JSON Quoting Issue

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

## 8. Missing Output Directory for Flash Extraction

**Problem**: `picotool save` fails silently if output directory doesn't exist.

**Solution**: Always create directory before extraction.

```powershell
$outputDir = "bench\results\autonomous_multi_20260903_v15"
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir | Out-Null }
picotool save -r 0x10F00000 0x10FF0000 -f "$outputDir\tuning.uf2"
```

---

## 9. Console Firmware Timeout & Heartbeat (New)

**Problem**: Console firmware blocks waiting for user input, preventing autonomous operation.

**Design** (to be implemented):
- Console firmware should timeout and return board to UF2/BOOTSEL if no host commands received within a defined window **after the last command completes** (not after last command received, as commands may take variable time to execute).
- Host can send a heartbeat message (e.g., `h`) to keep console alive.
- Host can send a reset message (e.g., `r`) to ask board to reboot into BOOTSEL mode.

**Proposed Protocol**:
- Heartbeat: Send `h` every 30s → board responds `H` + status
- Idle timeout: 120s after last command completion → auto-reboot to BOOTSEL
- Explicit reset: Send `r` → board acknowledges `R` → reboots to BOOTSEL

---

## 10. Git Workflow

- **Always commit** at every verified checkpoint (Status Board update, assumption closure, phase completion).
- **Descriptive commit messages**: Include phase, run ID, and key result (e.g., "Phase 8: run 0x2609022A - hardware validation 16/16 traces decoded").
- **Branch strategy**: Work on `main` directly for this project; no feature branches needed.
- **Pre-commit checks**: Run `Compile Project` task and verify zero errors before committing.
- **Key files to track**: `docs/PLAN.md` (Status Board), `docs/ASSUMPTIONS.md`, `docs/resume/*.md`, `hal/hal_tuning_log.h` (run ID), `CMakeLists.txt` (build config), source files under `hal/`, `motion/`, `pio/`.
- **Do not commit**: `build/` directory, `*.uf2` files, `bench/results/*` (large binary artifacts), `tools/_wait_bootsel.ps1` (temp file).

---

## 11. Common Commands Reference

```powershell
# Check board state (PRIMARY - polling)
powershell -NoProfile -ExecutionPolicy Bypass -File tools/check_bootsel.ps1

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

# Manual BOOTSEL listener (Terminal 1) - FALLBACK ONLY
powershell -NoProfile -ExecutionPolicy Bypass -File tools/wait_bootsel.ps1

# Extract flash after BOOTSEL detected
$dir = "bench\results\autonomous_multi_YYYYMMDD_vXX"
New-Item -ItemType Directory -Path $dir -Force | Out-Null
picotool save -r 0x10F00000 0x10FF0000 -f "$dir\tuning.uf2"

# Decode
python tools/decode_tuning_flash.py "$dir\tuning.uf2" --output "$dir"
```

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