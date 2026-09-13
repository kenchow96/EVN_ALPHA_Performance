# EVN ALPHA Performance — Autonomous Agent Workflow & Resume Index

> **This is the canonical entry point for every agent session.**  
> Start here → follow the workflow → update this file at session end.

> **AUTONOMOUS TUNING & VERIFICATION PROTOCOL**: Runs are executed in controlled batches using `tools/flash_extract_decode.py` or `tools/autonomous_loop.py --max-iterations N`. Each cycle verifies flash freshness, checks hardware metrics, and updates documentation at every verified checkpoint.

---

## 🎯 Autonomous Agent Session Workflow

### BEFORE STARTING — Pre-Session Checklist
- [ ] Read **this file** (index.md) completely
- [ ] Read `../../AGENTS.md` (mandatory rules — at repo root)
- [ ] Read `../PLAN.md` → check **Status Board** for active phase
- [ ] Read `../ASSUMPTIONS.md` → confirm any assumptions needed for active phase
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
> **CONTINUOUS LOOP DEFAULT**: After Step 4, the agent automatically restarts at Step 1 (re-reads this file) and continues the loop. The loop only stops when the user explicitly prompts (`KeyboardInterrupt` / "stop the loop"). The continuation command is always: `python tools/autonomous_loop.py` (or `python tools/flash_extract_decode.py --timeout 900` for a single run).

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
| 2026-09-05 | [2026-09-05_phase8_consecutive_validation_run_3D.md](2026-09-05_phase8_consecutive_validation_run_3D.md) | Phase 8 Consecutive Validation Run 0x2609043D — EV3 Large POS 12/12 reproduced, EV3 Medium config bug found |
| 2026-09-05 | [2026-09-05_phase8_autonomous_validation_3E.md](2026-09-05_phase8_autonomous_validation_3E.md) | Phase 8 Autonomous Validation Run 0x2609043E — 0/16 cases 12/12, run-to-run variation confirmed |
| 2026-09-05 | [2026-09-05_phase8_symmetric_ev3m_consecutive.md](2026-09-05_phase8_symmetric_ev3m_consecutive.md) | Phase 8 Symmetric EV3 Medium Config + Consecutive Validation (runs 0x26090440, 0x26090441) — case_04 12/12 in 2 consecutive runs |
| 2026-09-05 | [2026-09-05_phase8_simulator_enhancement.md](2026-09-05_phase8_simulator_enhancement.md) | Phase 8 Simulator Enhancement & Validation — Stribeck friction, cogging torque, thermal model, 16/16 cases 12/12 in sim |
| 2026-09-05 | [2026-09-05_phase8_autonomous_run_0x26090442.md](2026-09-05_phase8_autonomous_run_0x26090442.md) | Phase 8 Autonomous Validation Run 0x26090442 — 3rd consecutive run, case_00 12/12 for 3rd time, EV3 Medium 8-11/12 |
| 2026-09-05 | [2026-09-05_phase8_autonomous_run_0x26090443.md](2026-09-05_phase8_autonomous_run_0x26090443.md) | Phase 8 Autonomous Validation Run 0x26090443 — 4th run, case_15 121° error FIXED, case_08 first 12/12 for EV3M axis 3 NEG |
| 2026-09-06 | [2026-09-06_phase8_autonomous_run_0x26090445.md](2026-09-06_phase8_autonomous_run_0x26090445.md) | Phase 8 Run 0x26090445 — pipeline BOOTSEL false-positive FIXED; case_15 & case_04 12/12; axis 0 hunting regression (6/12) |
| 2026-09-06 | [2026-09-06_phase8_autonomous_run_0x26090446.md](2026-09-06_phase8_autonomous_run_0x26090446.md) | Phase 8 Run 0x26090446 — case_01 (axis 0 NEG) hunting SYSTEMATIC; case_04 12/12 2nd consecutive; axis0/axis1 divergence = per-axis/hardware |
| 2026-09-06 | [2026-09-06_phase8_autonomous_run_0x26090447.md](2026-09-06_phase8_autonomous_run_0x26090447.md) | Phase 8 Run 0x26090447 — vel_window lever FALSIFIED; BOTH EV3 Large axes collapsed (shared physical cause); case_09 first 12/12 (EV3 Medium axis 2 POS) |
| 2026-09-06 | [2026-09-06_phase8_autonomous_run_0x26090448.md](2026-09-06_phase8_autonomous_run_0x26090448.md) | Phase 8 Run 0x26090448 — **Motor-swap (M1↔M2) experiment**: hunting follows NEITHER motor NOR axis ⇒ EV3 Large config is marginally stable across the whole gear-train variability range; sim gap confirmed; case_08 12/12 (EV3 Medium) |
| 2026-09-06 | [2026-09-06_phase8_sim_calibration.md](2026-09-06_phase8_sim_calibration.md) | Phase 8 **Sim Calibration BREAKTHROUGH** — sim now reproduces the physical EV3 Large limit cycle (13.9 Hz vs physical 13.6 Hz); **vel_window=10 eliminates the limit cycle in sim** (never tested on hardware — run 47 only tried vel_window=60 which made it worse) |
| 2026-09-07 | [2026-09-07_phase8_vel_window_test.md](2026-09-07_phase8_vel_window_test.md) | Phase 8 vel_window=10 hardware test (run 0x26090449) — axis-0 NEG hunting improved (6/12→11/12), case_13/15 EV3 Medium POS stiction stalls |
| 2026-09-08 | [2026-09-08_phase8_autonomous_run_0x2609044A.md](2026-09-08_phase8_autonomous_run_0x2609044A.md) | Phase 8 Autonomous Validation Run 0x2609044A — axis 2 NEG first 12/12; axis 3 POS stiction stalls persist (9-10/12); vel_window=10 for axis 3 helped slightly |
| 2026-09-08 | [2026-09-08_sim_to_real_report_analysis.md](2026-09-08_sim_to_real_report_analysis.md) | Sim-to-Real Report Analysis — includes dissenting viewpoint section (3 challenges to parallel agent's DR/backlash/RPL recommendations, with workspace evidence) |
| 2026-09-08 | [2026-09-08_index_autonomous_session.md](2026-09-08_index_autonomous_session.md) | **Autonomous session (sim-only)** — Simulator verification (EV3 Large + EV3 Medium with backlash, vel_window=10); index.md updated; no real hardware transfer (user: "before trying real transfer") |
| 2026-09-08 | [2026-09-08_phase8_autonomous_run_0x2609044B.md](2026-09-08_phase8_autonomous_run_0x2609044B.md) | Phase 8 Autonomous Validation Run 0x2609044B — 0/16 cases 12/12, 5 cases 11/12; EV3 Large axis 0 strong (3×11/12), axis 3 POS stiction persists |
| 2026-09-08 | [2026-09-08_phase8_autonomous_run_0x2609044C.md](2026-09-08_phase8_autonomous_run_0x2609044C.md) | Phase 8 Autonomous Validation Run 0x2609044C — **Axis 3 stiction fix WORKED!** start_duty 0.80→0.90; 8 cases 11/12 (case_13/15 now 11/12), EV3 Large axis 0 4×11/12 |
| 2026-09-08 | [2026-09-08_phase8_dr_gain_tuning.md](2026-09-08_phase8_dr_gain_tuning.md) | Phase 8 DR Gain Tuning for EV3 Large — Identified delay+backlash as killer combo; prop9_accel06 (kp_pos=2.0e-4, kp_vel=1.0e-5, endpoint_kp=2.5e-6, accel_scale=0.60) achieves DR worst=8/12 (4× improvement over baseline 2/12) |
| 2026-09-08 | [2026-09-08_phase8_autonomous_run_0x2609044D.md](2026-09-08_phase8_autonomous_run_0x2609044D.md) | Phase 8 Autonomous Run 0x2609044D — DR-robust prop9_accel06 on hardware: axis 0 ALL 11/12, axis 1 still hunting (6-8/12); axis 3 POS 11/12 with start_duty=0.90 |
| 2026-09-12 | [2026-09-12_phase8_autonomous_run_0x2609044F.md](2026-09-12_phase8_autonomous_run_0x2609044F.md) | Phase 8 — Autonomous Validation 0x2609044F (start_duty=0.90 axis 2 POS, vel_window=10 all axes) |
| 2026-09-12 | [2026-09-12_audit_remediation.md](2026-09-12_audit_remediation.md) | Phase 8 Audit Remediation & Firmware Sync (run 0x2609044E) — Firmware defaults updated to match run 0x2609044E, I2C race fixed, run ID bumped |
| 2026-09-12 | [2026-09-12_phase8_autonomous_run_0x26090451.md](2026-09-12_phase8_autonomous_run_0x26090451.md) | Phase 8 — Autonomous Validation 0x26090451 (Stale flash guard & explicit motor labels validated, Core 1 perfect) |
| 2026-09-12 | [2026-09-12_phase8_autonomous_run_0x26090452.md](2026-09-12_phase8_autonomous_run_0x26090452.md) | Phase 8 — Autonomous Optimization 0x26090452 (One pass of auto_tuner.py, Sim-to-Real 92.5% agreement on Large motors) |
| 2026-09-12 | [2026-09-12_phase8_autonomous_run_0x26090453.md](2026-09-12_phase8_autonomous_run_0x26090453.md) | Phase 8 — Long-Term Daemon Validation 0x26090453 (6.0V cutoff, storage ring buffer, endurance log verified) |
| 2026-09-12 | [2026-09-12_phase8_autonomous_run_0x26090454.md](2026-09-12_phase8_autonomous_run_0x26090454.md) | Phase 8 — Torture Excitation Profile Validation 0x26090454 (Micro-step backlash, rapid reversal deadbands, 4x 12/12 passes) |
| 2026-09-12 | [2026-09-12_phase8_autonomous_run_0x26090455.md](2026-09-12_phase8_autonomous_run_0x26090455.md) | Phase 8 — Full Stack Integration 0x26090455 (Online DOB active, NVM parameter injection ready, Closed-loop CMA-ES feedback verified) |
| 2026-09-13 | [2026-09-13_phase8_autonomous_daemon_461_runs.md](2026-09-13_phase8_autonomous_daemon_461_runs.md) | Phase 8 — Autonomous Daemon 2-Day Run 0x26090456–0x26090628 (461 iterations, CMA-ES closed-loop, battery 8.19→7.00V, cost 52→26) |
| 2026-09-13 | [2026-09-13_phase8_autonomous_run_0x26090629.md](2026-09-13_phase8_autonomous_run_0x26090629.md) | Phase 8 — Autonomous Validation Run 0x26090629 (Symmetric Gains, Decoupled Architecture, Verified Physical Pass) |
| 2026-09-13 | [2026-09-13_phase8_autonomous_daemon_session.md](2026-09-13_phase8_autonomous_daemon_session.md) | Phase 8 — Autonomous Daemon Session (Runs 0x2609062A–0x26090686, 93 iterations) |

---

## 📋 Quick Reference — Current State (as of 2026-09-13 — **Hardware Validated on Run `0x26090686`**; Battery 7.52V; Symmetric Gains & Decoupled Unit Architecture in Daemon; Core 1: 0 missed ticks; Ready for Unsupervised Execution after recharge)

| Item | Value |
|------|-------|
| **Board State** | Console firmware restored (`EVN_AUTONOMOUS_TUNING=0`), USB CDC ready |
| **Motors** | M1/M2 = EV3 Large, M3/M4 = EV3 Medium **UNLOADED** (operated in temperature-controlled room) |
| **Build** | `build/EVN_ALPHA_Performance.uf2` = non-autonomous console (0 errors) |
| **Current Run ID** | `0x26090686` (93 daemon iterations completed, 1/16 cases 12/12) |
| **Disturbance Observer (DOB)** | Active at 1 kHz in Core 1 firmware (`evn_motion_set_dob`) for online payload & friction compensation |
| **NVM Parameter Table** | 256-byte flash page at `0x00FF8000` with zero-recompile injection tool (`tools/nvm_injector.py`) |
| **Optimizer Engine** | Closed-loop `OnlineCMAOptimizer` with decoupled per-motor-type credit assignment & worst-case cross-copy penalty (Gen 23) |
| **Excitation Profiles** | Multi-regime torture profiles (nominal moves, micro-step backlash, deadband reversals) integrated |
| **Battery Cutoff** | Hard cutoff at **6.0V pack** (`TUNING_BATTERY_MIN_PACK_MV=6000u`), 2.8V cell |
| **Battery Management** | Pack at **7.52V** (Cell 1: 3.77V, Cell 2: 3.76V). **Needs recharge** (≥7.6V) before resuming daemon |
| **Storage Management** | Automated ring buffer (`tools/storage_manager.py`) caps footprint to bounded disk usage |
| **Long-Term Tuning Daemon** | Automated daemon (`tools/autonomous_daemon.py`) with decoupled multi-unit optimizer |
| **Weak Agent Handoff** | Ready for unsupervised execution via `tools/autonomous_daemon.py` (resumes from run 0x26090687) |

---

## 🤖 Weak Agent Protocol & Long-Term Autonomous Execution

To run fully autonomous tuning for extended periods (e.g. 1 month) without code editing mistakes, context window loss, or hardware damage:

### Golden Execution Rule for the Weak Agent
**DO NOT MANUALLY GUESS OR EDIT GAIN NUMBERS IN C FILES.**  
The entire mathematical proposal, simulation pre-flight validation, NVM parameter injection, hardware execution, telemetry extraction, and Sim-to-Real evaluation are managed automatically by the daemon.

### Exact Launch Command for the Weak Agent
To start or resume the autonomous tuning process for 30 days:
```powershell
python tools/autonomous_daemon.py --days 30 --rest-seconds 15
```

### Supervisory Monitoring Commands (Read-Only)
The agent should only inspect progress using lightweight read-only commands:
- **Inspect overall progress and latest iteration scores**:
  ```powershell
  Get-Content bench/results/endurance_log.csv | Select-Object -Last 10
  ```
- **Inspect disk footprint and active runs**:
  ```powershell
  python tools/storage_manager.py
  ```
- **Stop or pause the daemon safely**:
  Send `Ctrl+C`. The daemon catches the signal, coasts all motors, restores the console firmware, and leaves the board in a safe idle state.
| **Autonomous Tuning** | Disabled in `CMakeLists.txt` (restored after run) |
| **Hardware Validation** | Complete — 224/224 cases run across 14 autonomous runs, all traces decoded |
| **Motor Model Calibration** | Complete — EV3 Medium model fixed for unloaded operation, sim 12/12 both directions |
| **Stiction Break Fix** | HITL VERIFIED & CONFIRMED IN AUTONOMOUS — case_15 catastrophic 121° error FIXED (0.0° final error); both EV3 Medium motors break stiction |
| **Dashboard** | 10/10 BUGS FIXED — All confirmed root causes from firmware console audit resolved (see session file) |
| **Symmetric EV3 Medium Config** | VALIDATED — Simulation 12/12 for both NEG/POS; hardware 7-12/12 consistent |
| **Consecutive 12/12** | case_04 (axis 1 POS r0): 2+ consecutive (0x26090445 + 0x26090446); case_01 (axis 0 NEG r1) hunting is SYSTEMATIC (6/12→5/12) — axes 0 & 1 share identical EV3 Large gains but diverge ⇒ per-axis/hardware difference, not gains |
| **Pipeline** | FIXED (2026-09-06) — `flash_extract_decode.py` BOOTSEL false-positive: now waits for the drive to disappear (app booted) before waiting for it to reappear (run done). Was extracting stale previous-run flash |
| **Simulator** | CALIBRATED TO PHYSICAL — Reproduces the EV3 Large endpoint limit cycle (13.9 Hz vs physical 13.6 Hz). **vel_window=10 eliminates the limit cycle in sim** (never tested on hardware). EV3 Medium 12/12 unaffected |
| **I2C Firmware Race** | **FIXED** — scan-active guard in `hal_i2c.c`/`hal_battery.c` prevents battery service from corrupting user scans |

### Winning Configurations (Promoted to `motion_engine.c`)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel | start_duty | vel_window |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|------------|------------|
| EV3 Large (axis 0) | **2.0e-4** | **1.0e-5** | 8e-7 | 0 | 0 | **0.60** | **2.5e-6** | 0.12 | **10** |
| EV3 Large (axis 1) | 2.0e-4 | 1.0e-5 | 8e-7 | 0 | 0 | 0.60 | 2.5e-6 | 0.12 | **10** |
| EV3 Medium (axis 2) | **2.5e-4** | **1.0e-6** | 8e-7 | 0 | 0 | **0.35** | **2.0e-6** | 0.80/0.90* | **10** |
| EV3 Medium (axis 3) | **2.5e-4** | **1.0e-6** | 8e-7 | 0 | 0 | **0.35** | **2.0e-6** | 0.80/0.90* | **10** |

* start_duty=0.80 for NEG, 0.90 for POS cases (stiction-break fix)
** vel_window=10 for both axes 2 & 3 (axis 2 testing; axis 3 confirmed working)

### Key Results Summary
- **Run 0x2609044F (2026-09-12)**: 0/16 12/12, best 11/12 (case_13/14/15). Axis 2 POS start_duty=0.90: case_09 9/12 (final error 1.508° vs 10.5° prior) — PARTIAL improvement. vel_window=10 all axes: no negative impact. Core 1 PERFECT. Stiction fix PARTIALLY CONFIRMED. Per-axis divergence (axis 0 10/12 vs axis 1 9/12) confirmed. Commit `21967d2`. Resume file: `docs/resume/2026-09-12_phase8_autonomous_run_0x2609044F.md`.
- **EV3 Large (axes 0,1)**: **12/12 ACHIEVED** on POS direction (repeat 0) in run 0x2609043D (cases 0,4 - W40_K50 gains). Max track error ~1.6-1.8° (< 2.0° threshold). **Run 0x2609043E: EV3 Large POS dropped to 8/12, 11/12** — run-to-run variation confirmed (~10% per axis). **Runs 0x26090440, 0x26090441: case_04 (axis 1 POS repeat 0) achieved 12/12 in TWO CONSECUTIVE RUNS** — first consecutive 12/12! **Run 0x26090442: case_00 (axis 0 POS repeat 0) achieved 12/12 in THREE CONSECUTIVE RUNS** (0x26090440, 0x26090441, 0x26090442) — first 3-peat! **Run 0x26090443: streaks broken** — case_00 11/12, case_04 11/12. **Run 0x26090449: axis-0 NEG hunting improved (6/12→11/12) but not eliminated**; case_00 POS r0 11/12, case_04 POS r0 8/12 (no hunting, velocity-limited settle). NEG direction and higher repeats show variance (4-12/12). **Run 0x2609044B: 0/16 cases 12/12, 5 cases 11/12** — EV3 Large axis 0 strong (case_00, 01, 02, 03 all 11/12), axis 1 weaker (8/12 across repeats). **Run 0x2609044C: 0/16 cases 12/12, 8 cases 11/12** — axis 0 4×11/12, axis 3 stiction fix worked. **Run 0x2609044D: DR-robust prop9_accel06 on hardware — axis 0 ALL 4 repeats 11/12 (excellent consistency, final error ~0°), axis 1 still hunting (6-8/12)** — confirms per-axis/hardware divergence despite identical gains.
- **EV3 Medium (axes 2,3)**: **SYMMETRIC CONFIG NOW USED** (kd_vel=0, endpoint_kp=2.0e-6) — simulation validated 12/12 for BOTH directions. **Run 0x26090440: axis 2 NEG repeat 0 achieved 12/12**; **Run 0x26090441: axis 2 NEG repeat 0 dropped to 9/12, axis 3 POS repeat 1 achieved 11/12**; **Run 0x26090442: axis 3 NEG repeat 2 achieved 11/12 (best for axis 3), axis 3 POS repeat 3 catastrophic final error 121°**; **Run 0x26090443: axis 3 NEG repeat 0 FIRST 12/12 (case_08), axis 3 POS repeat 3 FIXED (10/12, 0.0° final error)** — catastrophic 121° error eliminated by stiction break fix. **Run 0x26090449: case_13/15 EV3 Medium POS stiction stalls on reversal (1.1s breakaway)** — direction-reversal static friction despite start_duty=0.80, 4-tick pulse. **Run 0x2609044B: axis 2 NEG r0 first 11/12 (case_08), axis 3 POS stalls persist (case_13 10/12, case_15 8/12)**. **Run 0x2609044C: AXIS 3 STICTION FIX WORKED!** start_duty 0.80→0.90 for POS cases (case_13/15); both now 11/12; direction-reversal static friction overcome. **Run 0x2609044D: AXIS 3 STICTION FIX CONFIRMED** — case_13/15 both 11/12 with 0° final error.
- **ALL FOUR AXES HAVE 12/12 CONFIGS HISTORICALLY**: Milestone achieved in run 0x2609043B, but run-to-run variation prevents consistent reproduction. **2+ consecutive 12/12 achieved on case_00 (3 runs) and case_04 (2 runs)**. **Run 0x2609044B: 0/16 cases 12/12; Run 0x2609044C: 0/16 cases 12/12, 8 cases 11/12; Run 0x2609044D: 0/16 cases 12/12, 8 cases 11/12** — streaks broken by run-to-run variation.
- **Core 1 timing**: Excellent — 999-1001µs period, 102-208µs exec, **0 missed ticks** across all 16 cases (run 0x26090449, 0x2609044A, 0x2609044B, 0x2609044C, 0x2609044D).
- **Run-to-run variation**: Confirmed — EV3 Large POS 12/12 reproduced in runs 0x26090440, 0x26090441, 0x26090442 for case_00; case_04 12/12 in runs 0x26090440, 0x26090441. EV3 Medium symmetric config 7-12/12 consistent but no 2+ consecutive 12/12 yet. ~10% variance per axis. **Run 0x2609044B: 0/16 cases 12/12, 5 cases 11/12; Run 0x2609044C: 0/16 cases 12/12, 8 cases 11/12; Run 0x2609044D: 0/16 cases 12/12, 8 cases 11/12**.
- **Stiction Break Fix VERIFIED & CONFIRMED IN AUTONOMOUS**: Velocity threshold 5000→1000, pos-error activation works. EV3 Medium axes show no stiction stalls in autonomous runs 0x26090440, 0x26090441, 0x26090442, 0x26090443. **Run 0x26090449: case_13/15 EV3 Medium POS stiction stalls on reversal (1.1s breakaway)** — direction-reversal static friction despite start_duty=0.80, 4-tick pulse. **Run 0x2609044B: axis 3 POS stalls persist (case_13 10/12, case_15 8/12)**. **Run 0x2609044C: AXIS 3 STICTION FIX WORKED!** start_duty 0.80→0.90 for POS cases (case_13/15); both now 11/12; direction-reversal static friction overcome. **Run 0x2609044D: AXIS 3 STICTION FIX CONFIRMED** — case_13/15 both 11/12 with 0° final error.
- **Symmetric EV3 Medium Config**: Simulation 12/12 for both NEG/POS; hardware 7-12/12 consistent (vs 4-9/12 with asymmetric config).
- **Simulator Enhancement Validated**: All 16 autonomous tuning matrix cases pass 12/12 in simulation with Stribeck friction, cogging torque, and thermal model. Simulation deterministic (no run-to-run variation) vs hardware ~10% variation. Gap confirms need for stochastic parameters in sim.
- **Timeout Fix Applied**: Extended `TUNING_CORE_PAUSE_TIMEOUT_US` (10k→100k) and `TUNING_WATCHDOG_MS` (5k→30k) in `bench/autonomous_tuning.c` allowed all 16 cases to complete (previously stopped at case 9 due to core1 pause timeout).
- **Sim Calibration BREAKTHROUGH (2026-09-06)**: The sim now reproduces the physical EV3 Large endpoint limit cycle (13.9 Hz vs physical 13.6 Hz, 8.2° pp vs physical 6.2° pp). Root cause: the sim's plant used 5ms observer matrices at 1ms steps (5x too fast) + missing voltage lag. **Key prediction: vel_window=10 eliminates the limit cycle** (the windowed speed estimate's phase lag is the primary cause). Run 47 only tested vel_window=60 (wider, made it worse) — the narrower direction was never tested on hardware.
- **Domain Randomization Harness Implemented (2026-09-08 — prior session)**: `tools/run_validation.py` now supports `--mode dr` (DR validation), `--mode backlash` (backlash sweep), `--mode vel_window` (vel_window sweep under encoder noise). `tools/simulate_motor.py` added `--vel-noise-std` for Gaussian velocity measurement noise. DR validation worst-case: EV3 Large 2/12, EV3 Medium 4/12. vel_window=10 for EV3 Large robust to noise up to 5000 mdeg/s.
- **vel_window Sweep Results (2026-09-08 — prior session)**: EV3 Large: vel_window=5/10 achieve 10-11/12 pass across all noise levels (0-5000 mdeg/s); vel_window=20/40/60 only 2-3/12 pass. EV3 Medium: all vel_window values achieve 12/12 pass even with 5000 mdeg/s noise — very robust.
- **Backlash Sweep Results (2026-09-08 — prior session)**: EV3 Large: 11/12 pass up to 2.5° backlash. EV3 Medium: 12/12 pass up to 2.5° backlash + 2x friction + doubled static friction. Symmetric config very robust in sim.
- **DR Gain Tuning Results (2026-09-08 — prior session)**: EV3 Large DR baseline worst=2/12. **Killer combo: transport delay (4ms) + backlash (2.5°) = worst=2/12**. DR-robust gains found: prop9_accel06 (kp_pos=2.0e-4, kp_vel=1.0e-5, endpoint_kp=2.5e-6, accel_scale=0.60) achieves DR worst=8/12 (4× improvement). Trade-off: nominal 12/12→10/12. EV3 Medium already DR-robust (worst=4/12, all vel_window 12/12 with noise). Target worst≥11/12 not yet met.
- **Run 0x2609044D Results (this session)**: ✅ **EV3 Large axis 0: ALL 4 repeats 11/12** — DR-robust gains working excellently on this axis (final error ~0°). ✅ **EV3 Large axis 1: Still hunting (6-8/12)** — identical gains, dramatically worse → confirms per-axis/hardware divergence. ✅ **EV3 Medium axis 3: POS cases 11/12** with start_duty=0.90 — stiction fix confirmed working. ✅ **EV3 Medium axis 2: POS stalls persist** (case_09 10.5° final error) — needs start_duty=0.90 for POS cases. ✅ **vel_window=10 for axis 3 works well** (all 10-11/12). ✅ **Core 1: PERFECT** — 999-1001µs period, 0 missed ticks across all 16 cases.

### Documentation Updates (2026-09-08 — this session)
- **Domain Randomization Harness Implemented** (prior session): `tools/run_validation.py` now supports `--mode dr` (DR validation), `--mode backlash` (backlash sweep), `--mode vel_window` (vel_window sweep under encoder noise). `tools/simulate_motor.py` added `--vel-noise-std` for Gaussian velocity measurement noise.
- **Run 0x2609044A** (2026-09-08): Autonomous validation — axis 2 NEG first 12/12; axis 3 POS stiction stalls persist (9-10/12); vel_window=10 for axis 3 helped slightly. 16/16 traces, Core 1: 999-1001µs period, 0 missed ticks.
- **Run 0x2609044B** (2026-09-08): Autonomous validation — 0/16 cases 12/12, 5 cases 11/12; EV3 Large axis 0 strong (3×11/12), axis 1 weaker (8/12), axis 3 POS stalls persist. 16/16 traces, Core 1: 999-1001µs period, 0 missed ticks.
- **Run 0x2609044C** (2026-09-08): Autonomous validation — **Axis 3 stiction fix WORKED!** start_duty 0.80→0.90; 8 cases 11/12 (case_13/15 now 11/12), EV3 Large axis 0 4×11/12. 16/16 traces, Core 1: 999-1001µs period, 0 missed ticks.
- **Run 0x2609044D** (2026-09-08): Autonomous validation — **DR-robust prop9_accel06 on hardware**: axis 0 ALL 4 repeats 11/12 (final error ~0°), axis 1 still hunting (6-8/12) → confirms per-axis/hardware divergence. Axis 3 POS cases 11/12 with start_duty=0.90 CONFIRMED. Axis 2 POS stalls persist (needs start_duty=0.90). vel_window=10 for axis 3 works well. 16/16 traces, Core 1: 999-1001µs period, 0 missed ticks.
- `hal/hal_tuning_log.h`: Run ID incremented to 0x2609044E (ready for next run)
- `docs/resume/2026-09-08_sim_to_real_report_analysis.md`: Sim-to-Real Report Analysis with dissenting viewpoint (created in prior autonomous session)
- `docs/resume/2026-09-08_index_autonomous_session.md`: Autonomous sim-only session documentation
- `docs/resume/2026-09-08_phase8_autonomous_run_0x2609044A.md`: Run 0x2609044A results
- `docs/resume/2026-09-08_phase8_autonomous_run_0x2609044B.md`: Run 0x2609044B results
- `docs/resume/2026-09-08_phase8_autonomous_run_0x2609044C.md`: Run 0x2609044C results
- `docs/resume/2026-09-08_phase8_dr_gain_tuning.md`: DR Gain Tuning session documentation (prior session)
- `docs/resume/2026-09-08_phase8_autonomous_run_0x2609044D.md`: Run 0x2609044D results (this session)
- **Simulation DR Results** (prior session): DR validation worst-case: EV3 Large 2/12, EV3 Medium 4/12. vel_window=10 for EV3 Large robust to noise up to 5000 mdeg/s. Backlash sweep: EV3 Large 11/12 up to 2.5°, EV3 Medium 12/12 up to 2.5° + 2x friction + doubled static friction.
- **DR Gain Tuning Results** (prior session): Killer combo = delay (4ms) + backlash (2.5°). prop9_accel06 (2.0e-4, 1.0e-5, 2.5e-6, 0.60) achieves DR worst=8/12. EV3 Medium vel_window=10 robust to 5000 mdeg/s noise.
- **Run 0x2609044D Hardware Results** (this session): prop9_accel06 on hardware: axis 0 worst=11/12 (excellent), axis 1 worst=6/12 (hunting persists). DR target worst≥11/12 not yet met for axis 1.

### Simulator Enhancements (2026-09-08 — prior session)
- **Encoder Noise Support**: Added `--vel-noise-std` parameter to `simulate_motor.py` for Gaussian velocity measurement noise (Domain Randomization)
- **Domain Randomization Validation Harness**: Full DR validation in `run_validation.py` with configurable draws, seeds, parameter ranges (R ±25%, friction 0.5–2×, backlash 0–2.5°, delay 0–4 ms, V_max ±15%, velocity noise 0–5000 mdeg/s)
- **Backlash Sweep Mode**: `--mode backlash` sweeps backlash for specific axis
- **vel_window Sweep Mode**: `--mode vel_window` sweeps vel_window under encoder noise for specific motor
- **DR Analysis**: Identified transport delay (4ms) and high friction (2x) as primary degradation sources for EV3 Large; vel_window=10 eliminates limit cycle and robust to noise
- **Files Modified**: `tools/simulate_motor.py`, `tools/run_validation.py`

---

## 🎯 Next Session Priorities

### 1. Charge Battery — **CRITICAL** (Board is ON but battery at 7.52V)
- Pack at 7.52V (Cell 1: 3.77V, Cell 2: 3.76V) — below recharge trigger (7.0V) but board still powered
- Must charge to ≥7.6V before resuming autonomous daemon
- Daemon will auto-resume from run 0x26090687 with CMA-ES state preserved (Gen 23)

### 2. EV3 Large Axis 1 Hunting — **HIGH PRIORITY** (per-axis hardware divergence persists)
- **Finding (554 runs = 461 + 93)**: Axis 0 consistently outperforms axis 1 with identical gains (CMA-ES Gen 23: kp=2.88e-4, kv=1.41e-5, end_kp=1.0e-6)
- **Run 0x26090686**: axis 0 (M1) best 11/12, axis 1 (M2) best 10/12 — confirmed per-axis/hardware divergence
- **Next action**: Test per-axis gains for axis 1 (e.g., endpoint_kp=3.0e-6 or kp_vel=1.5e-5) via CMA-ES or manual override

### 3. EV3 Medium POS Stiction — **HIGH PRIORITY** (PARTIALLY RESOLVED)
- **Finding**: start_duty=0.90-0.95 for POS working well on axis 3 (case_13 11/12), axis 2 still needs verification
- **Run 0x26090686**: case_09 (axis 2 POS) 12/12, case_13 (axis 3 POS) 11/12 — strong progress
- **Next action**: Verify axis 2 POS consistency across runs; tune start_duty if needed

### 4. Domain Randomization Promotion Criterion — **HIGH PRIORITY** (Sim-to-Real gap)
- **Problem**: 554 runs show sim-to-real mean agreement ~25-30%; sim predicts 10-12/12 for Large but hardware gets 5-11/12
- **Action**: Use DR harness in `tools/run_validation.py` — N draws × 16 cases, report worst-case
- **Promotion Change**: Require worst-case ≥ 11/12 across DR ensemble to promote to `motion_engine.c`

### 5. Formalize Duty Slew as Acceptance Metric — **HIGH PRIORITY**
- **Finding**: EV3 Large limit cycle = duty chatter (±full at ~13.6 Hz)
- **Action**: Add max endpoint duty slew as formal pass/fail metric in validation harness

### 6. Resume Autonomous Daemon — **HIGH PRIORITY** (after battery charge)
- **Command**: `python tools/autonomous_daemon.py --days 1 --rest-seconds 5`
- Will resume from run 0x26090687 with CMA-ES Gen 23 state preserved
- Target: push cost below 25, achieve first 12/12 passes on EV3 Large

### 7. EV3 Medium Consistency (Axes 2 & 3) — **MEDIUM PRIORITY**
- **Finding**: 461 runs — axis 2: 7-11/12; axis 3: 8-11/12 (run-to-run variation)
- **Action**: Sweep endpoint_kp (2.6e-6 → 3.0e-6) and accel_scale (0.31 → 0.35) for both axes in DR ensemble

### 8. Enable Gearbox Backlash in Sim & Sweep for Axis-3 — **MEDIUM PRIORITY**
- **Finding**: `simulate_motor.py` backlash model disabled by default
- **Action**: Enable backlash for EV3 Medium axis-3 plant, sweep 0.5–2.5°

### 9. Repeat-Dependent Degradation Analysis — **MEDIUM PRIORITY**
- **Finding**: Repeat-index variation persists (e.g., repeat 0 NEG 11/12 → repeat 3 POS 7/12)
- **Action**: Add inter-move cooldown, reset observer state between repeats

### 10. Feed Thermal Effects Back Into Electrical Model — **MEDIUM PRIORITY**
- Simulator tracks temperatures open-loop; close the loop: temp → R_phase, flux_factor → torque

### 11. Add Stochastic Variation to Simulator — **MEDIUM PRIORITY**
- Hardware ~10% run-to-run variation; simulation deterministic
- **Action**: Add encoder noise, parameter tolerances (±5-10%), voltage noise

### 12. Phase 8 (Drive Base) — **BLOCKED**
- Cannot proceed until 2+ consecutive 12/12 runs on all 4 axes
- Current: 0/4 axes with consecutive 12/12 (best: axis 0 2/16 passes in single run 454)

| # | Symptom | Verified root cause | Fix location |
|---|---------|--------------------|--------------|
| 1 | White box after Motor 4 in dark mode | `tk.Canvas` in Motors/Servos tabs never recolored — `toggle_dark_mode()` only updates `console_output` + `i2c_results`, not the two scroll canvases | Dashboard: add `canvas.configure(bg=...)` for both tab canvases in `toggle_dark_mode()` |
| 2 | Servo pulse shows port number | **NOT reproducible from current code.** Parser verified correct (`>> Servo %d pulse=%lu us` → `servo_pulses[idx]` → `pulse_label`). Only 2 writes to `servo_pulses`: init `[1500×4]` + correct parser. Two separate labels exist: `pulse_label` (status, top) and `pulse_display` (slider, live). Likely stale observation from before the `E n 0` write-as-query fix, OR user reading the slider's `pulse_display`. **Action: re-observe on current build; if still wrong, capture which label + what was clicked.** | Re-test on hardware; no code change indicated yet |
| 3 | "Scan I2C Bus" shows only "Scanning port 16" | **FIRMWARE RACE (confirmed)**: `hal_battery_service()` runs every 20 ms (`BATTERY_US=20000`) and calls `hal_i2c_select_port(16)`. A port-16 scan takes ~112 ms (112 addrs × 1 ms probe) → battery service fires ~5× mid-scan, re-selecting the mux and corrupting probes. Few/no `Found:` lines emitted. | **FIRMWARE**: gate `hal_battery_service()` during a scan (set a `s_scan_active` flag in cmd `I`, skip battery service while set), OR pause battery during scan |
| 4 | Scanning individual port does not work | Same firmware race as #3 (single-port scan is the affected path) | Same as #3 |
| 5 | Reconnect after power cycle doesn't find board | `_find_cdc_port()` matches description substrings ('Pico'/'USB'/'Serial') — unreliable, never checks `port.vid == 0x2E8A` (Raspberry Pi). Also `_attempt_reconnect` doesn't reschedule after a failed CDC attempt → loop stalls | Dashboard: match `port.vid == 0x2E8A`; ensure `_attempt_reconnect` always calls `_start_reconnect_timer()` on failure |

**Key correction to earlier note**: The I2C scan problem is a **firmware bug** (battery-service/mux race), not a dashboard parser bug. Dashboard cannot fix #3/#4 — needs a firmware change. The `E`/`S`/`I`/`L`/`y` parsers were all re-verified correct against exact firmware printf formats.

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
| Agent rules | `../../AGENTS.md` |

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

## ⚡ Autonomous Mode Update (2026-09-12)

**Controlled autonomous execution operational.**
- **Automatic execution**: The pipeline builds, flashes, runs 16 test cases, extracts flash, and verifies freshness automatically.
- **Safety rules enforced automatically**: motors coasted (`coast_all()`) at AUTO_FINISH; battery gate (pack ≥6.5V, cells ≥3.0V, age ≤250ms) enforced by `autonomous_tuning.c`; board state checked via `check_bootsel.ps1` before flash.
- **Flash freshness assertion**: `flash_extract_decode.py` verifies that extracted `run_id` matches expected run and that trace CRC is fresh.
- **Documentation updated**: session resume files (`docs/resume/*.md`) and `index.md` updated at every verified checkpoint.

---

*Workflow v1.0 established 2026-09-04. Update this file at every session end.*