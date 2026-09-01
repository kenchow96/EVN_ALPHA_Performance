# Benchmark & Verification Results

One row per verified phase/test. Raw captures in `bench/results/`.

| Phase | Test | Result | Verified | Notes |
| :--- | :--- | :--- | :--- | :--- |
| 0 | LED/button smoke | PASS | 2026-09-01 | LED (GP25) toggles per debounced press (GP24) |
| 4 | I2C 16-port scan | PASS | 2026-09-01 | clk_sys=200 MHz, both buses 400 kHz, muxes ACK @0x70, BQ25887 @0x6A found ONLY on port 16, empty addr NACKs (ret=-1), full scan 54 ms, mux caching active |
| 5 | BQ25887 battery telemetry | PASS | 2026-09-01 | ID verified (0x29&0x78>>3=0x05), watchdog+ADC enabled; 2×P26A 18650: pack=7.109 V, cell1=3.551 V, cell2=3.539 V (12 mV balance); 50 Hz dispatcher, lock-free cache read <1 µs |
