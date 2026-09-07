# Assumptions Register — EVN ALPHA Performance

> **RESUME POINT (2026-09-05, Autonomous Run 0x26090443 Complete):**
> - **Run 0x26090443**: 4th consecutive validation — case_08 (EV3 Medium axis 3 NEG repeat 0) **FIRST 12/12**; case_15 (axis 3 POS repeat 3) catastrophic 121° error **FIXED** (10/12, 0.0° final error). 16 cases, 16/16 traces. Core 1: 999-1001µs period, 0 missed ticks.
> - **Stiction Break Fix CONFIRMED IN AUTONOMOUS**: case_15 final error went from 121.211° (run 0x26090442) to 0.0° (run 0x26090443). No stiction stalls in runs 0x26090440-43.
> - **Symmetric EV3 Medium Config VALIDATED**: Simulation 12/12 for both NEG/POS directions; hardware 7-12/12 consistent (vs 4-9/12 with asymmetric config).
> - **Run-to-run variation persists**: ~10% per axis. Streaks broken: case_00 (3-peat) now 11/12, case_04 (2-peat) now 11/12.
> - **Timeouts Fixed**: Extended TUNING_CORE_PAUSE_TIMEOUT_US (10k→100k) and TUNING_WATCHDOG_MS (5k→30k) allowed all 16 cases to complete.
> - **Dashboard 10/10 bugs fixed** (A-J from firmware console audit) in `tools/evn_dashboard.py`
> - **D7 IMPLEMENTED**: Console idle timeout (120s) + heartbeat protocol (`h`/`H`, `r`/`R`) enabled in `EVN_ALPHA_Performance.c` for autonomous↔console handoff.
> - Board: Console firmware (EVN_AUTONOMOUS_TUNING=0), USB CDC functional after power cycle
> - Next: 5th consecutive autonomous validation run 0x26090444 (target 2+ consecutive 12/12 on all 4 axes; case_08 achieved first 12/12). Phase 8 Drive Base blocked until achieved. EV3 Medium needs endpoint_kp/accel_scale sweep for consistency.

Every assumption made during development that is **not** marked `[GROUND TRUTH]` in the specs and has **not** been independently verified against hardware. **Review and confirm/refute each before we build dependent phases on top.** Each entry: the assumption, where it's baked in, why we made it, and how to falsify it.

Legend: ✅ confirmed · ❓ needs confirmation · ⚠️ known-deviation (accepted, monitor)

---

## A. Electrical / Timing

| # | Assumption | Where | Basis / Why | Falsify By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| A1 | System clock runs stably at **200 MHz** with `PICO_USE_FASTEST_SUPPORTED_CLOCK=1` | `CMakeLists.txt` | Spec §4 mandate; boot report confirmed `clk_sys=200000000` | 96 s full-load test (motors+I2C+PIO+Core 1) clean, battery steady | ✅ (96 s clean); soak in Phase 9 |
| A2 | I2C at **400 kHz** is within every attached device's tolerance | `hal_i2c.c` | Spec §7.3 default; BQ25887 works at it | Scan + read every planned sensor type at 400 kHz | ✅ BQ only |
| A3 | **5 ms** ADC settle after BQ25887 one-shot trigger (not 3 ms) | `hal_battery.c` `BQ_ADC_SETTLE_US` | Empirical — 3 ms returned 0s, 5 ms returned valid | Scope the ADC-ready flag / poll conversion-done bit instead of fixed delay | ❓ confirm no marginal reads |
| A4 | Battery reads **~0.9% low** consistently. Data points: loaded 7.12 V (meter 7.18), **no-load 7.257 V (meter 7.32)**. Constant offset, not drift | `hal_battery.c` | Two independent multimeter comparisons, consistent direction | Phase 9: apply calibration constant. **Also: log back-to-back readings over time (variance) to size the ADC filter for the motor controller** | ⚠️ monitor (action item) |
| A5 | Encoder 1 kHz FIFO drain is fast enough that the RX FIFO never overflows at max motor speed | `hal_encoder.c` | ~1150 counts/s observed ≪ FIFO capacity at 1 kHz | Max-RPM spin; check for missed steps vs known revolutions | ❓ needs max-speed test |
| A6 | Encoder scale ground truth **RESOLVED**: EVN `evn_motor_defs.h` `LEGO_PPR=180` pulses/rev; EVN counts all 4 edges → **720 edges/rev** (Pybricks counts 1 pin → 360). `counts_per_rev=720`, substeps/rev = 720/4×256 = 46080 | `motion/motion_engine.c`, main `CPR[]` | EVN library ground truth | Physical: 360° command should turn output exactly 1 rev | ❓ verify on hardware |

## B. Architecture / Concurrency

| # | Assumption | Where | Basis / Why | Falsify By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| B1 | **Core 0 owns all I2C/UART/SPI hardware**; Core 1 will only consume lock-free caches | `hal_*`, I2C Spec §2 | Prevents bus deadlock; spec dual-core plan | Phase 1 Core 1 bring-up | ❓ |
| B2 | Core 0 scheduler has headroom alongside the I2C governor | task-table in `EVN_ALPHA_Performance.c` | All services complete ≪ their period | Phase 1: encoder service moved to Core 1; Core 1 loop body ≤15 µs/tick (1.5%) | ✅ Phase 1 |
| B3 | Mux **channel caching** (skip reselect on same port) is safe — no other master changes the TCA9548A behind our back | `hal_i2c.c` `s_cached_channel` | We are the only I2C master on these buses | External write to mux → stale cache → wrong port. Recovery: `hal_i2c_deselect_all()` | ✅ (sole master) |
| B4 | `hal_i2c_*` blocking calls with 5 ms timeout are acceptable on Core 0 (they never run on the RT path) | `hal_i2c.c` | Spec §4.1 default 5000 µs | Confirm no RT consumer calls them directly | ✅ by design |
| B5 | Lock-free caches (battery seqlock; Core 1 status seqlock) correct cross-core | `hal_battery.c`, `motion/core1.c` | seqlock + `__dmb` | Core 1 status read cleanly by Core 0 under load; no torn reads in 88k-tick run | ✅ Phase 1 |
| B6 | TinyUSB has exactly one execution owner and packet-sized class FIFOs | `CMakeLists.txt`, `EVN_ALPHA_Performance.c` | SDK worker owns `tud_task`; no direct `tud_*`; full-speed TX/RX FIFOs are 64 B | Ten full dumps, packet-size correction, six battery-gated block-pulled cases | ✅ bulk USB + packet FIFO pass |
| B7 | Core 1 hardware-alarm callback remains on Core 1 with zero missed deadlines | `motion/core1.c` | Highest-priority direct-register ISR installed from Core 1 and linked in SRAM | 53,932-tick idle run + 16-case loaded sweep | ✅ 1000-1000 us idle; zero misses |
| B8 | Pybricks 5 ms observer remains valid when driven by five-sample mean applied voltage inside the 1 kHz controller | `motion/motion_engine.c` | Preserves generated model timestep and integrated input voltage | Compare observer state/stall behavior against encoder on both motor types | ❓ post-fix HITL |

## C. Pin / Peripheral Mapping

| # | Assumption | Where | Basis / Why | Falsify By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C1 | PIO partition: **pio0 = encoders (SM0–3), pio1 = servos (SM0–3)** is a stable, non-conflicting split | `hal_encoder.c`, `hal_servo.c` | PLAN §6 risk mitigation; 4+4 = 8 SMs across 2 blocks | PIO instr budget audit when motion engine lands | ✅ verified working |
| C2 | **PWM Slice 5 stays with Motor 2** (GP26/27); servos never claim hardware PWM | `hal_servo.c` | Spec §9.1 conflict resolution | Confirm Motor 2 PWM unaffected while servos run (done — both verified) | ✅ |
| C3 | Encoder sign conventions: M1/M3/M4 confirmed correct (M4=B-lower sign-flip works; tracked 360.4°). **M2 (port 2) runaway was a faulty motor — swapped in a NEW EV3 Large; re-tested and it tracks like the others (converges 0.12°).** | `hal_encoder.c` `s_hw`/`s_sign` | Tuning runs | Full test: M2 tracks like M1/M3/M4 | ✅ (new motor verified) |
| C4 | Per-motor direction defaults (+1) are correct for all 4 (M2 confirmed after motor swap) | `hal_motor.c` `s_dir` | All 4 verified | Per-motor HITL on M2 after swap | ✅ all 4 |
| C5 | UART **115200 8N1** is the right default for both serial headers | `hal_uart.c` | Spec §10 `EVN_UART_DEFAULT_BAUD` | Peripherals that need other bauds use the init arg | ✅ by API |

## D. Tooling / Process

| # | Assumption | Where | Basis / Why | Falsify By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| D1 | The RP2040 is the **only** USB-CDC device (VID `0x2E8A`) on the dev machine, so `serial_capture.py` auto-detect is unambiguous | `tools/serial_capture.py` | Single-board dev setup | Multiple RP2040s plugged in → wrong port | ⚠️ known limitation |
| D2 | Build stays on `PICO_BOARD pico` + flash overrides; a custom board header is deferred to Phase 9 | `CMakeLists.txt` | Custom header broke USB enumeration | Phase 9 board-header rework with correct TinyUSB defaults | ⚠️ deferred |
| D3 | Boot **LED heartbeat (3×)** is sufficient liveness signal without a console | `EVN_ALPHA_Performance.c` | Convenient diagnostic | — | ✅ working |
| D4 | **USB CDC is NOT wedging** after BOOTSEL→app transition; the issue is port enumeration timing in `serial_capture.py` (fixed timeout, no retry logic) | `tools/serial_capture.py` | Observed PermissionError 13, but may be host-side | Add retry-with-backoff to serial_capture; test power-cycle vs. wait-only recovery | ⚠️ partially addressed — dashboard thread-safety fixes (Bug C) eliminate Tkinter crashes from non-main threads |
| D5 | **BOOTSEL detection via `check_bootsel.ps1` polling** is reliable and fast; WMI event subscription (`wait_bootsel.ps1`) is timing-dependent fallback | `tools/check_bootsel.ps1`, `tools/wait_bootsel.ps1` | Empirical: polling works; WMI misses events if not initialized early | Compare both methods across 10+ flash cycles | ✅ polling confirmed |
| D6 | **Run ID format** `0xYYMMDDNN` (year, month, day, sequence) in `hal/hal_tuning_log.h`; auto-increment per autonomous run | `hal/hal_tuning_log.h` `EVN_TUNING_RUN_ID` | Convention established 2026-09-02 | Check git history for run ID sequence | ✅ documented |
| D7 | **Console firmware idle timeout** (120s after last command completion) + heartbeat protocol (`h`/`H`, `r`/`R`) will prevent USB CDC issues and enable autonomous handoff | `EVN_ALPHA_Performance.c` (implemented) | Console blocks waiting for input | Implement and test autonomous→console→autonomous cycles | ✅ implemented & tested in run 0x2609043C |

---

## E. Simulator Fidelity (2026-09-08 — Sim-to-Real Report Analysis)

| # | Assumption | Where | Basis / Why | Falsify By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| E1 | **Simulator uses deterministic physics** — no injected parameter noise, no measurement noise, no backlash/compliance unless explicitly enabled | `tools/simulate_motor.py` (PlantModel, EncoderSim) | Current validation harness runs single deterministic sim per config; no stochastic terms in codebase | Add Domain Randomization harness and verify pass-rate distribution changes; compare worst-case vs nominal | ❓ needs DR harness |
| E2 | **Encoder model includes quantization but no Gaussian velocity measurement noise** | `tools/simulate_motor.py` EncoderSim | Quantization present (`round()` in substeps/edges); grep confirms no `np.random` or `random.gauss` usage | Inject Gaussian noise; re-sweep vel_window for robustness | ❓ needs noise injection |
| E3 | **Gearbox backlash/compliance model is written but disabled by default** (`gearbox_backlash_mdeg = 0`) | `tools/simulate_motor.py` PlantModel | Two-inertia model with backlash & stiffness implemented but commented as "requires careful tuning" | Enable backlash sweep for axis-3 (0.5–2.5°); check for case_13/15 stall reproduction | ❓ needs enable & sweep |
| E4 | **Plant and observer run at same rate (1 ms)** — velocity lag mismatch mitigated by `voltage_lag_ms` term but not swept | `tools/simulate_motor.py` PlantModel | Plant uses 1 ms step; observer matrices derived from 5 ms step; voltage_lag added as fix but not validated across rates | Sweep plant step rate vs observer matrices; check limit cycle sensitivity | ❓ needs rate sweep |

---

## Before Phase 8 (Drive Base) we must close:

- **Sim-to-real gaps** — EV3 Medium residual vibration (14° p-p), EV3 Large tracking error (now <2.0° with W40_K50), EV3 Medium negative direction (8-9/12 vs 12/12 sim)
- **A6 / A5** — confirm encoder counts-per-revolution matches motor datasheet CPR (drives PID gain units) and no FIFO overflow at max RPM.
- **D4** — verify USB CDC root cause (wedging vs. enumeration timing) and fix `serial_capture.py` (partially addressed: dashboard thread-safety fixes eliminate Tkinter crashes)
- **D7** — implement console idle timeout + heartbeat protocol for autonomous handoff ✅ **IMPLEMENTED & TESTED** (run 0x2609043C)
- **Consecutive 12/12 validation** — Need 2+ consecutive autonomous runs with 12/12 on all 4 axes (current: 2×12/12 on EV3 Large pos, 11/12 on others)

Everything else is either confirmed ✅ or an accepted, monitored deviation ⚠️.
