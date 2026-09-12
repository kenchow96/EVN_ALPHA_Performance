# Phase 8 Audit Remediation & Firmware Sync (run 0x2609044E)

**Date**: 2026-09-12

## Test Matrix
- Firmware sync: Updated default gains in `motion_engine.c` to match run 0x2609044E validated config
- I2C firmware race fix: Added scan-active guard in `hal_i2c.c`/`hal_battery.c`
- Run ID bump: `hal/hal_tuning_log.h` → 0x2609044E

## Results: 6/6 files modified, build passes

| File | Change |
| :--- | :--- |
| `motion/motion_engine.c` | EV3 Large defaults: kp_pos=2.0e-4, kp_vel=1.0e-5, endpoint_kp=2.5e-6, accel_scale=0.60, vel_window=10; EV3 Medium: vel_window=10 |
| `hal/hal_tuning_log.h` | EVN_TUNING_RUN_ID 0x2609044D → 0x2609044E |
| `hal/hal_i2c.c/h` | Added `s_scan_active` flag + getter/setter API |
| `hal/hal_battery.c` | `hal_battery_service()` defers when scan active |
| `EVN_ALPHA_Performance.c` | I2C scan command ('I') sets/clears scan-active flag |
| `docs/PLAN.md` | Status Board updated: 7v ✅ Complete + Firmware Updated |

## Key Findings
1. **Firmware defaults were stale** — `motion_engine.c` still had W40_K50 config (kp=4.0e-4, kv=5.0e-6) while run 0x2609044E validated DR-robust prop9_accel06 (kp=2.0e-4, kv=1.0e-5). All flashed firmware since 0x2609044E was running wrong gains.
2. **I2C firmware race confirmed & fixed** — `hal_battery_service()` called `hal_i2c_select_port(16)` every 20ms, corrupting user I2C scans (which take ~112ms). Added scan-active guard.
3. **Blocking delays already non-blocking** — Audit claimed `busy_wait_ms` at lines 569, 609, 657; these were already replaced with `time_us_64()` elapsed-time checks.
4. **HAL violation in core1.c:80** — Direct `hw_set_bits(&timer_hw->inte, ...)` for timer alarm setup. This is a legitimate real-time setup pattern; documented but not refactored.

## Infrastructure & Safety
- Build: Clean compile (0 errors)
- Core 1: PERFECT — 999-1001µs period, 0 missed ticks (from run 0x2609044E)
- Battery: Fresh samples every 20ms, lock-free cache
- I2C: Dual-bus 400 kHz with mux caching + scan protection

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| (no new flash — firmware sync only) | — | — |

## Updated Winning Configurations (Promoted to `motion_engine.c`)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel | start_duty | vel_window |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EV3 Large (axis 0) | **2.0e-4** | **1.0e-5** | 8e-7 | 0 | 0 | **0.60** | **2.5e-6** | 0.12 | **10** |
| EV3 Large (axis 1) | 2.0e-4 | 1.0e-5 | 8e-7 | 0 | 0 | 0.60 | 2.5e-6 | 0.12 | **10** |
| EV3 Medium (axis 2) | **2.5e-4** | **1.0e-6** | 8e-7 | 0 | 0 | **0.35** | **2.0e-6** | 0.80/0.90* | **10** |
| EV3 Medium (axis 3) | **2.5e-4** | **1.0e-6** | 8e-7 | 0 | 0 | **0.35** | **2.0e-6** | 0.80/0.90* | **10** |

* start_duty=0.80 for NEG, 0.90 for POS cases (stiction-break fix)

## Next Step
1. **Apply start_duty=0.90 to EV3 Medium axis 2 POS cases** in `bench/autonomous_tuning.c` (case_09, case_11) — mirror axis 3 fix
2. **Test vel_window=10 for EV3 Medium axis 2** in AUTO_RUN_MOTION logic
3. **Test per-axis gains for EV3 Large axis 1** (different from axis 0 — per-axis hardware divergence confirmed)
4. **Run Autonomous Validation 0x2609044F** with above fixes: `python tools/flash_extract_decode.py --timeout 900`
5. **Adopt Domain Randomization as Tuning Methodology** — use DR harness for worst-case gain selection
6. **Formalize Duty Slew as Acceptance Metric** — add max endpoint duty slew to validation harness