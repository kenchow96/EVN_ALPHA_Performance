# EVN ALPHA Performance — Comprehensive Audit Report
**Date**: 2026-09-05

## Executive Summary

This project suffers from severe **scatter, inconsistency, and technical debt** due to extended agentic development without proper consolidation. The most critical issue: **firmware default gains are stale and do NOT match documented "winning configurations"** — meaning the claimed performance breakthroughs were never actually flashed to the board.

## Critical Findings (Must Fix Before Proceeding)

### 1. Firmware Gains Are Stale — Performance Claims Are False
- **Location**: `motion/motion_engine.c` lines 111-130
- **Issue**: Default PID gains are v18-era values, not the validated configurations from autonomous runs
- **EV3 Large mismatch**:
  - Code: `kp_pos=2.2e-4, kp_vel=2.5e-6, endpoint_kp=1.0e-6`
  - Documented (since run 0x26090437): `kp_pos=4.0e-4, kp_vel=5.0e-6, endpoint_kp=1.0e-6`
- **EV3 Medium mismatch**:
  - Code: `kp_pos=3.0e-4, kp_vel=1.0e-6, accel_scale=0.30, endpoint_kp=1.0e-6, start_duty=0.65`
  - Documented (since stiction fix): `kp_pos=2.5e-4, kp_vel=1.0e-6, kd_vel=0, accel_scale=0.35, endpoint_kp=2.0e-6, start_duty=0.80`

> **Consequence**: All autonomous runs claiming 12/12 performance were actually running with outdated gains. The "Symmetric EV3 Medium config" validation in docs used different gains than what's flashed.

### 2. Blocking Delays Violate Core Real-Time Rule
- **Violations**: 
  - `EVN_ALPHA_Performance.c:569` - `busy_wait_ms(100)` before reboot
  - `EVN_ALPHA_Performance.c:609` - `busy_wait_ms(80)` in startup LED blink
  - `EVN_ALPHA_Performance.c:657` - `busy_wait_ms(100)` in idle timeout handler
  - `hal/hal_i2c.c:208-216` - Multiple `busy_wait_us(5)` in I2C recovery
- **Impact**: These violate AGENTS.md Rule #1 ("No sleep_ms/sleep_us or blocking delays").

### 3. Documentation & Process Breakdown
- **~48 stale artifact files** at repo root (`test_*.txt`, `sim_*.txt`, `trace_*.txt`, `validation_*.txt`)
- **bench/RESULTS.md not maintained** since 2026-09-02 — missing ~20 autonomous run summaries (violates PLAN.md §5)
- **NEXT_SESSION_PROMPT.md is stale** — claims next run ID is 0x26090439 (actual: 0x26090444)
- **Broken reference**: `docs/resume/index.md` references non-existent `docs/AGENTS.md` (actual file is `AGENTS.md` at repo root)
- **Phase numbering contradiction**: PLAN.md Status Board has two "Phase 8" rows and misnumbers Drive Base as Phase 9

### 4. Tooling Debt & Duplication
- **Dead/broken scripts**: `motion_sweep.py` (broken vs firmware), `tune_cmd.py`/`tune_session.py` (legacy), `analyze_trace.py` (superseded), `batch_sweep.py` (output incompatible), `sysid_motor.py`, `local_commit_bot.py`
- **Critical bug**: `flash_extract_decode.py` summary table is garbage — column mismatch makes all autonomous runs appear to fail
- **5 copies** of COM-port auto-detect logic, 4 copies of BOOTSEL wait logic
- **Dashboard thread-safety partially fixed** — `port_var.set()` still called from background threads

## Recommended Immediate Actions

### Priority 1: Fix Firmware Defaults (Same Day)
1. Update `motion/motion_engine.c` default gains to match documented winning configurations:
   - EV3 Large: `kp_pos=4.0e-4, kp_vel=5.0e-6, endpoint_kp=1.0e-6`
   - EV3 Medium: `kp_pos=2.5e-4, kp_vel=1.0e-6, kd_vel=0, accel_scale=0.35, endpoint_kp=2.0e-6, start_duty=0.80`
2. Replace blocking delays with non-blocking alternatives using `time_us_64()` elapsed-time checks
3. Remove dead code or add missing declarations:
   - `hal_button_set_callback()` (remove or declare in header)
   - `hal_battery_debug_regs()` and `hal_i2c_cached_channel()` (declare in headers)

### Priority 2: Consolidate Documentation & Process (Next 2 Days)
1. Archive/delete ~48 stale artifact files from repo root (move to `bench/results/archive/` or delete)
2. Update `bench/RESULTS.md` with all missing autonomous run summaries from `docs/resume/` files
3. Fix `NEXT_SESSION_PROMPT.md` or delete it (superseded by `docs/resume/index.md`)
4. Fix broken reference in `docs/resume/index.md`: change `docs/AGENTS.md` → `../AGENTS.md`
5. Correct PLAN.md Status Board phase numbering to match plan body

### Priority 3: Tooling Consolidation (Within Week)
1. Keep only canonical tools:
   - Flash: `flash_and_capture.py`, `flash_extract_decode.py` (fix summary-column bug)
   - Board detection: `check_bootsel.ps1` (primary), `wait_bootsel.ps1` (fix WMI fallback)
   - Dashboard: `evn_dashboard.py` (complete thread-safety fix)
   - Simulation: `simulate_motor.py`, `motor_models.json`, `run_validation.py` (fix CWD pollution)
   - Metrics: `motion_metrics.py`
2. Create `tools/_common.py` for shared logic (port detection, trace parsing)
3. Add `tools/requirements.txt` declaring dependencies
4. Remove/dead scripts: `motion_sweep.py`, `tune_cmd.py`, `tune_session.py`, `analyze_trace.py`, `batch_sweep.py`, `sysid_motor.py`, `local_commit_bot.py`

## Root Cause
Extended agentic development without:
- Regular consolidation of winning configurations into firmware defaults
- Enforcement of documentation-as-single-source-of-truth
- Tooling audits to remove dead/duplicated code
- Strict adherence to AGENTS.md rules (especially no blocking delays)

## Verification After Fixes
1. Reflash firmware with corrected gains
2. Run autonomous validation — should see performance match documented claims
3. Verify zero blocking delays in real-time paths
4. Confirm `bench/RESULTS.md` is current
5. Validate dashboard thread-safety under load

Without fixing the stale gains, all claims of performance breakthroughs are invalid — the actual flashed firmware is running outdated parameters.