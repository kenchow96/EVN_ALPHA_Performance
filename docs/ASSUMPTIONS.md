# Assumptions Register — EVN ALPHA Performance

Every assumption made during development that is **not** marked `[GROUND TRUTH]` in the specs and has **not** been independently verified against hardware. **Review and confirm/refute each before we build the motion engine (Phase 7) on top.** Each entry: the assumption, where it's baked in, why we made it, and how to falsify it.

Legend: ✅ confirmed · ❓ needs confirmation · ⚠️ known-deviation (accepted, monitor)

---

## A. Electrical / Timing

| # | Assumption | Where | Basis / Why | Falsify By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| A1 | System clock runs stably at **200 MHz** with `PICO_USE_FASTEST_SUPPORTED_CLOCK=1` | `CMakeLists.txt` | Spec §4 mandate; boot report confirmed `clk_sys=200000000` | Long-run stress under full motor+I2C load; check for crashes/clock faults | ❓ under-load |
| A2 | I2C at **400 kHz** is within every attached device's tolerance | `hal_i2c.c` | Spec §7.3 default; BQ25887 works at it | Scan + read every planned sensor type at 400 kHz | ✅ BQ only |
| A3 | **5 ms** ADC settle after BQ25887 one-shot trigger (not 3 ms) | `hal_battery.c` `BQ_ADC_SETTLE_US` | Empirical — 3 ms returned 0s, 5 ms returned valid | Scope the ADC-ready flag / poll conversion-done bit instead of fixed delay | ❓ confirm no marginal reads |
| A4 | Battery **reads ~0.8% low** (7.12 V vs 7.18 V multimeter) is a constant offset, not drift | `hal_battery.c` | Single measurement | Track across charge cycles; calibrate constant in Phase 9 | ⚠️ monitor (action item) |
| A5 | Encoder 1 kHz FIFO drain is fast enough that the 4-deep RX FIFO never overflows at max motor speed | `hal_encoder.c` | ~1150 counts/s observed ≪ FIFO capacity at 1 kHz | Max-RPM spin; check for missed steps vs known revolutions | ❓ needs max-speed test |
| A6 | Quadrature single edge-count-per-FIFO-value resolution is acceptable (we count full steps, not 4× substep) | `pio/quadrature.pio` | Used the simpler official `quadrature_encoder` (not `_substep`) | Confirm counts/revolution = motor CPR (not ¼ of it) | ❓ needs CPR check |

## B. Architecture / Concurrency

| # | Assumption | Where | Basis / Why | Falsify By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| B1 | **Core 0 owns all I2C/UART/SPI hardware**; Core 1 will only consume lock-free caches | `hal_*`, I2C Spec §2 | Prevents bus deadlock; spec dual-core plan | Phase 1 Core 1 bring-up | ❓ |
| B2 | The single-threaded Core 0 non-blocking scheduler (button 1 kHz, battery 50 Hz, encoder 1 kHz) has enough headroom to also host the I2C governor without starving the 1 kHz tasks | `EVN_ALPHA_Performance.c` | All current services complete ≪ their period | Measure worst-case loop latency with DWT (Phase 1) | ❓ measure in Phase 1 |
| B3 | Mux **channel caching** (skip reselect on same port) is safe — no other master changes the TCA9548A behind our back | `hal_i2c.c` `s_cached_channel` | We are the only I2C master on these buses | External write to mux → stale cache → wrong port. Recovery: `hal_i2c_deselect_all()` | ✅ (sole master) |
| B4 | `hal_i2c_*` blocking calls with 5 ms timeout are acceptable on Core 0 (they never run on the RT path) | `hal_i2c.c` | Spec §4.1 default 5000 µs | Confirm no RT consumer calls them directly | ✅ by design |
| B5 | Lock-free battery cache (seq-counter + `__dmb`) is correct for cross-core reads | `hal_battery.c` | Standard seqlock pattern | Phase 1 Core 1 reads; check for torn values under contention | ❓ Phase 1 |

## C. Pin / Peripheral Mapping

| # | Assumption | Where | Basis / Why | Falsify By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C1 | PIO partition: **pio0 = encoders (SM0–3), pio1 = servos (SM0–3)** is a stable, non-conflicting split | `hal_encoder.c`, `hal_servo.c` | PLAN §6 risk mitigation; 4+4 = 8 SMs across 2 blocks | PIO instr budget audit when motion engine lands | ✅ verified working |
| C2 | **PWM Slice 5 stays with Motor 2** (GP26/27); servos never claim hardware PWM | `hal_servo.c` | Spec §9.1 conflict resolution | Confirm Motor 2 PWM unaffected while servos run (done — both verified) | ✅ |
| C3 | Encoder **base pin = lower of the A/B pair** for M2/M4 (B lower) with software sign-flip yields correct direction | `hal_encoder.c` `s_hw` | Empirical — M2 FWD gave +2365, REV −2399 | Confirm M3/M4 (the other two conventions) behave; per-motor `hal_encoder_set_sign` now exposed | ❓ M3/M4 untested |
| C4 | Default **motor direction +1** for all four is correct until per-installation override | `hal_motor.c` `s_dir` | Placeholder default | Per-motor HITL: does FWD match the physical "forward"? | ❓ per-motor confirm |
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
