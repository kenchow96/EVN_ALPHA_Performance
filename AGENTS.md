# Agent Instructions — EVN ALPHA Performance Project

Instructions for AI agents and engineers working in this repository.

## Project Purpose

Native C/C++ high-performance SDK for the **EVN ALPHA** robotics controller board (Raspberry Pi **RP2040**, Pico SDK 2.3.0, 200 MHz target clock). The library must outperform the existing EVN Arduino library on all quantitative metrics (loop frequency, jitter, CPU utilization, I2C throughput, deterministic memory).

## Authoritative Specifications

Read these first. They are the ground truth for all hardware decisions:

1. [docs/EVN ALPHA Hardware Reference.md](docs/EVN%20ALPHA%20Hardware%20Reference.md) — complete pinout, flash geometry, motion-control architecture (cascaded PID + Luenberger observer + trajectory profiler), PWM/PIO peripheral conflict analysis
2. [docs/EVN Alpha I2C Architecture Specification.md](docs/EVN%20Alpha%20I2C%20Architecture%20Specification.md) — dual TCA9548A mux topology (16 ports), dual-core I2C/DMA engine design
3. [docs/PLAN.md](docs/PLAN.md) — phased master plan, quantitative targets, efficiency protocol, Status Board. **Check the Status Board before starting any work and update it at every verified checkpoint.**
4. [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) — every unverified assumption, where it's baked in, and how to falsify it. **Confirm assumptions before building dependent phases on top; update the status column as each is closed.**

Items tagged `[GROUND TRUTH]` are non-negotiable hardware facts. Items tagged `[RECOMMENDATION / DERIVED]` are the agreed architecture — deviate only with justification.

## Repository Rules (MANDATORY)

### Performance
- **Never sleep**: No `sleep_ms()`, `sleep_us()`, or any blocking delay. Use non-blocking schedulers (`time_us_64()` elapsed-time pattern + `tight_loop_contents()`), hardware timers, or alarm callbacks.
- **Prioritize speed** at all costs. Profile before optimizing, but design for determinism up front.
- **Direct register access** (e.g., SIO) over SDK wrappers where performance is critical.
- Real-time paths (PID loop, PIO handlers, observers) must be marked `__not_in_flash_func()` and must perform **zero dynamic heap allocation**.

### Architecture
- **HAL pattern**: All hardware-specific GPIO/peripheral access lives in `hal/hal_*.c` modules; application logic must not touch hardware directly.
- **Debouncing**: Button/switch interfaces must use stable state-machine debouncers (see [hal/hal_button.c](hal/hal_button.c) for the reference implementation — 1 kHz tick, 20-sample stability threshold).
- **Dual-core plan**: Core 1 = deterministic 1 kHz real-time control loop; Core 0 = background tasks, I2C governor, stdio. Never call `flash_range_erase()`/`flash_range_program()` without the `multicore_lockout` pattern documented in the Hardware Reference §6.4.
- **Peripheral conflicts**: PWM Slice 5 is shared between Motor 2 (GP26/27) and Servos 3/4 (GP10/11). Motors keep hardware PWM at 25 kHz; servos must be PIO-driven. See Hardware Reference §9.1.
- **Efficiency**: Follow the Efficiency Protocol in [docs/PLAN.md](docs/PLAN.md) §2 — falsifying check first, batched reads, single focused validation, commit at each verified checkpoint.

## Repository Layout

```
├── EVN_ALPHA_Performance.c     # Main entry — subsystem self-tests on a non-blocking Core 0 scheduler
├── hal/                        # HAL modules (all hardware access lives here)
│   ├── hal_led.c/h             #   User LED GP25 (direct SIO)
│   ├── hal_button.c/h          #   User button GP24, state-machine debouncer
│   ├── hal_i2c.c/h             #   Dual TCA9548A mux, 16 ports, channel caching, stuck-bus recovery
│   ├── hal_battery.c/h         #   BQ25887 on port 16, lock-free cache, 50 Hz dispatcher
│   ├── hal_uart.c/h            #   Serial1 (uart0 GP0/1) + Serial2 (uart1 GP8/9), IRQ ring-buffer RX
│   ├── hal_servo.c/h           #   4ch PIO PWM on pio1, 50 Hz, µs pulses (Slice-5-safe)
│   ├── hal_motor.c/h           #   4× DRV8833, 25 kHz hardware PWM, direction setters
│   └── hal_encoder.c/h         #   4× PIO quadrature on pio0, 1 kHz drain, sign setters
├── motion/                     # Core 1 real-time control engine (planned)
├── pio/                        # quadrature.pio (pio0), servo.pio (pio1)
├── bench/                      # RESULTS.md + results/*.csv (planned cycle harness)
├── tools/                      # serial_capture.py (agent reads board serial directly)
├── docs/                       # Authoritative specs + PLAN.md (read first!)
├── build/                      # Ninja build output (do not commit)
├── CMakeLists.txt              # Pico SDK 2.3.0, PICO_BOARD=pico, 200 MHz, 16MB flash overrides
└── pico_sdk_import.cmake
```

## Reading Board Output & Deploying (single command)

Use the wrapper for any flash+verify cycle — do NOT chain flash/sleep/capture
by hand (it races USB re-enumeration and loses boot banners):

```
python tools/flash_and_capture.py --time 105 --send s --expect "TEST COMPLETE" --log bench/results/run.txt
```

It flashes the UF2, robustly waits for the COM port to appear AND be openable,
optionally sends the start char, captures output, and logs it. `--expect` is a
machine-checkable acceptance gate (nonzero exit if the substring never appears).
Use `--no-flash` to capture from an already-running board. Confirm the board is
powered on first.

## Preflight: Verify Hardware Facts Before Coding

Before using any peripheral capability, confirm it EXISTS on the RP2040 in the
SDK/datasheet — do not assume from the ARM architecture family. (Cost us a
flash cycle: the Cortex-M0+ has NO DWT `CYCCNT` cycle counter; use the hardware
µs timer `time_us_64()` for sub-µs-adjacent measurement.) One grep of the SDK
headers or a 30-second datasheet check beats a flash-and-discover loop.

## Edit Discipline: Rewrite vs Patch

If a file needs a third corrective patch in a row for the same bug, STOP and
rewrite the affected function/file cleanly from the corrected mental model.
Incremental patching of a misunderstanding compounds errors (see the hal_i2c
probe saga). Batch independent edits in one call; never edit-run-inspect the
same file more than twice without re-reading it in full.

## Hard-Won Gotchas (do not relearn)

- **I2C probe = 1-byte read**, never 0-byte write (0-byte writes don't clock the
  bus on SDK 2.3.0 @ 200 MHz → phantom ACKs on every address).
- **PIO output needs explicit OE**: `pio_sm_set_consecutive_pindirs(..., true)`
  or `set pins` never drives the pad (symptom: runs fine, no physical motion).
- **BQ25887 one-shot ADC needs ~5 ms settle** (not 3 ms) before reads.
- **`i2c_get_baudrate()` doesn't exist** — capture `i2c_init()`'s return value.
- **A from-scratch custom board header broke USB enumeration.** Stay on
  `PICO_BOARD pico` + `PICO_FLASH_SIZE_BYTES`/`PICO_FLASH_SPI_CLKDIV` overrides.
- **Flash via picotool UF2** (`picotool load -f build\X.uf2 -x`) when in BOOTSEL;
  the OpenOCD `Flash` task needs a CMSIS-DAP probe attached.

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
- **Before any flash/deploy**, explicitly ask the user to confirm the EVN board is powered on. Do not flash unprompted.
- **HITL rule**: Before any hardware-in-the-loop test requiring the user's visual or physical feedback (LED state, button press, motor movement, marker placement), explicitly prompt the user to prepare and confirm readiness before and after the test.
- The current firmware toggles the user LED (GP25) on each debounced press of the user button (GP24) — this is the canonical "board is alive" smoke test.

## Adding New Subsystems

**Standard peripherals** (EVN-validated motors with characterised observer models)
live in [motion/motor_models.c](motion/motor_models.c): EV3 Large, EV3 Medium,
NXT. The motion engine's observer and feedforward use these for guaranteed
performance. Adding a new motor = characterise it (or port its Pybricks model)
and append a row to the table.

Follow the phase order in [docs/PLAN.md](docs/PLAN.md) and the HAL naming convention (`hal/hal_<peripheral>.c/h`):

1. Measurement & Core 1 infrastructure (DWT cycle counter, 1 kHz loop skeleton)
2. DRV8833 motor PWM @ 25 kHz (WRAP = 7999 at 200 MHz)
3. PIO quadrature encoders (M1–M4) — 100% PIO-offloaded
4. I2C mux layer (TCA9548A ×2, ports 1–16, BQ25887 battery on port 16)
5. PIO-based 4-channel servo PWM
6. Core 1 motion engine (1 kHz trajectory → cascaded PID → observer)

Keep the pin table in the Hardware Reference §5 as the single source of truth — never hardcode pins outside the HAL headers.
