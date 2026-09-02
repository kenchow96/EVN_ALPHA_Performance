# Next Session Priorities (2026-09-04)

**Date**: 2026-09-04  
**Source**: Merged from `docs/NEXT_SESSION.md`

## Session End State (2026-09-03)
- **Board**: Console firmware running, USB CDC functional (after power cycle)
- **Motors**: M1/M2 = EV3 Large, M3/M4 = EV3 Medium (gains set correctly)
- **Build**: `EVN_AUTONOMOUS_TUNING=0`, run ID `0x2609022A`
- **Key results**: v15 autonomous run completed — v13 breakthrough (accel_scale=0.30 → 12/12 for EV3 Medium negative) NOT replicated in 2 consecutive runs (v14, v15 both 8/12). Best EV3 Medium negative: 10/12 with endpoint_kp=2.0e-6. EV3 Medium positive: 12/12 at 1100°/s. EV3 Large 800°/s: 11/12 ceiling.

---

## Next Session Priorities

### 1. Fix All Plumbing & Eliminate Repeated Errors
- **Drive detection**: Python can't see mounted UF2 drive → use PowerShell WMI (validated) or `wmic logicaldisk get caption,volumename`
- **Timeout reduction**: Current 10-30s timeouts excessive; recovery gets values instantly
- **Error deduplication**: Document every error + fix in PROCEDURES.md; never re-debug same issue
- **Automation**: Create `tools/flash_extract_decode.py` — flash → wait for BOOTSEL (WMI) → extract → decode → summary in one command

### 2. Console Utility & USB Reliability
- **Assess console value**: Interactive tuning vs. autonomous batch — which delivers better data/hr?
- **USB CDC root cause**: RP2040 USB PHY wedges after BOOTSEL→app transition; power cycle only reliable fix
- **Alternatives**: 
  - UART console (GP0/GP1) for reliable serial without USB CDC
  - CMSIS-DAP + OpenOCD + GDB for debug console
  - `flash_and_capture.py` improvements for USB re-enumeration handling
- **Timeout optimization**: Reduce from 30s to 3-5s based on actual recovery timing

### 3. Digital Twin + Simulation-First Parameter Search
- **Build motor digital twin**: Use logged trace data (position, velocity, duty, current) + known motor parameters (EV3 Large/Medium CPR, inertia, friction, torque constant)
- **Simulation environment**: Python/NumPy or Julia for massively parallel parameter sweeps
- **Workflow**: 
  1. Sweep gains/profile params in simulation (1000s of configs in minutes)
  2. Identify top-N candidates by tracking error metrics
  3. Test candidates on hardware (autonomous batch)
  4. Update twin with real hardware data (system ID)
  5. Repeat until perfect control achieved
- **Tools**: `tools/simulate_motor.py`, `tools/system_id.py`, `tools/batch_sweep.py`

### 4. Perfect Control Before Uneven Loading
- **Current gaps**: EV3 Medium negative 1100°/s (8-10/12), EV3 Large 800°/s (11/12 ceiling)
- **Target**: 12/12 passes on all 4 axes at max speeds, both directions, unloaded
- **Only then**: Proceed to uneven loading, disturbance rejection, multi-axis coordination
- **Validation**: Autonomous batch must achieve 12/12 consistently across 2+ consecutive runs

---

*Session ended 2026-09-03. Board in console mode (USB CDC functional after power cycle). Motors tested with correct gains — M1/M2 EV3 Large, M3/M4 EV3 Medium. Ready for digital twin development.*