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

---

## 📋 Quick Reference — Current State (as of 2026-09-04 end — run 0x26090435 complete)

| Item | Value |
|------|-------|
| **Board** | Console firmware (`EVN_AUTONOMOUS_TUNING=0`), USB CDC functional after power cycle |
| **Motors** | M1/M2 = EV3 Large, M3/M4 = EV3 Medium **UNLOADED** (new motors, no wheels) |
| **Build** | `build/EVN_ALPHA_Performance.uf2` = non-autonomous console with v23 gains |
| **Next Run ID** | `0x26090436` (in `hal/hal_tuning_log.h`) |
| **Autonomous Tuning** | Disabled in `CMakeLists.txt` |
| **Hardware Validation** | ✅ Complete — 112/112 cases run across 7 autonomous runs, all traces decoded |

### Winning Configurations (Promoted to `motion_engine.c`)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large | **2.8e-4** | **3.5e-6** | 8e-7 | **0** | 0 | 0.70 | 1.0e-6 |
| EV3 Medium NEG | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35-0.40** | **2.0e-6** |
| EV3 Medium POS | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **1.0e-6** |

### Key Results Summary
- **EV3 Medium NEG (axis 2)**: **BREAKTHROUGH 12/12 VALIDATED** — TWO configurations with kp=2.5e-4, kv=1.0e-6, endpoint_kp=2.0e-6 (accel_scale 0.35 & 0.40). Max track error 1.43-1.56° (< 2.0° threshold). First 12/12 on unloaded motors!
- **EV3 Medium POS (axis 3)**: 11/12 with kp=2.5e-4, kv=1.0e-6, endpoint_kp=1.0e-6, accel_scale=0.35 (1.95° error). Close to 12/12 but oscillates on POS approach.
- **EV3 Large (axes 0,1)**: Consistent 10/12 with tracking error 3.18-4.41°. Best: kp=2.8e-4, kv=3.5e-6 (3.18° error). Need <2.0° for 12/12.
- **Core 1 timing**: Excellent — 999-1001µs period, 194-211µs exec, 0 missed ticks across all 112 cases.
- **Sim-to-real gap**: EV3 Large tracking error ~3.2° (threshold 2.0°). EV3 Medium NEG CLOSED (12/12). EV3 Medium POS needs 12/12.
- **Hardware change**: EV3 Medium motors on ports 3/4 now UNLOADED (no wheels) — significantly changes dynamics. REDUCED gains work better. Higher endpoint_kp critical for NEG.

### Documentation Updates (2026-09-04 — this session)
- `AGENTS.md`: Already updated in prior session
- `PLAN.md`: Efficiency Protocol §2.13-2.15 (BOOTSEL check, documentation, time estimates), Key Protocols table
- `PROCEDURES.md`: Restructured with Board Detection, Autonomous Pipeline, Console Timeout/Heartbeat, Git Workflow
- `ASSUMPTIONS.md`: D4 (USB wedging investigation), D5 (BOOTSEL polling primary), D6 (run ID format), D7 (console timeout/heartbeat)
- **Run 0x26090433**: kff_accel sweep (0-2e-6) for EV3 Large — kff=0 best. EV3 Medium retune for unloaded motors. 16 cases.
- **Run 0x26090434**: kd_vel sweep for EV3 Large — kd=0 best. EV3 Medium POS REDUCED gains = 11/12 BREAKTHROUGH. 16 cases. kd_vel not stored in header (fixed for next run).
- **Run 0x26090435**: EV3 Medium NEG 12/12 VALIDATED with TWO configs (accel_scale 0.35 & 0.40). EV3 Medium POS 11/12 reproduced. EV3 Large 10/12. 16 cases. kd_vel properly stored in header.

---

## 🎯 Next Session Priorities

### 1. EV3 Medium NEG (axis 2) — **VALIDATED 12/12** → Need 2+ consecutive runs
- **BREAKTHROUGH**: TWO 12/12 configs with kp=2.5e-4, kv=1.0e-6, endpoint_kp=2.0e-6 (accel_scale 0.35 & 0.40)
- Target: Reproduce case 8 & 10 params for 2+ consecutive 12/12 autonomous runs
- This axis is READY for Phase 8 once reproducibility confirmed

### 2. EV3 Medium POS (axis 3) — Push 11/12 to 12/12
- Current: kp=2.5e-4, kv=1.0e-6, endpoint_kp=1.0e-6, accel_scale=0.35 → 11/12, 1.95° error
- NEG move (case 12) = 11/12; POS moves = 7-10/12 (oscillation on approach)
- Try: increase endpoint_kp to 1.5-2.0e-6, reduce kp_pos to 2.3-2.4e-6, add kd_vel 0.5e-6 for damping

### 3. EV3 Large (axes 0,1) — Close 3.2° → 2.0° tracking gap
- Best: kp=2.8e-4, kv=3.5e-6 → 10/12, 3.18° error (all cases 10/12 with 3.18-4.41°)
- kd_vel HARMFUL (proven); kff_accel HARMFUL (proven); both = 0
- Paths: (a) Motor model recalibration from HW system ID, (b) Increase kp_pos to 3.0-3.5e-4, kv to 4.0-4.5e-6

### 4. Motor Model Calibration (High Priority)
- Run system identification on hardware for EV3 Large and EV3 Medium (unloaded)
- Update `tools/motor_models.json` with HW-identified parameters
- Re-run digital twin with calibrated models to verify sim-hw alignment

### 5. Require 2+ Consecutive 12/12 Before Phase 8
- EV3 Medium NEG: **VALIDATED 12/12** → Need 2+ consecutive 12/12 runs
- EV3 Medium POS: 11/12 → Need 12/12 then 2+ consecutive
- EV3 Large: Need 12/12 with tracking error < 2.0°

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