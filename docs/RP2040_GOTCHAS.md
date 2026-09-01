# RP2040 Gotchas — EVN ALPHA Relevant Subset

Curated from the team's exhaustive RP2040 gotcha/errata list, filtered to what
**actually bites this project** (EVN ALPHA: RP2040 @ 200 MHz, Pico SDK 2.3.0,
dual-core 1 kHz motion loop, PIO encoders/servos, USB-CDC tuning console).
Each entry notes where it applies here and our mitigation.

---

## Critical — directly hit this project

### 1. `printf`/stdio over USB CDC blocks when the FIFO is full → host wedge
`printf()`/`fwrite()` to stdio USB CDC is **blocking** and unbuffered when no
host listens; worse, when the host polls slowly, the device-side TX path backs
up and the Windows `usbser` driver can enter a state where the COM port
enumerates but **won't open** (`PermissionError 31, "A device attached to the
system is not functioning"`). We hit this repeatedly during trace dumps.

**Mitigation (now in firmware):** dump paths use a **non-blocking, FIFO-aware
writer** — `tud_cdc_write_available()` → `tud_cdc_write()` →
`tud_cdc_write_flush()`, servicing `tud_task()` while waiting, never blocking
(`cdc_write_paced()` in `EVN_ALPHA_Performance.c`). Host side uses small reads
+ short timeouts + non-blocking writes so the device RX stays polled.
**Rule: never let a bulk `printf` loop run unthrottled against a closed/slow host.**

### 2. No DWT `CYCCNT` on Cortex-M0+ (already cost us a flash cycle)
The M0+ has **no DWT cycle counter**. Don't assume it exists from the ARM
family name. Use the hardware µs timer (`time_us_64()`, 1 µs floor) for
sub-µs-adjacent measurement. (Recorded in AGENTS.md "Preflight"; kept here for
completeness.)

### 3. Blocking stdio + dual-core = deadlock / corruption risk
Standard `libc` (`printf`, `malloc`, `sprintf`) is **not thread-safe**; a
`printf` on Core 0 holding the stdio lock while a Core-1 ISR also prints
deadlocks permanently. **Rule (already enforced):** Core 1 (RT loop) never
calls `printf` — it fills lock-free ring buffers/seqlocks drained by Core 0 →
USB. All heap/I-O lives on Core 0.

### 4. Flash erase/program disables XIP → concurrent ISR must be in SRAM
During `flash_range_erase()`/`flash_range_program()` the whole XIP flash
subsystem is off; any ISR in flash crashes the MCU. **Mitigation (already
enforced):** RT paths are `__not_in_flash_func()` and use the
`multicore_lockout` pattern (Hardware Reference §6.4) — required before Phase 9
`hal_nvm` flash writes.

---

## Applies to specific subsystems here

### Clocks
- **USB needs a stable 48 MHz `clk_usb`.** We overclock `clk_sys` to 200 MHz —
  the 200 MHz profile must keep `clk_usb` at exactly 48 MHz or USB silently
  drops/corrupts. (Our console working at 200 MHz confirms the dividers are right;
  keep `PICO_USE_FASTEST_SUPPORTED_CLOCK` + verify `clk_usb` on any clock change.)
- **Only 4 hardware alarm channels**, shared by `repeating_timer`/`alarm_pool`.
  Our Core 1 1 kHz loop uses one hardware alarm; budget the rest carefully.

### PIO
- **32-instruction memory per PIO block.** Our split (pio0 = 4× quadrature,
  pio1 = 4× servo) is a deliberate budget partition (Assumption C1). Audit
  instruction count before adding PIO programs to a block.
- **PIO output needs explicit OE**: `pio_sm_set_consecutive_pindirs(..., true)`
  or `set pins` never drives the pad. (In AGENTS.md hard-won list.)
- **`pio_sm_exec()` injection** while a SM is stalled on `pull`/`push` can
  desync its PC. Avoid CPU-injected instructions on running encoder/servo SMs.

### I2C
- **I2C peripheral can lock up permanently** if a slave stretches `SCL` or drops
  mid-transaction — the silicon has **no internal timeout recovery**. Our
  `hal_i2c.c` implements the manual **9-clock SCL clear** bus-recovery routine
  (Spec §7.3). Keep it; never rely on the hardware to self-recover.

### GPIO / interrupts
- **`gpio_set_irq_enabled()` does NOT enable the NVIC line.** You must also
  `irq_set_enabled(IO_IRQ_BANK0, true)` or use
  `gpio_set_irq_enabled_with_callback()`. Relevant when wiring the user
  button / future sensor IRQs.
- **Floating digital inputs bleed current** — always set a pull-up/down on
  unused input pins (matters for low-power and for noise on encoder lines).

### Analog (battery ADC path)
- **ADC DNL erratum (RP2040-E11)**: DNL spikes near MSB transitions make the
  on-chip ADC noisy for precision work. **Not a problem for us** — battery
  telemetry is from the BQ25887 over I2C (external, accurate), not the RP2040
  ADC. Note only for any future on-chip ADC use.

### Memory
- **No unaligned 32-bit access on M0+** — casting a byte stream to a multi-byte
  struct and reading from an odd address HardFaults. Unpack wire/SPI/I2C
  payloads with `memcpy` or `__attribute__((packed, aligned(1)))`.
- **SRAM bank collision jitter**: both cores + DMA hitting the same SRAM bank
  on the same cycle adds wait-states. For the 1 kHz RT path, keep hot RT data
  and Core-0 telemetry buffers from thrashing the same bank if jitter matters.

---

## Build / process
- **`main()` returning → BOOTSEL trap** (`PICO_ENTER_USB_BOOT_ON_EXIT`): our
  `main()` never returns (infinite scheduler loop). Keep it that way.
- **`%f` in printf pulls in float-print libs** (binary bloat). We already print
  floats heavily on the console; acceptable for the tuning build, but be aware
  if Flash gets tight.

---

## Deliberately excluded (not applicable to EVN ALPHA)
- **USB Host mode errata (E5)**, **E2 deep-sleep GPIO glitch** — we run USB
  *device* (CDC) and never deep-sleep the RT board.
- **E11 ADC** in the signal path (see above — we use the BQ25887, not on-chip ADC).
- DMA self-chain deadlocks, WiFi/BTstack/lwIP notes — no such peripherals here.

See AGENTS.md "Hard-Won Gotchas" for project-specific ones (I2C probe = 1-byte
read, BQ25887 5 ms ADC settle, `i2c_get_baudrate()` doesn't exist, custom board
header breaks USB enumeration, etc.).
