# Audit Remediation — AUDIT_REPORT.md Fixes (2026-09-05)

**Date**: 2026-09-05
**Trigger**: `AUDIT_REPORT.md` comprehensive audit — fix all findings autonomously.

## Scope
Addressed every actionable finding in `AUDIT_REPORT.md` (firmware defaults,
blocking delays, declarations, documentation consolidation, tooling).

## Priority 1 — Firmware (DONE, compiled clean)

### 1. Stale default gains → promoted to validated winning configs
`motion/motion_engine.c` `evn_motion_init()`:
- **EV3 Large (axes 0,1)**: `kp_pos` 2.2e-4→**4.0e-4**, `kp_vel` 2.5e-6→**5.0e-6**,
  `endpoint_kp_vel`=**1.0e-6**, `kd_vel`=0, `accel_scale`=0.70 (W40_K50).
- **EV3 Medium (axes 2,3)**: `kp_pos` 3.0e-4→**2.5e-4**, `kp_vel`=**1.0e-6**,
  `kd_vel`=**0**, `endpoint_kp_vel` 1.0e-6→**2.0e-6**, `start_duty` 0.65→**0.80**,
  `startup_release_speed_mdegs` 10000→**2000**, `accel_scale` 0.30→**0.35**
  (symmetric stiction-break config from run 0x2609043B).

### 2. Blocking delays removed (AGENTS.md Rule #1)
- `EVN_ALPHA_Performance.c`: `busy_wait_ms(100)` before `reset_usb_boot` (×2 —
  'R' command + idle-timeout) → **deferred non-blocking reboot** (`s_reboot_at`
  deadline checked in main loop after a 100 ms TX-drain window).
- `EVN_ALPHA_Performance.c`: startup `busy_wait_ms(80)` LED blink loop →
  **non-blocking boot blinker** (`s_boot_blinks_left`/`s_boot_blink_next`
  serviced in main loop).
- `hal/hal_i2c.c`: `busy_wait_us(5)` bit-bang recovery — removed with the
  function (see below).

### 3. Dead code / missing declarations
- `hal_i2c_recover_bus()`: **removed** (defined + declared but never called;
  contained the flagged `busy_wait_us` calls). Declaration removed from
  `hal_i2c.h`.
- `hal_battery_debug_regs()`: **declaration added** to `hal/hal_battery.h`
  (was defined in .c but not declared).
- `hal_button_set_callback()`: already declared in `hal_button.h`; fully wired
  (set + invoked). No change needed — audit item already satisfied.
- `hal_i2c_cached_channel()`: already declared in `hal_i2c.h`. No change needed.

## Priority 2 — Documentation & Process (DONE)
- Archived **58 stale artifact files** from repo root → `bench/results/archive/`
  (gitignored; root now clean).
- Updated `bench/RESULTS.md` with **21 missing Phase 8 autonomous run summaries**
  (v11 → run 0x26090443), sourced from `docs/resume/`.
- **Deleted** `NEXT_SESSION_PROMPT.md` (stale: claimed next run 0x26090439,
  actual 0x26090444; superseded by `docs/resume/index.md`).
- Fixed broken ref in `docs/resume/index.md`: `docs/AGENTS.md` → `../../AGENTS.md`
  (also corrected `docs/PLAN.md`→`../PLAN.md`, `docs/ASSUMPTIONS.md`→`../ASSUMPTIONS.md`).
- Fixed `docs/PLAN.md` Status Board phase numbering to match plan body:
  rogue "Phase 8" rows → **7u (Motor Model Calibration)** / **7v (Autonomous
  Validation)**; Drive Base back to **Phase 8**, Benchmarks back to **Phase 9**.

## Priority 3 — Tooling (DONE)
- **Fixed `flash_extract_decode.py` summary bug**: `print_summary()` read a
  non-existent schema (`case_index/status/kp/...`); rewrote to the real
  `summary.csv` schema (`name,passed,total,failures,score,max_track_err_deg,...`).
  Verified against `bench/results/autonomous_auto_20260905_153343/summary.csv` —
  now correctly reports case_08 as 12/12 PASS (was all-FAIL before).
- Created `tools/_common.py`: shared `find_board_port()` / `find_bootsel_drive()`
  / `RP2040_VID` (was duplicated 5×/4×). Refactored `flash_and_capture.py` and
  `serial_capture.py` to use it.
- Created `tools/requirements.txt` (`pyserial>=3.5`; everything else stdlib).
- Moved dead scripts to `tools/legacy/`: `motion_sweep.py`, `tune_cmd.py`,
  `tune_session.py`, `analyze_trace.py`, `batch_sweep.py`, `sysid_motor.py`,
  `local_commit_bot.py`.
- **Dashboard thread-safety**: added `_set_port_var()` helper that marshals
  `port_var.set()` to the Tk main thread via `root.after(0, ...)`; replaced the
  two unsafe background-thread call sites (`startup_sequence`,
  `_wait_for_cdc_port`) plus the main-thread site for consistency.

## Verification
- `Compile Project` task: **zero errors** (firmware builds clean with new gains
  + non-blocking changes).
- All edited Python tools: `py_compile` clean.
- `print_summary` fix validated against a real captured `summary.csv`.

## Hardware Validation — SKIPPED (human intervention required)
- **Board not detected**: no BOOTSEL UF2 drive (RPI-RP2), no RP2040 CDC COM port,
  no USB device with VID 2E8A present. `check_bootsel.ps1` exit 1;
  `picotool info` found no device; WMI/PnP scans empty.
- User indicated board was "plugged in and in uf2", but Windows does not see it.
  Likely needs: USB reseat / cable check / re-enter BOOTSEL / power cycle.
- **Action for user**: reconnect the EVN ALPHA in BOOTSEL (RPI-RP2 drive visible),
  then run: `python tools/flash_and_capture.py --time 105 --send s --expect "TEST COMPLETE" --log bench/results/run.txt`
  to flash the corrected firmware and run the smoke test.

## Next Step
1. User: reseat/power-cycle board into BOOTSEL; confirm RPI-RP2 drive appears.
2. Flash corrected firmware + run smoke test (command above).
3. Run autonomous validation 0x26090444 to confirm the promoted gains reproduce
   the documented 12/12 results on hardware.
