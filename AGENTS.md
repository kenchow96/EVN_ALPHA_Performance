# Agent Instructions — EVN ALPHA Performance Project

Instructions for AI agents and engineers working in this repository.

## Project Purpose

Native C/C++ high-performance SDK for the **EVN ALPHA** robotics controller board (Raspberry Pi **RP2040**, Pico SDK 2.3.0, 200 MHz target clock). The library must outperform the existing EVN Arduino library on all quantitative metrics (loop frequency, jitter, CPU utilization, I2C throughput, deterministic memory).

## Authoritative Specifications

Read these first. They are the ground truth for all hardware decisions:

1. [docs/EVN ALPHA Hardware Reference.md](docs/EVN%20ALPHA%20Hardware%20Reference.md) — complete pinout, flash geometry, motion-control architecture (cascaded PID + Luenberger observer + trajectory profiler), PWM/PIO peripheral conflict analysis
2. [docs/EVN Alpha I2C Architecture Specification.md](docs/EVN%20Alpha%20I2C%20Architecture%20Specification.md) — dual TCA9548A mux topology (16 ports), dual-core I2C/DMA engine design

Items tagged `[GROUND TRUTH]` are non-negotiable hardware facts. Items tagged `[RECOMMENDATION / DERIVED]` are the agreed architecture — deviate only with justification.

## Repository Rules (MANDATORY)

### Performance
- **Never sleep**: No `sleep_ms()`, `sleep_us()`, or any blocking delay. Use non-blocking schedulers (`time_us_64()` elapsed-time pattern + `tight_loop_contents()`), hardware timers, or alarm callbacks.
- **Prioritize speed** at all costs. Profile before optimizing, but design for determinism up front.
- **Direct register access** (e.g., SIO) over SDK wrappers where performance is critical.
- Real-time paths (PID loop, PIO handlers, observers) must be marked `__not_in_flash_func()` and must perform **zero dynamic heap allocation**.

### Architecture
- **HAL pattern**: All hardware-specific GPIO/peripheral access lives in `hal_*.c` modules; application logic must not touch hardware directly.
- **Debouncing**: Button/switch interfaces must use stable state-machine debouncers (see [hal_button.c](hal_button.c) for the reference implementation — 1 kHz tick, 20-sample stability threshold).
- **Dual-core plan**: Core 1 = deterministic 1 kHz real-time control loop; Core 0 = background tasks, I2C governor, stdio. Never call `flash_range_erase()`/`flash_range_program()` without the `multicore_lockout` pattern documented in the Hardware Reference §6.4.
- **Peripheral conflicts**: PWM Slice 5 is shared between Motor 2 (GP26/27) and Servos 3/4 (GP10/11). Motors keep hardware PWM at 25 kHz; servos must be PIO-driven. See Hardware Reference §9.1.

## Repository Layout

```
├── EVN_ALPHA_Performance.c   # Main application entry (currently LED/button hardware test)
├── hal_led.c / hal_led.h     # User LED HAL — GP25 (EVN_LED_USER, active-high)
├── hal_button.c / hal_button.h # User button HAL — GP24 (EVN_BTN_USER, active-low, debounced)
├── docs/                     # Authoritative specs (read first!)
├── build/                    # Ninja build output (UF2/ELF artifacts; do not commit)
├── CMakeLists.txt            # Pico SDK 2.3.0 build config
└── pico_sdk_import.cmake
```

## Build & Deploy (VS Code Tasks)

Do **not** hand-run `cmake`/`ninja`. Use the preconfigured tasks via `run_task`:

| Task | Action |
| :--- | :--- |
| **Compile Project** | Incremental ninja build into `build/` |
| **Run Project** | Flash via picotool and reboot (`-fx`). Board must be in BOOTSEL or running USB-stdio firmware |
| **Flash** | Flash via OpenOCD + CMSIS-DAP debug probe |
| **Rescue Reset** | Recover a bricked/hung chip via OpenOCD |

Typical workflow: `Compile Project` → verify zero errors → `Run Project` (or `Flash` if picotool can't see the board).

## Verification & HITL Testing

- Always rebuild after code changes before deploying.
- **HITL rule**: Before any hardware-in-the-loop test requiring the user's visual or physical feedback (LED state, button press, motor movement, marker placement), explicitly prompt the user to prepare and confirm readiness before and after the test.
- The current firmware toggles the user LED (GP25) on each debounced press of the user button (GP24) — this is the canonical "board is alive" smoke test.

## Adding New Subsystems

Follow the HAL naming convention (`hal_<peripheral>.c/h`) and the spec priorities:

1. PIO quadrature encoders (M1–M4) — 100% PIO-offloaded
2. DRV8833 motor PWM @ 25 kHz (WRAP = 7999 at 200 MHz)
3. I2C mux layer (TCA9548A ×2, ports 1–16, BQ25887 battery on port 16)
4. PIO-based 4-channel servo PWM
5. Core 1 motion engine (1 kHz trajectory → cascaded PID → observer)

Keep the pin table in the Hardware Reference §5 as the single source of truth — never hardcode pins outside the HAL headers.
