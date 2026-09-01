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
| 3 | PIO quadrature encoders | PASS | 2026-09-01 | official pico-examples jump-table decoder on pio0 SM0–3, 100% offloaded, 1 kHz drain, 32-bit accum; M1 FWD +2305/REV −2157 counts, M2 (B-lower) sign-flip FWD +2365/REV −2399; per-motor `hal_encoder_set_sign` exposed |
