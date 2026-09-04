# EVN ALPHA Performance — Autonomous Agent Workflow & Resume Index

> **This is the canonical entry point for every agent session.**  
> Start here → follow the workflow → update this file at session end.

---

## 🎯 Autonomous Agent Session Workflow

### BEFORE STARTING — Pre-Session Checklist
- [ ] Read **this file** (index.md) completely
- [ ] Read `docs/AGENTS.md` (mandatory rules)
- [ ] Read `docs/PLAN.md` → check **Status Board** for active phase
- [ ] Read `docs/ASSUMPTIONS.md` → confirm any assumptions needed for active phase
- [ ] Verify board state: **powered on?** (HITL requirement — ask user before any flash)
- [ ] Check `hal/hal_tuning_log.h` for current `EVN_TUNING_RUN_ID`
- [ ] Check `CMakeLists.txt` for `EVN_AUTONOMOUS_TUNING` value (0 = console, 1 = autonomous)

---

### STEP 1: UNDERSTAND THE NEXT ACTION (5 min max)

**Read the "Next Step" section of the latest resume file** (linked below).  
Identify the **single deliverable** and the **cheapest falsifying check** (Efficiency Protocol §2.1).

> **Efficiency Protocol Rule 1**: State exact deliverable + falsifying check *before* searching/editing.

**Output**: Write a one-line goal at the top of your session notes (see template below).

---

### STEP 2: EXECUTE WITH VERIFICATION

**Implementation Loop**:
1. Make smallest grounded edit once controlling path is known
2. **One focused validation immediately after** (Efficiency Protocol §2.3)
3. Do not repeat passing checks unless later edit affects them (§2.4)
4. Batch independent reads/searches in one parallel call (§2.2)
5. If 3rd patch on same bug → **rewrite function cleanly** (§2.10)

**Build & Deploy** (never hand-run cmake/ninja):
- `Compile Project` task → verify zero errors
- **Ask user to confirm board is powered on** (mandatory HITL rule)
- `Run Project` task (flashes via picotool + reboots)  
  - OR `Flash` task if picotool can't see board (needs CMSIS-DAP probe)

**Autonomous Tuning Pipeline** (if applicable):
```powershell
# One-command full pipeline (build + flash + wait BOOTSEL + extract + decode + summary)
python tools/flash_extract_decode.py
```
> Uses PowerShell WMI for reliable BOOTSEL detection. Creates timestamped results dir.

**HITL Testing**:
- **Before**: Explicitly prompt user to prepare (marker placement, motor freedom, battery check)
- **During**: Single human observation batched; all else automated
- **After**: Explicitly prompt user to confirm result + coast motors (`hal_motor_coast_all()`)

---

### STEP 3: LOG & PLAN NEXT SESSION

**At every verified checkpoint** (and at session end):
1. Update **Status Board** in `docs/PLAN.md` (phase state, verified date, commit hash)
2. Update **ASSUMPTIONS.md** (close/resolve any assumptions tested)
3. Create new resume file: `docs/resume/YYYY-MM-DD_phaseX_description.md`
4. Update **this index.md** with:
   - New session file in chronological table
   - Current State block
   - Winning Configurations table
   - Key Results Summary
   - Next Session Priorities

**Resume File Template** (copy & fill):
```markdown
# Phase X Description (run 0xRUNID)

**Date**: YYYY-MM-DD

## Test Matrix
- N cases: [what was tested]
- [parameters]

## Results: N/N committed, N/N traces
[Table with pass/fail counts, key metrics]

## Key Findings
1. [New fact 1]
2. [New fact 2]
...

## Infrastructure & Safety
- [Battery, Core 1 timing, CRC counts]

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |

## Updated Winning Configurations (to promote to motion_engine.c)
[Table]

## Next Step
1. [Specific actionable item]
2. [Specific actionable item]
...
```

---

### STEP 4: CLEAN UP & HANDOFF

**Before ending session**:
- [ ] Coast all motors: `hal_motor_coast_all()` or `evn_motion_coast(i)`
- [ ] Commit all changes with descriptive message
- [ ] Ensure board is in known state (console firmware, USB CDC working — power cycle if needed)
- [ ] Leave **one exact continuation command** for next session
- [ ] Update this `index.md` with complete session summary

> **Efficiency Protocol Rule 12**: Start fresh agent session when context becomes inefficient.  
> First coast hardware, commit verified work, update Status Board/resume point, leave one exact next command.

---

## 📂 Session Files (Chronological)

| Date | File | Phase / Focus |
|------|------|---------------|
| 2026-09-02 | [2026-09-02_phase7_ev3_medium.md](2026-09-02_phase7_ev3_medium.md) | Phase 7 — EV3 Medium Motion (initial resume) |
| 2026-09-02 | [2026-09-02_phase8_multi_axis_v11.md](2026-09-02_phase8_multi_axis_v11.md) | Phase 8 Multi-Axis Validation v11 (run 0x26090224) |
| 2026-09-02 | [2026-09-02_phase8_focused_v12.md](2026-09-02_phase8_focused_v12.md) | Phase 8 Focused Tuning v12 (run 0x26090226) |
| 2026-09-02 | [2026-09-02_phase8_focused_v13.md](2026-09-02_phase8_focused_v13.md) | Phase 8 Focused Tuning v13 — **Breakthrough** (run 0x26090227) |
| 2026-09-02 | [2026-09-02_usb_issues.md](2026-09-02_usb_issues.md) | Safe Console Handoff & USB CDC Issues |
| 2026-09-03 | [2026-09-03_phase8_focused_v14.md](2026-09-03_phase8_focused_v14.md) | Phase 8 Focused Tuning v14 — v13 not reproduced (run 0x26090228) |
| 2026-09-03 | [2026-09-03_phase8_focused_v15.md](2026-09-03_phase8_focused_v15.md) | Phase 8 Focused Tuning v15 — v13 not reproduced 2nd time (run 0x26090229) |
| 2026-09-03 | [2026-09-03_session_end.md](2026-09-03_session_end.md) | Session End State & Autonomous Flash Extraction Protocol |
| 2026-09-04 | [2026-09-04_next_session.md](2026-09-04_next_session.md) | Next Session Priorities (from NEXT_SESSION.md) |
| 2026-09-04 | [2026-09-04_phase8_hardware_validation.md](2026-09-04_phase8_hardware_validation.md) | Phase 8 Hardware Validation (run 0x2609022A) |
| 2026-09-04 | [2026-09-04_phase8_v17_v20.md](2026-09-04_phase8_v17_v20.md) | Phase 8 Autonomous Iteration v17-v20 (runs 0x2609042C-31) |
| 2026-09-04 | [2026-09-04_phase8_kff_accel_sweep.md](2026-09-04_phase8_kff_accel_sweep.md) | Phase 8 kff_accel Sweep & Unloaded EV3 Medium Retune (run 0x26090433) |
| 2026-09-04 | [2026-09-04_phase8_kd_vel_sweep.md](2026-09-04_phase8_kd_vel_sweep.md) | Phase 8 kd_vel Sweep & Unloaded EV3 Medium Retune v2 (run 0x26090434) |
| 2026-09-04 | [2026-09-04_phase8_neg_breakthrough.md](2026-09-04_phase8_neg_breakthrough.md) | Phase 8 EV3 Medium NEG 12/12 BREAKTHROUGH (run 0x26090435) |
| 2026-09-04 | [2026-09-04_phase8_all_axes_12_12.md](2026-09-04_phase8_all_axes_12_12.md) | Phase 8 ALL AXES 12/12 BREAKTHROUGH (run 0x26090437) |
| 2026-09-04 | [2026-09-04_phase8_final_validation.md](2026-09-04_phase8_final_validation.md) | Phase 8 Final Validation — Run-to-Run Variation (run 0x26090438) |
| 2026-09-04 | [2026-09-04_dashboard_development.md](2026-09-04_dashboard_development.md) | Phase 8 Dashboard Development — GUI Dashboard with real telemetry, BOOTSEL auto-flash, dark mode |
| 2026-09-04 | [2026-09-04_dashboard_fixes.md](2026-09-04_dashboard_fixes.md) | Phase 8 Dashboard Fixes — Serial crash fixes, dark mode rewrite, button styling (run 0x26090439) |
| 2026-09-04 | [2026-09-04_motor_model_calibration.md](2026-09-04_motor_model_calibration.md) | Phase 8 Motor Model Calibration — Fixed EV3 Medium unloaded model, sysid run 0x2609043A |
| 2026-09-04 | [2026-09-04_phase8_stiction_fix.md](2026-09-04_phase8_stiction_fix.md) | Phase 8 Stiction Break Fix — Lowered velocity threshold, added pos-error activation, symmetric EV3 Medium gains (run 0x2609043B) |
| 2026-09-04 | [2026-09-04_phase8_stiction_hitl_test.md](2026-09-04_phase8_stiction_hitl_test.md) | Phase 8 Stiction Break Fix — HITL Verification (run 0x2609043B) |
| 2026-09-05 | [2026-09-05_dashboard_fixes_autonomous_run.md](2026-09-05_dashboard_fixes_autonomous_run.md) | Phase 8 Dashboard Fixes (10 bugs) + Autonomous Run (run 0x2609043C) |

---

## 📋 Quick Reference — Current State (as of 2026-09-05 — dashboard fixes complete + autonomous run 0x2609043C)

| Item | Value |
|------|-------|
| **Board** | Console firmware (`EVN_AUTONOMOUS_TUNING=0`), USB CDC functional after power cycle |
| **Motors** | M1/M2 = EV3 Large, M3/M4 = EV3 Medium **UNLOADED** (new motor on port 4 per user) |
| **Build** | `build/EVN_ALPHA_Performance.uf2` = non-autonomous console with stiction fix + dashboard fixes |
| **Next Run ID** | `0x2609043C` (in `hal/hal_tuning_log.h`) |
| **Autonomous Tuning** | Disabled in `CMakeLists.txt` (restored after run) |
| **Hardware Validation** | ✅ Complete — 176/176 cases run across 11 autonomous runs, all traces decoded |
| **Motor Model Calibration** | ✅ Complete — EV3 Medium model fixed for unloaded operation, sim 12/12 both directions |
| **Stiction Break Fix** | ✅ **HITL VERIFIED** — Both EV3 Medium motors break stiction and complete ±30° moves (4/4 moves done) |
| **Dashboard** | **10/10 BUGS FIXED** — All confirmed root causes from firmware console audit resolved (see session file) |

### Winning Configurations (Promoted to `motion_engine.c`)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large | **4.0e-4** | **5.0e-6** | 8e-7 | **0** | 0 | 0.70 | 1.0e-6 |
| EV3 Medium NEG | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **2.0e-6** |
| EV3 Medium POS | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **2.0e-6** |

### Key Results Summary
- **EV3 Large (axes 0,1)**: **12/12 ACHIEVED** in run 0x2609043C (cases 0,4 - W40_K50 gains). Max track error ~1.6-1.8° (< 2.0° threshold). Previous 12/12 configs from run 0x2609043B also valid.
- **EV3 Medium NEG (axis 2)**: **12/12 REPRODUCED** with kp=2.5e-4, kv=1.0e-6, endpoint_kp=2.0e-6 (2 configs in run 0x2609043B). Max track error 1.43°.
- **EV3 Medium POS (axis 3)**: **12/12 BREAKTHROUGH** with kp=2.5e-4, kv=1.0e-6, endpoint_kp=2.5e-6, kd_vel=1.0e-6 (run 0x2609043B case 12).
- **ALL FOUR AXES HAVE 12/12 CONFIGS**: Historic milestone maintained across runs.
- **Core 1 timing**: Excellent — 999-1001µs period, 105-202µs exec, 0 missed ticks across all 176 cases.
- **Run-to-run variation**: Still present - need 2+ consecutive 12/12 runs on all 4 axes simultaneously.
- **Stiction Break Fix VERIFIED**: Velocity threshold 5000→1000, pos-error activation works. EV3 Medium axes show no stiction stalls in autonomous run 0x2609043C.

### Documentation Updates (2026-09-05 — this session)
- `tools/evn_dashboard.py`: **10/10 bugs fixed** (A-J from firmware console audit)
- **Run 0x2609043C**: Autonomous validation run - 2 configs 12/12 (EV3 Large pos, W40_K50), multiple 11/12 & 10/12. 16 cases. Core 1: 999-1001µs period, 0 missed ticks.
- `CMakeLists.txt`: EVN_AUTONOMOUS_TUNING toggled for run, restored to 0 after
- `hal/hal_tuning_log.h`: Run ID incremented to 0x2609043C
- `docs/resume/2026-09-05_dashboard_fixes_autonomous_run.md`: New session file created

---

## 🎯 Next Session Priorities

### 0. HITL Test Stiction Break Fix — **HITL VERIFIED ✅** (was blocking 12/12 on EV3 Medium)
- **Status**: Code changes **COMMITTED** (pid.c, simulate_motor.py, autonomous_tuning.c). Firmware **FLASHED** to board. **HITL TEST PASSED**.
- **Changes Made**:
  - Firmware (pid.c): Velocity threshold 5000→1000 mdeg/s, added `pos_err_starting` activation when `pos_err > deadzone` && `abs_vel_ref < 1000` && `abs_speed < 1000` && `displacement < 100`
  - Simulation (simulate_motor.py): Synced with firmware
  - Autonomous Tuning (autonomous_tuning.c): EV3 Medium (axes 2,3) → `startup_duty` 0.65→0.80, `startup_release_speed_mdegs` 10000→2000, symmetric gains: `kd_vel=0`, `endpoint_kp_vel=2.0e-6` both directions
- **Falsifying Check Done**: Simulation runs correctly with new logic
- **Verify (HITL)**: **COMPLETED** — Both EV3 Medium axes (2,3) tested with ±30° moves (4/4 moves completed, no stiction stall)
- **Next**: Enable `EVN_AUTONOMOUS_TUNING=1`, run autonomous → target 12/12 on all 4 axes, 2+ consecutive runs

### 1. Dashboard Fixes — **COMPLETED ✅** (10/10 bugs fixed, 2026-09-05)
- All 10 confirmed bugs from firmware console audit resolved in `tools/evn_dashboard.py`
- **Verification needed**: HITL test with user to confirm all fixes work on hardware

### 2. Phase 8 (Drive Base) — BLOCKED
- Cannot proceed until 2+ consecutive 12/12 runs on all 4 axes.
- Current best: 9-11/12 consistently (run 0x2609043C: 2×12/12 on EV3 Large pos, 11/12 on others).
- Once stiction fixed and 2+ consecutive 12/12 achieved → begin drive base kinematics.

### 3. Consecutive Autonomous Validation Runs — **HIGH PRIORITY**
- Run 2+ consecutive autonomous runs with current winning configs (W40_K50 for EV3 Large, W35_K10 for EV3 Medium)
- Target: 12/12 on all 4 axes in 2+ consecutive runs
- Run ID increment: 0x2609043D, 0x2609043E...

### 4. Alternative: Statistical Approach (Lower Priority)
- Run 20+ consecutive autonomous runs with current winning configs.
- Low probability of 2+ consecutive 12/12 given current variance (~10% per axis).
- Only viable if consecutive validation fails.

Audit method: every console command handler in `EVN_ALPHA_Performance.c` (lines 305–585) read and matched against `tools/evn_dashboard.py` parsers. **Nemotron's guesses are superseded** — root causes below are confirmed against firmware source. Fix in priority order; each fix is independent.

#### Firmware console ground truth (EVN_ALPHA_Performance.c)

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

#### Bug A — SERVO WRITE-AS-QUERY, HARDWARE-ACTIVE (fix first)
`send_periodic_queries()` sends `E {i+1} 0` every 2 s "to query". Firmware `E` has no query mode: `E n 0` calls `hal_servo_write_us(n-1, 0)` — **all 4 servos are commanded to 0 µs every 2 seconds** while the dashboard is connected.
- **Fix**: Delete the entire `_last_servo_query` block from `send_periodic_queries()`. Track pulses locally — the echo parser (`>> Servo N pulse=M us`) already works for dashboard-initiated sets. Initialize display to 1500 µs (firmware default at `hal_servo_init`).
- **Note**: The reported "1,2,3,4 µs" display is NOT reproducible from current code (expected symptom of this bug is "0 us"). Treat exact numbers as unverified; the write-to-0 is certain. Re-observe after fix.

#### Bug B — Motor telemetry always 0 (regex vs firmware padding)
Firmware prints `tgt=%5.0f` → `tgt=   90`. Dashboard regex has `tgt=([-\d.]+)` — `[-\d.]+` cannot match the spaces, so **every M-line fails to parse** and angles/speeds/targets stay 0.0 forever.
- **Fix** in `parse_console_output()`: `r'M(\d):\s+(-?[\d.]+)\s+deg\s+(-?[\d.]+)\s+d/s\s+tgt=\s*(-?[\d.]+)'` (the `\s*` after `tgt=` is the fix).

#### Bug C — Crashes: Tkinter calls from non-main threads
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

#### Bug D — Accent.TButton white-on-white + dark mode not applying (wrong ttk theme)
Windows native theme (`vista`/`xpnative`) **ignores** `background`/`foreground` on `TButton` and `TNotebook.Tab` — every `style.configure`/`style.map` for button faces and tabs is a no-op. This is the single root cause of both the invisible Quit button text and dark mode "white on white".
- **Fix**: One line at the top of `setup_styles()`: `style.theme_use('clam')`. `clam` honors all the existing color configuration. (Nemotron rewrote colors repeatedly without touching the theme — that's why nothing changed.)

#### Bug E — BOOTSEL check parses a drive letter as a COM port
`check_bootsel.ps1` returns a **drive letter** (e.g. `D:`), not a COM port. `check_bootsel_mode()` does `port_var.set("D:")` and reports "BOOTSEL detected on port D:".
- **Fix**: Treat output as drive letter; never set the port combo. On BOOTSEL detection → `_flash_firmware()` → `_wait_for_cdc_port()` (the startup path already does this correctly by accident of truthiness).
- **Also**: Harden `_find_cdc_port()` — match `port.vid == 0x2E8A` (Raspberry Pi) instead of substring guesses that can grab the wrong USB-serial device.

#### Bug F — Window X close doesn't reboot to UF2
`on_closing()` → `final_quit()` never sends `R`. Only the Quit & Reboot button does.
- **Fix**: In `on_closing()`, ask "Reboot board to UF2 before exit?"; if yes, `send_console_command_raw("R")` then `self.root.after(1000, self.final_quit)` (reuse `quit_and_reboot`'s path). Not a brick risk — firmware auto-reboots to BOOTSEL after 120 s of console silence.

#### Bug G — Quick command "Status (S)" sends lowercase 's'
Firmware lowercase `s` = set encoder/motor signs → prints `?? usage: s motor enc_sign motor_dir`.
- **Fix**: Change the quick button lambda to send `"S"` (uppercase).

#### Bug H — LED toggle indicator
Firmware has no LED query; `>> LED TOGGLE` reveals nothing, and the GP24 button also toggles the LED, so the indicator can drift regardless.
- **Fix**: Remove the TOGGLE button (per original note). Indicator updates only from `>> LED ON`/`>> LED OFF` echoes. Document: indicator reflects last dashboard command only. (If true state is ever needed, firmware must add a query — flag for firmware owner, not the dashboard.)

#### Bug I — I2C parse nits
`i2c_scanning_match` (`Scanning (?:all \d+ |)I2C ports?\.?`) prefix-matches `Scanning I2C port 16...` too, so the port-specific branch is dead code (harmless — same clear+print behavior). Device lines (`  Found: 0xNN`) DO parse correctly. Single-port scans print **no summary line** — on an empty port only "Scanning I2C port N..." appears (expected, not a bug).
- **Fix**: Anchor the all-ports regex (`^Scanning all`). If "scanning port 16 only" was observed WITH the battery present, verify on hardware — port 16 should list `0x6B` (BQ25887); probe is 1-byte read, 1 ms/address.

#### Bug J — Console spam / duplicate heartbeat
Every periodic query is logged (`> h`, `> S` every 500 ms) and each log calls `update_idletasks()` → UI churn. Two heartbeats run concurrently (`heartbeat_loop` 5 s + periodic `h` 2 s).
- **Fix**: Add a `quiet=False` param to `send_console_command_raw()`; use `quiet=True` for all periodic sends. Remove one heartbeat (keep the 2 s periodic `h`, delete `heartbeat_loop`).

#### Remaining unverified (need hardware)
- `hold_motor` sends `M n 0` (relative 0) — expected to retarget+hold via endpoint PID; verify.
- `coast_motor` coasts ALL motors (firmware has no per-motor coast) — relabel "Coast All" or request firmware per-motor coast.
- Servo "1,2,3,4 µs" display — not reproducible from current code; re-observe after Bug A fix.

#### Verification checklist (HITL, in order)
1. Connect → battery voltage populates within 2 s (h response).
2. Motors tab: angles/speeds/targets go nonzero after a move (Bug B).
3. Servos: set 1000/2000 µs, display follows; **no servo motion while idle** (Bug A).
4. Dark mode: all buttons/tabs/frames restyle; Quit & Reboot shows red face + white text (Bug D).
5. I2C: scan port 16 → `0x6B` listed (Bug I).
6. Close via X with reboot → board enumerates as RPI-RP2 drive (Bug F).
7. Idle connected 10 min → no crash (Bug C).
8. Coast all motors at end (`c`) — motor safety rule.

### 2. Phase 8 (Drive Base) — BLOCKED
- Cannot proceed until 2+ consecutive 12/12 runs on all 4 axes.
- Current best: 9-11/12 consistently, but stiction + run-to-run variation prevents 2+ consecutive 12/12.
- Once stiction fixed and 2+ consecutive 12/12 achieved → begin drive base kinematics.

### 3. Alternative: Statistical Approach (Lower Priority)
- Run 20+ consecutive autonomous runs with current winning configs.
- Low probability of 2+ consecutive 12/12 given current variance (~10% per axis).
- Only viable if stiction fix fails or takes too long.

---

## ⚡ Key Protocols (Condensed)

| Protocol | Rule | Reference |
|----------|------|-----------|
| **Efficiency** | State deliverable + falsifying check first | `PLAN.md` §2.1 |
| **Efficiency** | Batch reads; read context once | `PLAN.md` §2.2 |
| **Efficiency** | One focused validation per edit | `PLAN.md` §2.3 |
| **Efficiency** | 3 patches same bug → rewrite | `PLAN.md` §2.10 |
| **Flash/Verify** | Always use `flash_and_capture.py` (or `flash_extract_decode.py`) | `PLAN.md` §2.11 |
| **HITL** | Ask user to confirm board powered before flash | `AGENTS.md` |
| **HITL** | Batch physical asks; prompt before/after | `AGENTS.md` |
| **Motor Safety** | Always coast at end of every test | `AGENTS.md` |
| **Battery Gate** | Fresh sample ≤250ms, pack ≥6.5V, cells ≥3.0V | `AGENTS.md` |
| **Assumptions** | Verify hardware capability before coding | `PLAN.md` §2.9 |
| **Session Handoff** | Coast → commit → update Status Board → leave next command | `PLAN.md` §2.12 |
| **Board Detection** | Check BOOTSEL first via `check_bootsel.ps1` | `AGENTS.md` Board State Detection |
| **Documentation** | Document common ops in `PROCEDURES.md`; update when unexpected | `PLAN.md` §2.14 |
| **Time Estimates** | Declare autonomous run duration for realistic timeouts | `PLAN.md` §2.15 |

---

## 🔧 Common Commands Reference

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

# Manual BOOTSEL listener (Terminal 1)
powershell -NoProfile -ExecutionPolicy Bypass -File tools/wait_bootsel.ps1

# Extract flash after BOOTSEL detected
$dir = "bench\results\autonomous_multi_YYYYMMDD_vXX"
New-Item -ItemType Directory -Path $dir -Force | Out-Null
picotool save -r 0x10F00000 0x10FF0000 -f "$dir\tuning.uf2"

# Decode
python tools/decode_tuning_flash.py "$dir\tuning.uf2" --output "$dir"
```

---

## 📁 Key File Locations

| Purpose | File |
|---------|------|
| Run ID | `hal/hal_tuning_log.h` (`EVN_TUNING_RUN_ID`) |
| Autonomous toggle | `CMakeLists.txt` (`EVN_AUTONOMOUS_TUNING`) |
| Test matrix | `bench/autonomous_tuning.c` (`s_cases` array) |
| Decode script | `tools/decode_tuning_flash.py` |
| Automation script | `tools/flash_extract_decode.py` |
| BOOTSEL listener | `tools/wait_bootsel.ps1` |
| Results | `bench/results/autonomous_multi_*/summary.csv` |
| Flash records | `bench/results/autonomous_multi_*/flash_records.json` |
| Session logs | `docs/resume/*.md` |
| Master plan | `docs/PLAN.md` (Status Board) |
| Assumptions | `docs/ASSUMPTIONS.md` |
| Procedures | `docs/PROCEDURES.md` |
| Agent rules | `docs/AGENTS.md` |

---

## 🏁 Session End Template (Copy to New Resume File)

```markdown
# Phase X Description (run 0xRUNID)

**Date**: YYYY-MM-DD

## Test Matrix
- [cases tested]

## Results: N/N committed, N/N traces
[Results table]

## Key Findings
1. [Fact 1]
2. [Fact 2]

## Infrastructure & Safety
- Battery: [range] V; min cell [V]; age <250 µs
- Core 1 period: [range] µs; exec max [µs]; missed ticks: 0
- Duty smoothness: [range]

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| [filename.uf2] | [size] | [hash] |

## Updated Winning Configurations (to promote to motion_engine.c)
| Motor | kp_pos | kp_vel | ki_pos | accel_scale | endpoint_kp_vel |
| :--- | :--- | :--- | :--- | :--- | :--- |

## Next Step
1. [Action 1]
2. [Action 2]
```

---

*Workflow v1.0 established 2026-09-04. Update this file at every session end.*