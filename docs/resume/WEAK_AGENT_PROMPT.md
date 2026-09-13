# Weak Agent Handoff Prompt — EVN ALPHA Autonomous Tuning

Copy the block below verbatim into a fresh agent session to resume unattended
long-term tuning.

---

```
You are resuming the EVN ALPHA Performance autonomous long-term motor tuning
daemon. Work from the repository root:
c:\Users\kenne\OneDrive - Centre Of Robotics Excellence\CORE\Projects\EVN_ALPHA_Performance

STEP 1 — ORIENT (read, do not edit):
  1. Read docs/resume/index.md in full (canonical entry point + workflow).
  2. Read AGENTS.md (mandatory repository rules).
  3. Read docs/PLAN.md -> Status Board (active phase = 7v autonomous validation).
  4. Read docs/resume/2026-09-13_phase8_single_pass_0x26090687.md (last verified run).

STEP 2 — VERIFY HARDWARE IS READY:
  - Run: & tools/check_bootsel.ps1
    * If it prints a drive letter (e.g. "E:"), the board is in BOOTSEL and ready.
    * If it prints nothing / exits 1, STOP and ask the human to power on the board
      and confirm the USB cable is connected. Do NOT proceed without confirmation.
  - Battery was measured at 8.21 V (cells 4.09/4.08 V) on the last run; the daemon
    enforces a 6.0 V hard cutoff and a 7.0 V recharge-pause automatically.

STEP 3 — LAUNCH THE DAEMON (single command, runs unattended):
  python tools/autonomous_daemon.py --days 30 --rest-seconds 15

  What it does automatically each iteration (do NOT hand-edit gain numbers in C):
    - Calls CMA-ES (OnlineCMAOptimizer) for the next Large + Medium parameter candidate.
    - Runs a simulator pre-flight gate (tools/sim_integration.py) before any flash.
    - Bumps the run ID, builds autonomous firmware, flashes via picotool, runs all
      16 multi-regime cases, extracts + decodes tuning flash, verifies run-ID freshness.
    - Computes decoupled per-motor cost J = max(mean_M1, mean_M2) + 0.5*|Δ|.
    - Runs online SysID (tools/sysid_motor.py) to update tools/motor_models.json
      via EMA (alpha=0.25) from the physical traces — keeps the digital twin honest.
    - Logs one line to bench/results/endurance_log.csv and prunes storage.
    - Stops automatically on 16/16 cases at 12/12, on battery cutoff, or on Ctrl+C.

STEP 4 — MONITOR WITH READ-ONLY COMMANDS ONLY (never edit mid-run):
  - Latest progress:      Get-Content bench/results/endurance_log.csv | Select-Object -Last 10
  - Disk footprint:       python tools/storage_manager.py
  - Current run ID:       Select-String -Path hal/hal_tuning_log.h -Pattern "EVN_TUNING_RUN_ID"

STEP 5 — STOP SAFELY:
  - Send Ctrl+C. The daemon catches it, coasts all motors (hal_motor_coast_all()),
    and leaves the board idle. Never kill the process forcibly.

HARD CONSTRAINTS (from AGENTS.md — non-negotiable):
  - Never sleep/poll in firmware real-time paths; never add heap allocation to Core 1.
  - Always coast motors at the end of any test.
  - Before any flash, confirm BOOTSEL via tools/check_bootsel.ps1; only ask the human
    to confirm power if the board cannot be detected.
  - Do NOT hand-edit gain numbers or the s_cases array; the daemon owns them.
  - One flash+verify cycle = tools/flash_extract_decode.py. Never hand-chain
    flash/sleep/capture.
  - Commit at every verified checkpoint and update docs/PLAN.md Status Board.

PRIORITIES TO PUSH (from index.md Next Session Priorities):
  1. EV3 Large axis 1 (M2) hunting — per-axis hardware divergence persists despite
     identical gains to M1; DOB is now active to reject it. Watch case_05/case_01.
  2. EV3 Medium POS stiction — confirm start_duty breakout holds on the new
     micro-step cases (case_11/13/15).
  3. Drive the worst-case DR cost down; target first 12/12 on an EV3 Large axis.
  4. Watch the new max_duty_slew metric — it is now penalized in the cost function
     to discourage endpoint limit-cycle chatter.

Begin now. Report only new facts: changed files, validation output, commit hash.
```
