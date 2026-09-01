# EVN ALPHA Performance — Master Plan

Status of phases is kept in the [Status Board](#status-board) and updated at every verified checkpoint. This document is the single source of truth for sequencing; [AGENTS.md](../AGENTS.md) holds the mandatory working rules. Unverified assumptions are tracked in [ASSUMPTIONS.md](ASSUMPTIONS.md) — close them before building dependent phases. The Phase 7 failure analysis and repair ledger are in [AUDIT_2026-09-02.md](AUDIT_2026-09-02.md).

## 1. Mission & Quantitative Success Metrics

Native C/C++ SDK for the EVN ALPHA (RP2040, 200 MHz) that beats the EVN Arduino library on every metric. Final acceptance is a benchmark table, not a vibe.

| Metric | Target | How Measured |
| :--- | :--- | :--- |
| Control loop rate | 1000 Hz sustained | Core 1 loop period counters over ≥ 10 s |
| Loop jitter | < 1 µs target; ≤ 5 µs firmware gate | Hardware µs timer; logic analyzer for sub-µs proof |
| Encoder overhead | ~0% CPU (100% PIO) | Cycle count of 1 kHz accumulator read; logic probe optional |
| Motor PWM | 25 kHz, 8000 steps | Frequency report; optional 25/40 kHz current-ripple A/B |
| I2C throughput | Dual-bus parallel, 400 kHz, mux re-select caching | Transaction timing + bus scan benchmark |
| Telemetry cache read | < 1 µs from control loop | DWT cycle count on cached read |
| RT-path heap | 0 allocations | Link-map audit + runtime `malloc` trap |
| Stall detection | < 100 ms, sensorless | Observer torque estimate vs. physical obstruction |
| Battery telemetry | 50 Hz update, ±tolerance vs. multimeter | Comparator HITL |

All results stored as CSV in `bench/results/` with a one-line summary appended to `bench/RESULTS.md`. Never rely on rereading raw logs.

## 2. Efficiency Protocol (adapted from prior agentic HITL runs)

1. State the exact deliverable and cheapest falsifying check **before** searching or editing.
2. Batch independent reads/searches in one parallel call; read enough context once — do not reread unchanged files.
3. Make the smallest grounded edit as soon as the controlling path is known; run **one** focused validation immediately after.
4. Do not repeat a passing check unless a later edit can affect it.
5. Any deterministic workflow used twice → script or VS Code task with noninteractive execution and nonzero exit on failure.
6. Separate automated measurement from the **single** human observation a HITL test genuinely needs; batch physical asks.
7. Keep progress updates to new facts; never restate an unchanged plan.
8. Stop when acceptance criteria pass — no opportunistic refactoring.
9. **Verify hardware capability exists before coding against it** (grep SDK /
   datasheet). Example cost: RP2040 M0+ has no DWT `CYCCNT`; don't assume from
   the ARM family name.
10. **Three corrective patches on the same bug → rewrite the function cleanly**
    instead of patching again. Patching a wrong mental model compounds errors.
11. **One command for flash+verify**: always use `tools/flash_and_capture.py`
    (flash → robust port wait → optional start char → capture → log). Never
    hand-chain flash/sleep/capture — it races USB re-enumeration.
12. **Start a fresh agent session when context becomes inefficient.** First
    coast hardware, commit verified work, update the Status Board and
    `ASSUMPTIONS.md` resume point, and leave one exact continuation command.

## 3. Target Repository Structure

```
├── EVN_ALPHA_Performance.c    # Thin main entry; subsystem test modes only
├── CMakeLists.txt
├── hal/                       # Hardware Abstraction Layer (register-level)
│   ├── hal_led.c/h  hal_button.c/h            # [done]
│   ├── hal_sysclk.c/h                         # 200 MHz profile + validation
│   ├── hal_motor.c/h                          # 4× DRV8833 PWM
│   ├── hal_encoder.c/h                        # PIO quadrature front-end
│   ├── hal_i2c.c/h                            # Dual-bus + TCA9548A mux layer
│   ├── hal_battery.c/h                        # BQ25887 on port 16
│   ├── hal_servo.c/h                          # PIO servo PWM
│   └── hal_nvm.c/h                            # Flash config store (lockout pattern)
├── motion/                    # Core 1 real-time control engine
│   ├── core1.c/h                              # Launcher + 1 kHz loop skeleton
│   ├── trajectory.c/h  pid.c/h  observer.c/h
│   └── drivebase.c/h
├── pio/                       # PIO programs (quadrature.pio, servo.pio)
├── bench/                     # Cycle-count harness + machine-readable results
│   ├── bench_cycles.c/h
│   └── results/*.csv          # (+ RESULTS.md summary table)
├── tools/                     # Host-side scripts (serial capture, metrics summary)
├── docs/                      # Authoritative specs + this plan
└── AGENTS.md
```

Naming: `hal_*` = touches hardware registers; `motion/*` = pure control math + Core 1 orchestration (no direct GPIO); `bench_*` = measurement; `tools/` = host-side only.

## 4. Phase Plan

Each phase: implement → automated checks → single focused HITL confirmation (if listed) → update Status Board → **commit**. Never start a phase while its dependencies are unverified.

### Phase 0 — Foundation ✅
Deliverables: repo cleanup, `hal_led`/`hal_button`, build/deploy tasks, specs in `docs/`, AGENTS.md, git baseline.
Acceptance: LED (GP25) toggles per debounced press of button (GP24). **Verified 2026-09-01.**

### Phase 1 — Measurement & Concurrency Infrastructure
- `hal/hal_sysclk`: enforce/validate 200 MHz profile (`PICO_USE_FASTEST_SUPPORTED_CLOCK`), print clock tree on boot.
- `bench/bench_cycles`: hardware microsecond timer measurement. RP2040 Cortex-M0+ has no DWT `CYCCNT`; use a logic analyzer for sub-microsecond proof.
- `motion/core1`: Core 1 launcher; Core-1-owned hardware alarm, 1 kHz loop (`__not_in_flash_func`, zero heap); lock-free period/jitter/missed-deadline counters readable from Core 0.
- **Acceptance (automated via USB console):** `clk_sys == 200 MHz`; loop at 1000.0 Hz ±0.1% over 10 s; measured jitter ≤ 5 µs; zero missed deadlines; counters printable on demand.
- **HITL:** none.

### Phase 2 — Motor PWM (DRV8833 ×4)
- `hal/hal_motor`: PWM slices 6/5/3/2, WRAP = 7999 (25 kHz); API `hal_motor_set(id, duty ∈ [-1,1])`, `hal_motor_brake(id)`, `hal_motor_coast(id)`; duty writes via direct PWM register access.
- **Acceptance:** all four channels command forward/reverse/brake/coast; duty→speed monotonic; operation inaudible (25 kHz).
- **Carrier decision:** 25 kHz is the performance default: both options are ultrasonic, while 25 kHz provides 8,000 vs 5,000 duty levels and 37.5% fewer switching events than 40 kHz. Revisit only with an isolated current-ripple/thermal/tracking A/B.
- **HITL:** wheels off ground; user confirms spin direction per channel in one session.

### Phase 3 — PIO Quadrature Encoders (M1–M4)
- `pio/quadrature.pio` (4 SMs, transition-table decoder) + `hal/hal_encoder`: 32-bit accumulators, 1 kHz service, direction inversion for M2/M4, counts + counts/sec API.
- **Acceptance:** one marker-revolution by hand = expected CPR ±0 counts on all 4 channels; open-loop spin gives monotonic counts with correct sign; PIO offload confirmed (service routine cycle count only).
- **HITL:** user places marker, rotates each shaft exactly 1 rev (one batched session).

### Phase 4 — I2C Mux Layer (TCA9548A ×2)
- `hal/hal_i2c`: i2c0/i2c1 @ 400 kHz; port→(bus, channel) mapping per Hardware Reference §7.3; mux-select caching (skip write when port unchanged); timeout + stuck-bus recovery (9-clock SCL clear); 16-port scanner.
- **Acceptance:** full 16-port scan completes within budgeted time; BQ25887 ACKs at 0x6A on port 16; cross-port isolation (no device visible on wrong port).
- **HITL:** user plugs one known sensor into one port; scan must find exactly it.

### Phase 5 — Battery Telemetry (BQ25887)
- `hal/hal_battery`: register reads (VBAT/VBUS/IBAT/CHG status); Core 0 50 Hz dispatcher → lock-free SRAM cache; control-loop read API < 1 µs.
- **Acceptance:** VBAT within tolerance of multimeter; 50 Hz update verified by cache sequence counter; cache read latency measured and recorded.
- **HITL:** one multimeter comparison.

### Phase 6 — PIO Servo Outputs (4ch)
- `pio/servo.pio` + `hal/hal_servo`: 500–2500 µs pulses @ 50 Hz, µs-set API, all 4 channels independent. **Constraint:** no use of PWM slice 5 (reserved for Motor 2) — PIO only.
- **Acceptance:** 4 servos hold commanded positions simultaneously; Motor 2 PWM unaffected.
- **HITL:** one sweep observation.

### Phase 7 — Motion Engine (Core 1, the core deliverable)
- `motion/motor_models`: **EVN standard peripherals** — characterised motor model table (EV3 Large/Medium, NXT) ported from Pybricks pbio observer models. These are the motors we guarantee max performance for; the observer + feedforward use them.
- `motion/observer`: Luenberger state observer (θ̂ angle, ω̂ speed, current) + sensorless stall detection + feedforward torque — faithful integer port of Pybricks `observer.c`.
- `motion/trajectory`: trapezoidal profiler (S-curve optional phase 2); `motion/pid`: cascaded position/velocity PID + acceleration feedforward + friction + battery-voltage compensation (feeds from Phase 5 cache); `motion/motion_engine`: per-motor command API (`move_to`, `move_at_speed`, `stop`, hold).
- **Acceptance (all logged to `bench/results/`):** 1 kHz loop with jitter < 1 µs **under full 4-motor load**; step-response CSV (rise time, overshoot, settling); N-rev move accuracy ±counts; sensorless stall flag < 100 ms under gentle obstruction.
- **HITL:** marker rev-count validation; gentle obstruction test (one batched session).

### Phase 8 — Drive Base Kinematics
- `motion/drivebase`: differential drive straight/turn primitives, encoder heading-hold (IMU fusion via I2C is a later extension).
- **Acceptance:** fixed-distance straight run and 360° turn repeatability within recorded tolerances.
- **HITL:** floor runs with start/finish markers (batched).

### Phase 9 — Benchmarks, NVM & Hardening
- `hal/hal_nvm`: config/calibration store using `multicore_lockout` pattern (Hardware Reference §6.4); round-trip test.
- Full benchmark table (§1) populated; A/B runbook vs EVN Arduino library on identical rig (same battery/motors/surface).
- Watchdog integration, bus-fault recovery drills, heap-free audit of RT path (link map).
- **HITL:** minimal; final demo run.

## 5. Measurement Methodology

- **Cycle timing:** RP2040 hardware µs timer via `bench_cycles`; external logic analyzer when sub-µs resolution is required.
- **Telemetry discipline:** Core 1 never calls `printf`; it fills lock-free ring buffers drained by Core 0 → USB CDC CSV at decimated rates.
- **Motor-run preflight:** every automated case logs a fresh battery sample immediately before motion and aborts if age > 250 ms, pack < 6.5 V, or either cell < 3.0 V.
- **Result storage:** `bench/results/phase<N>_<test>_<YYYYMMDD>.csv` + one summary row per run appended to `bench/RESULTS.md`.
- **A/B fairness:** identical battery charge, motors, surface, and ambient conditions for Arduino-vs-native comparisons.

## 6. Risk Register & Open Questions

### Action Items (open)
- [ ] **Battery calibration**: BQ25887 reads ~0.8% low (7.12 V vs multimeter 7.18 V). Add a calibration constant (or verify against a second meter) in Phase 9 hardening. Monitor drift over charge cycles.
- [ ] **Custom board header**: `boards/evn_alpha.h` broke USB enumeration; currently using `pico` board + flash overrides. Revisit a proper board header in Phase 9 (needs correct TinyUSB/VID-PID defaults).

| Risk / Question | Impact | Mitigation |
| :--- | :--- | :--- |
| PIO instruction budget: quadrature (4 SM) + servo (4 SM) across 2 PIO blocks × 32 instr | Blocks Phases 3 & 6 | Budget table before coding; quadrature on pio0, servo on pio1; servo SM time-multiplexing fallback |
| 1 kHz budget: 4× (trajectory + PID + observer) per tick | Phase 7 timing failure | 200k cycles available; profile with DWT per stage; fixed-point math if float falls short |
| USB stdio stalls or TinyUSB re-entry | CDC corruption / jitter | SDK worker exclusively owns `tud_task()`; bounded app queue drains via mutex-protected `stdio_put_string`; host waits for framed `TRACE END` |
| Timer callback installed through default Core 0 alarm pool | USB conflict / false RT isolation | Dedicated hardware alarm claimed and installed on Core 1 |
| I2C shared across cores | Deadlock/corruption | Only Core 0 ever touches I2C hardware |
| Flash writes while Core 1 runs from XIP | Bus stall / crash | `multicore_lockout` pattern only (§6.4 of Hardware Reference) |
| M2/M4 encoder direction inversion wrong | Negative feedback | Phase 3 HITL verifies sign before any closed loop |

## 7. Status Board

| Phase | State | Verified On | Commit |
| :--- | :--- | :--- | :--- |
| 0 — Foundation | ✅ Done | 2026-09-01 | `ea1bddc` |
| 1 — Measurement & Core 1 skeleton | ✅ Done | 2026-09-01 | see commit |
| 2 — Motor PWM | ✅ Done | 2026-09-01 | `4b898f3` |
| 3 — PIO encoders | ✅ Done | 2026-09-01 | `4b898f3` |
| 4 — I2C mux | ✅ Done | 2026-09-01 | `a63422a` |
| 5 — Battery telemetry | ✅ Done | 2026-09-01 | `f556bc8` |
| 6 — PIO servos | ✅ Done | 2026-09-01 | `a16a5d3` |
| — | UART loopback (bonus) | ✅ Done | 2026-09-01 | `2f771f5` |
| 7 — Motion engine | 🟠 Audit repair HITL in progress — Core 1 timing, battery gates, 12 metrics, and autonomous flash extraction are verified. The PIO edge watchdog yields multiple 11/12 traces. Endpoint-only velocity gain is rejected above the smooth `5e-7` cruise value; 8e-6 saturated into large oscillation. Remaining best-case failure is first-breakaway acceleration, so the next sweep changes only the adaptive startup torque-ramp duration. Follow [ASSUMPTIONS.md](ASSUMPTIONS.md). **Phase 8 remains blocked** until all four motors pass the battery-gated profile suite and beat baseline. | 2026-09-02 | through `919c67a` + endpoint data |
| 8 — Drive base | ⬜ Not started — **BLOCKED by the Phase 7 smoothness gate above** | — | — |
| 9 — Benchmarks/NVM/hardening | ⬜ Not started | — | — |

## 8. Agent Session Protocol

1. Read `AGENTS.md` → this file → the Status Board row for the active phase.
2. State deliverable + falsifying check (Efficiency Protocol §2.1) before touching code.
3. Implement → one focused validation → HITL confirmation if the phase lists one → update Status Board → commit.
4. Report only new facts: changed files, validation output, HITL result, commit hash.
