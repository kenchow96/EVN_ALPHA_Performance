# Benchmark & Verification Results

One row per verified phase/test. Raw captures in `bench/results/`.

| Phase | Test | Result | Verified | Notes |
| :--- | :--- | :--- | :--- | :--- |
| 0 | LED/button smoke | PASS | 2026-09-01 | LED (GP25) toggles per debounced press (GP24) |
| 4 | I2C 16-port scan | PASS | 2026-09-01 | clk_sys=200 MHz, both buses 400 kHz, muxes ACK @0x70, BQ25887 @0x6A found ONLY on port 16, empty addr NACKs (ret=-1), full scan 54 ms, mux caching active |
| 5 | BQ25887 battery telemetry | PASS | 2026-09-01 | ID verified (0x29&0x78>>3=0x05), watchdog+ADC enabled; 2×P26A 18650: pack=7.12 V, cell1=3.55 V, cell2=3.55 V; 50 Hz dispatcher, lock-free cache. **Calibration note: reads 0.8% low vs multimeter 7.18 V — action item open** |
| — | UART1↔UART2 loopback | PASS | 2026-09-01 | TX1(GP0)→RX2(GP9) crossover; PING counter echoed Serial1→Serial2, zero corruption over continuous 2 Hz run, RX IRQ ring-buffer drain |
| 6 | PIO servo 4ch | PASS (timing) | 2026-09-01 | pio1, 1 MHz SM clock (1 µs/instr), 50 Hz frame, 200–2800 µs clamp, 500–2500 µs angle range; sweep 0↔180° verified; Slice 5 left free for Motor 2. Positional/scope accuracy HITL pending |
| 2 | Motor PWM (DRV8833 ×4) | PASS | 2026-09-01 | 25 kHz, WRAP=7999 @200 MHz; FWD/REV/BRAKE/COAST all correct; 60% duty overcomes stiction; per-motor `hal_motor_set_direction` exposed |
| 3 | PIO quadrature encoders | PASS | 2026-09-01 | **substep version** (official pico-examples) on pio0 SM0–3, origin 0, 100% offloaded, 1 kHz drain; M1 FWD +2330/REV −2196 steps, fractional pos (64 substeps/step), edge-timed smooth speed (±80k substeps/s), `[stopped]` speed=0 during brake/coast; `hal_encoder_set_sign` + substep accessors exposed |
| — | Perf pass (finite motor test) | PASS | 2026-09-01 | 40 kHz PWM (WRAP 4999) + register-level CC writes; encoder idle-decimation (50 Hz when stopped); non-blocking battery ADC (no busy_wait); task-table scheduler. All 4 motors FWD/REV correct: M3 +3588/−3802, M4 +3813/−3816 steps @ ~±130k substeps/s. **No-load battery 7.257 V** (cells 3.614/3.611) |
