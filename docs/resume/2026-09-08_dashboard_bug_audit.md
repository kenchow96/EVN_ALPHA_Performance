# Dashboard Bug Audit — Firmware-Grounded Root Causes

**Date**: 2026-09-08

Extracted from `index.md` (2026-09-09) to keep the canonical index lean. All root causes below were confirmed by reading every console command handler in `EVN_ALPHA_Performance.c` (lines 305–585) and matching against `tools/evn_dashboard.py` parsers. **Earlier guesses are superseded.** Fix in priority order; each fix is independent.

## Symptom → Root Cause Table

| # | Symptom | Verified root cause | Fix location |
|---|---------|--------------------|--------------|
| 1 | White box after Motor 4 in dark mode | `tk.Canvas` in Motors/Servos tabs never recolored — `toggle_dark_mode()` only updates `console_output` + `i2c_results`, not the two scroll canvases | Dashboard: add `canvas.configure(bg=...)` for both tab canvases in `toggle_dark_mode()` |
| 2 | Servo pulse shows port number | **NOT reproducible from current code.** Parser verified correct (`>> Servo %d pulse=%lu us` → `servo_pulses[idx]` → `pulse_label`). Only 2 writes to `servo_pulses`: init `[1500×4]` + correct parser. Two separate labels exist: `pulse_label` (status, top) and `pulse_display` (slider, live). Likely stale observation from before the `E n 0` write-as-query fix, OR user reading the slider's `pulse_display`. **Action: re-observe on current build; if still wrong, capture which label + what was clicked.** | Re-test on hardware; no code change indicated yet |
| 3 | "Scan I2C Bus" shows only "Scanning port 16" | **FIRMWARE RACE (confirmed)**: `hal_battery_service()` runs every 20 ms (`BATTERY_US=20000`) and calls `hal_i2c_select_port(16)`. A port-16 scan takes ~112 ms (112 addrs × 1 ms probe) → battery service fires ~5× mid-scan, re-selecting the mux and corrupting probes. Few/no `Found:` lines emitted. | **FIRMWARE**: gate `hal_battery_service()` during a scan (set a `s_scan_active` flag in cmd `I`, skip battery service while set), OR pause battery during scan |
| 4 | Scanning individual port does not work | Same firmware race as #3 (single-port scan is the affected path) | Same as #3 |
| 5 | Reconnect after power cycle doesn't find board | `_find_cdc_port()` matches description substrings ('Pico'/'USB'/'Serial') — unreliable, never checks `port.vid == 0x2E8A` (Raspberry Pi). Also `_attempt_reconnect` doesn't reschedule after a failed CDC attempt → loop stalls | Dashboard: match `port.vid == 0x2E8A`; ensure `_attempt_reconnect` always calls `_start_reconnect_timer()` on failure |

**Key correction to earlier note**: The I2C scan problem is a **firmware bug** (battery-service/mux race), not a dashboard parser bug. Dashboard cannot fix #3/#4 — needs a firmware change. The `E`/`S`/`I`/`L`/`y` parsers were all re-verified correct against exact firmware printf formats.

## Firmware console ground truth (EVN_ALPHA_Performance.c)

| Cmd | Exact firmware output | Dashboard implication |
|---|---|---|
| `h` | `H alive` + `Core1: ...` + `Battery: %.3f V (cells %.3f / %.3f)` | Battery regex OK ✓ |
| `S` | `M%d: %7.1f deg  %6.1f d/s  tgt=%5.0f  %s%s` (`STALL ` + `done`/`moving`) + Core1 line | **`tgt=` is SPACE-PADDED** → Bug B |
| `s` (lowercase) | Sets encoder/motor signs — NOT status | Quick button sends wrong case → Bug G |
| `E n us` | `>> Servo %d pulse=%lu us` — **WRITE ONLY, no query mode exists** | `E n 0` drives servo to 0 µs → Bug A |
| `L 0/1/2` | `>> LED ON` / `>> LED OFF` / `>> LED TOGGLE` — **no query exists** | Toggle state unknowable → Bug H |
| `I` | `Scanning all 16 I2C ports...` → `Port N: M device(s)` → `  0xNN` | Parses OK |
| `I n` | `Scanning I2C port N...` → `  Found: 0xNN` per device — **NO summary line** | Empty port shows only "Scanning..." → Bug I |
| `y` | `BUTTON: PRESSED` / `BUTTON: RELEASED` | OK ✓ |
| `R` | `R rebooting to BOOTSEL...` then `reset_usb_boot(0,0)` | Works; not called on window close → Bug F |
| `c` | Coasts ALL motors (no per-motor coast exists) | Relabel button "Coast All" |
| `M n d` | RELATIVE move | Dashboard delta-from-cache OK (≤500 ms stale) |
| (idle 120 s) | Auto-reboot to BOOTSEL (`CONSOLE_IDLE_TIMEOUT_US`) | Heartbeat must keep firing; also means Bug F self-heals after 120 s |

## Bug A — SERVO WRITE-AS-QUERY, HARDWARE-ACTIVE (fix first)
`send_periodic_queries()` sends `E {i+1} 0` every 2 s "to query". Firmware `E` has no query mode: `E n 0` calls `hal_servo_write_us(n-1, 0)` — **all 4 servos are commanded to 0 µs every 2 seconds** while the dashboard is connected.
- **Fix**: Delete the entire `_last_servo_query` block from `send_periodic_queries()`. Track pulses locally — the echo parser (`>> Servo N pulse=M us`) already works for dashboard-initiated sets. Initialize display to 1500 µs (firmware default at `hal_servo_init`).
- **Note**: The reported "1,2,3,4 µs" display is NOT reproducible from current code (expected symptom of this bug is "0 us"). Treat exact numbers as unverified; the write-to-0 is certain. Re-observe after fix.

## Bug B — Motor telemetry always 0 (regex vs firmware padding)
Firmware prints `tgt=%5.0f` → `tgt=   90`. Dashboard regex has `tgt=([-\d.]+)` — `[-\d.]+` cannot match the spaces, so **every M-line fails to parse** and angles/speeds/targets stay 0.0 forever.
- **Fix** in `parse_console_output()`: `r'M(\d):\s+(-?[\d.]+)\s+deg\s+(-?[\d.]+)\s+d/s\s+tgt=\s*(-?[\d.]+)'` (the `\s*` after `tgt=` is the fix).

## Bug C — Crashes: Tkinter calls from non-main threads
Tkinter is not thread-safe. Two confirmed violators: (1) `startup_sequence()` runs in a raw thread and calls `log_to_console()`/`update_status()` directly (also via `_flash_firmware`/`_wait_for_cdc_port`); (2) `heartbeat_loop` thread → `send_console_command_raw()` → `log_to_console()`. Either causes intermittent crashes "after running for a bit".
- **Fix**: Marshal to the main thread at the top of both methods:
  ```python
  def log_to_console(self, message, tag=None):
      if threading.current_thread() is not threading.main_thread():
          self.root.after(0, lambda m=message, t=tag: self.log_to_console(m, t))
          return
      # ...existing body...
  ```
  Same pattern for `update_status()`.
- **Also**: `final_quit()` must cancel pending after-ids — `update_gui`'s 100 ms self-reschedule and `_reconnect_timer` fire on a destroyed root → TclError on exit. Store the ids (`self._update_gui_id = self.root.after(100, self.update_gui)`) and `after_cancel` them in `final_quit()`; guard `_start_reconnect_timer()` with `if self._shutting_down: return`.

## Bug D — Accent.TButton white-on-white + dark mode not applying (wrong ttk theme)
Windows native theme (`vista`/`xpnative`) **ignores** `background`/`foreground` on `TButton` and `TNotebook.Tab` — every `style.configure`/`style.map` for button faces and tabs is a no-op. This is the single root cause of both the invisible Quit button text and dark mode "white on white".
- **Fix**: One line at the top of `setup_styles()`: `style.theme_use('clam')`. `clam` honors all the existing color configuration. (Prior attempts rewrote colors repeatedly without touching the theme — that's why nothing changed.)

## Bug E — BOOTSEL check parses a drive letter as a COM port
`check_bootsel.ps1` returns a **drive letter** (e.g. `D:`), not a COM port. `check_bootsel_mode()` does `port_var.set("D:")` and reports "BOOTSEL detected on port D:".
- **Fix**: Treat output as drive letter; never set the port combo. On BOOTSEL detection → `_flash_firmware()` → `_wait_for_cdc_port()` (the startup path already does this correctly by accident of truthiness).
- **Also**: Harden `_find_cdc_port()` — match `port.vid == 0x2E8A` (Raspberry Pi) instead of substring guesses that can grab the wrong USB-serial device.

## Bug F — Window X close doesn't reboot to UF2
`on_closing()` → `final_quit()` never sends `R`. Only the Quit & Reboot button does.
- **Fix**: In `on_closing()`, ask "Reboot board to UF2 before exit?"; if yes, `send_console_command_raw("R")` then `self.root.after(1000, self.final_quit)` (reuse `quit_and_reboot`'s path). Not a brick risk — firmware auto-reboots to BOOTSEL after 120 s of console silence.

## Bug G — Quick command "Status (S)" sends lowercase 's'
Firmware lowercase `s` = set encoder/motor signs → prints `?? usage: s motor enc_sign motor_dir`.
- **Fix**: Change the quick button lambda to send `"S"` (uppercase).

## Bug H — LED toggle indicator
Firmware has no LED query; `>> LED TOGGLE` reveals nothing, and the GP24 button also toggles the LED, so the indicator can drift regardless.
- **Fix**: Remove the TOGGLE button (per original note). Indicator updates only from `>> LED ON`/`>> LED OFF` echoes. Document: indicator reflects last dashboard command only. (If true state is ever needed, firmware must add a query — flag for firmware owner, not the dashboard.)

## Bug I — I2C parse nits
`i2c_scanning_match` (`Scanning (?:all \d+ |)I2C ports?\.?`) prefix-matches `Scanning I2C port 16...` too, so the port-specific branch is dead code (harmless — same clear+print behavior). Device lines (`  Found: 0xNN`) DO parse correctly. Single-port scans print **no summary line** — on an empty port only "Scanning I2C port N..." appears (expected, not a bug).
- **Fix**: Anchor the all-ports regex (`^Scanning all`). If "scanning port 16 only" was observed WITH the battery present, verify on hardware — port 16 should list `0x6B` (BQ25887); probe is 1-byte read, 1 ms/address.

## Bug J — Console spam / duplicate heartbeat
Every periodic query is logged (`> h`, `> S` every 500 ms) and each log calls `update_idletasks()` → UI churn. Two heartbeats run concurrently (`heartbeat_loop` 5 s + periodic `h` 2 s).
- **Fix**: Add a `quiet=False` param to `send_console_command_raw()`; use `quiet=True` for all periodic sends. Remove one heartbeat (keep the 2 s periodic `h`, delete `heartbeat_loop`).

## Remaining unverified (need hardware)
- `hold_motor` sends `M n 0` (relative 0) — expected to retarget+hold via endpoint PID; verify.
- `coast_motor` coasts ALL motors (firmware has no per-motor coast) — relabel "Coast All" or request firmware per-motor coast.
- Servo "1,2,3,4 µs" display — not reproducible from current code; re-observe after Bug A fix.

## Verification checklist (HITL, in order)
1. Connect → battery voltage populates within 2 s (h response).
2. Motors tab: angles/speeds/targets go nonzero after a move (Bug B).
3. Servos: set 1000/2000 µs, display follows; **no servo motion while idle** (Bug A).
4. Dark mode: all buttons/tabs/frames restyle; Quit & Reboot shows red face + white text (Bug D).
5. I2C: scan port 16 → `0x6B` listed (Bug I).
6. Close via X with reboot → board enumerates as RPI-RP2 drive (Bug F).
7. Idle connected 10 min → no crash (Bug C).
8. Coast all motors at end (`c`) — motor safety rule.
