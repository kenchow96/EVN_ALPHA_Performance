# Assumptions Register — EVN ALPHA Performance

> **RESUME POINT (2026-09-01, end of tuning session):** Phase 7 motion-engine bring-up.
> Board has console firmware flashed (listening for serial commands). Motors coasted.
> **Hardware change: port 2 motor swapped to a NEW EV3 Large.** Next session: re-test M2
> (should track like M1/M3/M4 now), confirm M1 EV3-Large per-model gains, then close Phase 7.
> Tune live over `tools/tune_session.py` (holds port open) — see AGENTS.md.

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

## C. Pin / Peripheral Mapping

| # | Assumption | Where | Basis / Why | Falsify By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C1 | PIO partition: **pio0 = encoders (SM0–3), pio1 = servos (SM0–3)** is a stable, non-conflicting split | `hal_encoder.c`, `hal_servo.c` | PLAN §6 risk mitigation; 4+4 = 8 SMs across 2 blocks | PIO instr budget audit when motion engine lands | ✅ verified working |
| C2 | **PWM Slice 5 stays with Motor 2** (GP26/27); servos never claim hardware PWM | `hal_servo.c` | Spec §9.1 conflict resolution | Confirm Motor 2 PWM unaffected while servos run (done — both verified) | ✅ |
| C3 | Encoder sign conventions: M1/M3/M4 confirmed correct (M4=B-lower sign-flip works; tracked 360.4°). **M2 (port 2) ran away negative regardless of sign/dir flips → hardware suspect; user swapped in a NEW motor on port 2** — re-test to confirm | `hal_encoder.c` `s_hw`/`s_sign` | Tuning runs | Full test: M2 should track 360 like M1/M3/M4 | ❓ re-test after motor swap |
| C4 | Per-motor direction defaults (+1) are correct for M1/M3/M4; M2 pending after hardware fix | `hal_motor.c` `s_dir` | M1/M3/M4 verified | Per-motor HITL on M2 after swap | ❓ M2 pending |
| C5 | UART **115200 8N1** is the right default for both serial headers | `hal_uart.c` | Spec §10 `EVN_UART_DEFAULT_BAUD` | Peripherals that need other bauds use the init arg | ✅ by API |

## D. Tooling / Process

| # | Assumption | Where | Basis / Why | Falsify By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| D1 | The RP2040 is the **only** USB-CDC device (VID `0x2E8A`) on the dev machine, so `serial_capture.py` auto-detect is unambiguous | `tools/serial_capture.py` | Single-board dev setup | Multiple RP2040s plugged in → wrong port | ⚠️ known limitation |
| D2 | Build stays on `PICO_BOARD pico` + flash overrides; a custom board header is deferred to Phase 9 | `CMakeLists.txt` | Custom header broke USB enumeration | Phase 9 board-header rework with correct TinyUSB defaults | ⚠️ deferred |
| D3 | Boot **LED heartbeat (3×)** is sufficient liveness signal without a console | `EVN_ALPHA_Performance.c` | Convenient diagnostic | — | ✅ working |

---

## Before Phase 7 (Motion Engine) we must close:

- **A6 / A5** — confirm encoder counts-per-revolution matches motor datasheet CPR (drives PID gain units) and no FIFO overflow at max RPM.
- **C3 / C4** — run all 4 motors, confirm each FWD physically matches its encoder count sign; set per-motor `hal_motor_set_direction`/`hal_encoder_set_sign` accordingly and record in NVM later.
- **B2 / B5** — Phase 1 lands the DWT harness + Core 1; measure loop latency and verify cache integrity under dual-core load.
- **A1** — confirm 200 MHz stability under combined full load (all motors + I2C + PIO running).

Everything else is either confirmed ✅ or an accepted, monitored deviation ⚠️.
