# EVN ALPHA Hardware Specification & High-Performance Architecture Reference

This document is the authoritative engineering specification and software design blueprint for developing the high-performance native C/C++ SDK library for the **EVN ALPHA** robotics controller board on the Raspberry Pi **RP2040**.

---

## 1. Ground Truths vs. Architectural Recommendations

To ensure absolute clarity during automated, agentic, and human engineering workflows, all information is strictly partitioned into two categories:

* **`[GROUND TRUTH]`**: Non-negotiable hardware pinouts, electrical constraints, silicon components, and primary project mandates supplied directly by the hardware design.
* **`[RECOMMENDATION / DERIVED]`**: Control theory architectures, mathematical models, timing parameters, peripheral conflict workarounds, memory partition layouts, and software layering derived to achieve industrial-grade performance.

---

## 2. Key References & Benchmark Targets

### 2.1 Official Hardware & Reference Implementations `[GROUND TRUTH]`
* **Official Documentation:** [https://evn.readthedocs.io/latest/](https://evn.readthedocs.io/latest/)
* **Existing Arduino Library:** [https://github.com/EVNdevs/EVN-arduino](https://github.com/EVNdevs/EVN-arduino)

### 2.2 Performance Benchmark Baseline `[GROUND TRUTH]`
* **Performance Mandate:** The native C/C++ library must outperform the existing Arduino library in all quantitative metrics:
  * Control loop execution frequency & jitter ($< 1\,\mu\text{s}$ jitter).
  * Encoder throughput and interrupt handling overhead (offloaded 100% to PIO).
  * CPU utilization on Core 0 (background tasks) and Core 1 (deterministic real-time control).
  * I2C multiplexing throughput and sensor polling latency.
  * Deterministic memory footprint (zero dynamic heap allocation in the real-time control path).
* **Control Architecture Benchmark:** [Pybricks MicroPython Motor Controller](https://github.com/pybricks/pybricks-micropython). The EVN ALPHA motor and drive-base subsystems will be benchmarked against Pybricks' control scheme (cascaded PID, real-time trajectory/motion profile generation, and Luenberger state observers).

---

## 3. Target Audience & Layered Software Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        UPPER-LAYER ECOSYSTEM                           │
│  ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────┐  │
│  │    Arduino Wrapper    │ │  MicroPython Module   │ │ Scratch/Block │  │
│  │   (Beginner / Edu)    │ │   (Rapid Scripting)   │ │  (Visual IDE) │  │
│  └───────────┬───────────┘ └───────────┬───────────┘ └───────┬───────┘  │
└──────────────┼─────────────────────────┼─────────────────────┼──────────┘
               │                         │                     │
┌──────────────▼─────────────────────────▼─────────────────────▼──────────┐
│                   EVN ALPHA NATIVE C/C++ SDK ENGINE                     │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Advanced Developer C/C++ API                                      │  │
│  │ (Direct access to Motion Profiles, Observers, Raw PIO & Buffers)  │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │ Motion & Control Engine (Core 1 Dedicated 1 kHz Real-Time Task)   │  │
│  │ • Trajectory Generator (S-Curve / Trapezoidal Motion Profiler)    │  │
│  │ • Cascaded Position/Velocity PID + Feedforward Compensator       │  │
│  │ • Luenberger State Observer (Velocity & Torque Disturbance Est.)  │  │
│  │ • Differential / Omnidirectional Drive Base Kinematics            │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │ Low-Level Hardware Abstraction Layer (HAL)                        │  │
│  │ • PIO Quadrature Decoders (M1–M4)                                 │  │
│  │ • Dual TCA9548A I2C Router (16 Ports @ 400 kHz)                   │  │
│  │ • DRV8833 High-Frequency PWM Drivers (25 kHz)                     │  │
│  │ • PIO/Timer-Assisted 5V Servo Drivers                             │  │
│  │ • BQ25887 Battery Telemetry Driver                                │  │
│  │ • Non-Volatile Memory (W25Q128JV Flash / Configuration Store)     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────┐
│                  HARDWARE (Raspberry Pi RP2040)                         │
└─────────────────────────────────────────────────────────────────────────┘
```

* **Target Audience `[GROUND TRUTH]`:** The native C/C++ library is built for advanced developers, controls engineers, and industrial robotics applications.
* **Extensibility `[GROUND TRUTH]`:** The native C/C++ engine serves as the high-speed foundation for future Arduino, MicroPython, and Scratch interfaces.

---

## 4. System Clock & Performance Profile

* **`[GROUND TRUTH]` Build Configuration:** Target overclock configuration:
  ```cmake
  target_compile_definitions(${PROJECT_NAME} PRIVATE
      PICO_USE_FASTEST_SUPPORTED_CLOCK=1
  )
  ```
  Target frequency: **$200\text{ MHz}$** ($f_{\text{sys}} = 200\,000\,000\text{ Hz}$).
* **`[RECOMMENDATION / DERIVED]` Timing Parameters:**
  * System clock cycle period: $T_{\text{sys}} = 5.0\text{ ns}$.
  * Execution Determinism: Mark inner PID loops, PIO interrupt handlers, and observer calculations with `__not_in_flash_func()` to run from 0-wait-state SRAM, preventing flash cache miss stalls.

---

## 5. Complete Hardware Pinout & Peripherals `[GROUND TRUTH]`

| Subsystem | Port / Channel | Function Name | GPIO Pin | Hardware Details |
| :--- | :--- | :--- | :---: | :--- |
| **Serial Ports** | Serial 1 | `EVN_UART0_TX` | **GP0** | RP2040 `UART0 TX` |
| | Serial 1 | `EVN_UART0_RX` | **GP1** | RP2040 `UART0 RX` |
| | Serial 2 | `EVN_UART1_TX` | **GP8** | RP2040 `UART1 TX` |
| | Serial 2 | `EVN_UART1_RX` | **GP9** | RP2040 `UART1 RX` |
| **Servo Ports** | Servo 1 | `EVN_SERVO_1` | **GP2** | 5V Output (Shared 3A max rail) |
| | Servo 2 | `EVN_SERVO_2` | **GP3** | 5V Output (Shared 3A max rail) |
| | Servo 3 | `EVN_SERVO_3` | **GP10** | 5V Output (Shared 3A max rail) |
| | Servo 4 | `EVN_SERVO_4` | **GP11** | 5V Output (Shared 3A max rail) |
| **I2C Buses** | Wire (`i2c0`) | `EVN_I2C0_SDA` | **GP4** | TCA9548A MUX #1 SDA (Ports 1–8) |
| | Wire (`i2c0`) | `EVN_I2C0_SCL` | **GP5** | TCA9548A MUX #1 SCL (Ports 1–8) |
| | Wire 1 (`i2c1`) | `EVN_I2C1_SDA` | **GP6** | TCA9548A MUX #2 SDA (Ports 9–16) |
| | Wire 1 (`i2c1`) | `EVN_I2C1_SCL` | **GP7** | TCA9548A MUX #2 SCL (Ports 9–16) |
| **Motor Port 1** | Encoder A | `EVN_M1_ENC_A` | **GP18** | Quadrature Channel A (PIO) |
| | Encoder B | `EVN_M1_ENC_B` | **GP19** | Quadrature Channel B (PIO) |
| | Driver IN A | `EVN_M1_DRV_A` | **GP29** | DRV8833 IN1 (PWM Slice 6, Ch B) |
| | Driver IN B | `EVN_M1_DRV_B` | **GP28** | DRV8833 IN2 (PWM Slice 6, Ch A) |
| **Motor Port 2** | Encoder A | `EVN_M2_ENC_A` | **GP17** | Quadrature Channel A (PIO) |
| | Encoder B | `EVN_M2_ENC_B` | **GP16** | Quadrature Channel B (PIO) |
| | Driver IN A | `EVN_M2_DRV_A` | **GP27** | DRV8833 IN1 (PWM Slice 5, Ch B) |
| | Driver IN B | `EVN_M2_DRV_B` | **GP26** | DRV8833 IN2 (PWM Slice 5, Ch A) |
| **Motor Port 3** | Encoder A | `EVN_M3_ENC_A` | **GP14** | Quadrature Channel A (PIO) |
| | Encoder B | `EVN_M3_ENC_B` | **GP15** | Quadrature Channel B (PIO) |
| | Driver IN A | `EVN_M3_DRV_A` | **GP23** | DRV8833 IN1 (PWM Slice 3, Ch B) |
| | Driver IN B | `EVN_M3_DRV_B` | **GP22** | DRV8833 IN2 (PWM Slice 3, Ch A) |
| **Motor Port 4** | Encoder A | `EVN_M4_ENC_A` | **GP13** | Quadrature Channel A (PIO) |
| | Encoder B | `EVN_M4_ENC_B` | **GP12** | Quadrature Channel B (PIO) |
| | Driver IN A | `EVN_M4_DRV_A` | **GP21** | DRV8833 IN1 (PWM Slice 2, Ch B) |
| | Driver IN B | `EVN_M4_DRV_B` | **GP20** | DRV8833 IN2 (PWM Slice 2, Ch A) |
| **UI Hardware** | Pushbutton | `EVN_BTN_USER` | **GP24** | Momentary Tactile (Active-Low) |
| | User LED | `EVN_LED_USER` | **GP25** | High-Efficiency LED (Active-High) |

---

## 6. Flash Memory Specification (Winbond W25Q128JVSIQ)

### 6.1 Silicon Parameters & Geometry `[GROUND TRUTH]`
* **IC Model:** Winbond **W25Q128JVSIQ** (Industrial Grade, SOIC-8 208-mil package).
* **Total Capacity:** 16 MBytes ($16\,777\,216\text{ bytes} = 128\text{ Mbits}$).
* **Bus Type:** Quad-SPI (QSPI) connected via dedicated RP2040 QSPI interface pins.

```
       WINBOND W25Q128JV FLASH GEOMETRY (16 MB Total)
┌─────────────────────────────────────────────────────────────┐
│ 256 Blocks (64 KB each)                                     │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Block n (64 KB / 65,536 Bytes)                          │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ 16 Sectors (4 KB / 4,096 Bytes per sector)          │ │ │
│ │ │ ┌─────────────────────────────────────────────────┐ │ │ │
│ │ │ │ 16 Pages (256 Bytes per page)                   │ │ │ │
│ │ │ └─────────────────────────────────────────────────┘ │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

| Memory Parameter | Value (Bytes) | Hex Representation | Notes |
| :--- | :--- | :--- | :--- |
| **Total Size** | $16\,777\,216$ | `0x01000000` ($16\text{ MB}$) | Full addressable flash space |
| **Page Size** | $256$ | `0x00000100` ($256\text{ B}$) | Smallest programmable unit (`flash_range_program`) |
| **Sector Size** | $4\,096$ | `0x00001000` ($4\text{ KB}$) | Smallest erasable unit (`flash_range_erase`) |
| **Block Size (Half)**| $32\,768$ | `0x00008000` ($32\text{ KB}$) | Fast block erase command (`0x52`) |
| **Block Size (Full)**| $65\,536$ | `0x00010000` ($64\text{ KB}$) | Standard block erase command (`0xD8`) |

### 6.2 JEDEC & Silicon Identifiers `[RECOMMENDATION / DERIVED]`
* **Manufacturer ID:** `0xEF` (Winbond Serial Flash)
* **Memory Type ID:** `0x40`
* **Capacity ID:** `0x18` ($2^{18} = 256\text{ Mbits}$ density index $\rightarrow 128\text{ Mbit} / 16\text{ MB}$)
* **JEDEC ID Word:** `0x1840EF`

### 6.3 Memory Mapping & XIP Operations `[RECOMMENDATION / DERIVED]`
* **RP2040 Memory Map:**
  * Flash XIP Base Address: `0x10000000` (`XIP_BASE`)
  * Flash XIP End Address: `0x11000000` (`XIP_BASE + 16MB`)
* **SPI Clock Divider at $200\text{ MHz}$:**
  * The RP2040 Synchronous Serial Interface (`ssi_hw`) divides $f_{\text{sys}}$ to generate the flash SPI clock.
  * Setting the QSPI divisor to `/2` yields a **$100\text{ MHz}$ SCK**, safely within the W25Q128JV maximum rating ($133\text{ MHz}$) across the industrial temperature band ($-40^\circ\text{C}$ to $+85^\circ\text{C}$).

### 6.4 Non-Volatile Memory (NVM) Layout & Safety Protocol `[RECOMMENDATION / DERIVED]`

```
0x10000000 ┌─────────────────────────────────────────────────────────┐
           │ Firmware Image & Application Binaries                   │
           │ (Code, Constants, Vector Tables)                        │
           ├─────────────────────────────────────────────────────────┤
           │ Reserved for User File System (LittleFS / MicroPython)  │
           ├─────────────────────────────────────────────────────────┤
0x10FF0000 │ Persistent Configuration & Calibration (64 KB)          │
           │ (PID constants, motor offsets, observer gains, I2C map) │
0x11000000 └─────────────────────────────────────────────────────────┘
```

#### Dual-Core Flash Safety Rule:
Because the RP2040 executes code directly from XIP Flash, calling `flash_range_erase()` or `flash_range_program()` from Core 0 while Core 1 is actively running the $1\text{ kHz}$ motor control loop from Flash will cause an unrecoverable hardware bus stall.

**Mandatory Runtime Flash Programming Pattern:**
```c
#include "pico/multicore.h"
#include "hardware/flash.h"
#include "hardware/sync.h"

void __not_in_flash_func(evn_nvm_save_config)(uint32_t flash_offset, const uint8_t *data, size_t count) {
    // 1. Lock out Core 1 to prevent XIP execution during flash modification
    multicore_lockout_start_blocking();

    // 2. Disable local interrupts on Core 0
    uint32_t ints = save_and_disable_interrupts();

    // 3. Perform Erase & Write (must be 4KB sector aligned and 256B page aligned)
    flash_range_erase(flash_offset, FLASH_SECTOR_SIZE);
    flash_range_program(flash_offset, data, count);

    // 4. Re-enable interrupts
    restore_interrupts(ints);

    // 5. Release Core 1 back to real-time control
    multicore_lockout_end_blocking();
}
```

---

## 7. Subsystems & Peripherals

### 7.1 Motor Drivers `[GROUND TRUTH]`
* **Silicon:** 4x dedicated **TI DRV8833** Dual H-Bridge motor drivers.
* **Current Capacity:** 3.0 A RMS continuous, 4.0 A peak per port.
* **Decay & Truth Table `[RECOMMENDATION / DERIVED]`:**
  $$\text{Forward: } \text{IN1} = \text{PWM},\ \text{IN2} = 0 \quad\Big|\quad \text{Reverse: } \text{IN1} = 0,\ \text{IN2} = \text{PWM}$$
  $$\text{Active Brake: } \text{IN1} = 1,\ \text{IN2} = 1 \quad\Big|\quad \text{Coast (High-Z): } \text{IN1} = 0,\ \text{IN2} = 0$$
* **PWM Frequency Calculation ($200\text{ MHz}$ Clock) `[RECOMMENDATION / DERIVED]`:**
  To achieve ultrasonic switching at $25\text{ kHz}$ ($0\text{ dB}$ audible coil noise):
  $$\text{WRAP} = \frac{200\,000\,000}{1 \times 25\,000} - 1 = 7999$$
  Yields 8,000 discrete duty steps ($\approx 13\text{-bit}$ resolution).

---

### 7.2 Encoder Capture via PIO `[GROUND TRUTH]`
* **Requirement:** Quadrature encoder counting must be handled entirely in RP2040 PIO state machines.
* **Decoder Architecture `[RECOMMENDATION / DERIVED]`:**
  * 4 PIO State Machines running a 4-instruction transition table.
  * Invert direction sign for Motors 2 & 4 in software (`EncB` on lower pin).
  * 32-bit accumulators in software polled at $1\text{ kHz}$ via Core 1 to prevent register overflow.

---

### 7.3 16-Port I2C Multiplexing & Battery Monitor `[GROUND TRUTH]`
* **Speed:** 400 kHz Fast-Mode default.
* **Multiplexers:** 2x TI TCA9548A, both responding at 7-bit address `0x70`.
  * `Wire` (`i2c0`, GP4/GP5) $\rightarrow$ TCA9548A #1 $\rightarrow$ **Ports 1–8**
  * `Wire 1` (`i2c1`, GP6/GP7) $\rightarrow$ TCA9548A #2 $\rightarrow$ **Ports 9–16**
* **Battery IC:** TI **BQ25887** (Address `0x6A`) permanently routed on **I2C Port 16** (Channel 7 of MUX #2).
* **Multiplexer Channel Selection Formula `[RECOMMENDATION / DERIVED]`:**
  $$\text{Channel Mask} = 1 \ll ((\text{Port} - 1) \pmod 8)$$
  $$\text{Target Bus} = \begin{cases} \texttt{i2c0} & \text{if } 1 \le \text{Port} \le 8 \\ \texttt{i2c1} & \text{if } 9 \le \text{Port} \le 16 \end{cases}$$

---

### 7.4 5V Servo Outputs `[GROUND TRUTH]`
* 4 headers (GP2, GP3, GP10, GP11) powered from a shared **5V / 3.0 A** regulator.

---

## 8. Advanced Motion Control & Pybricks Benchmark Architecture `[RECOMMENDATION / DERIVED]`

To match and exceed the benchmark performance set by **Pybricks MicroPython**, the EVN ALPHA motion engine implements the following mathematical control pipeline on **Core 1** at a deterministic $1\text{ kHz}$ update rate ($T_s = 1.0\text{ ms}$).

```
                  ┌────────────────────────────────────────────────────────┐
 Target Position  │            TRAJECTORY / PROFILE GENERATOR              │
 Target Speed ───►│ Computes reference state vector:                       │
 Acceleration     │   s*(t) = [ θ*(t),  ω*(t),  α*(t) ]^T                  │
                  └───────┬──────────────────────┬─────────────────┬───────┘
                          │ θ*(t)                │ ω*(t)           │ α*(t)
                          ▼                      ▼                 ▼
                  ┌──────────────┐       ┌──────────────┐  ┌──────────────┐
                  │ Position PID │       │ Velocity PID │  │ Acceleration │
                  │  (Outer Loop)│       │ (Inner Loop) │  │ Feedforward  │
                  └───────┬──────┘       └───────┬──────┘  └───────┬──────┘
                          │                      │                 │
                          ▼                      ▼                 ▼
                  ┌────────────────────────────────────────────────────────┐
                  │                 TORQUE / VOLTAGE SUMMER                │
                  │   V(t) = K_p(θ* - θ̂) + K_v(ω* - ω̂) + K_ff α* + V_fric │
                  └───────────────────────┬────────────────────────────────┘
                                          │ V(t) (Duty Cycle)
                                          ▼
                               ┌─────────────────────┐
                               │  DRV8833 PWM Driver │
                               └──────────┬──────────┘
                                          │
                                          ▼
                                   [ DC Motor / Load ]
                                          │
                                          ▼ Raw Encoders
                  ┌────────────────────────────────────────────────────────┐
                  │               LUENBERGER STATE OBSERVER                │
                  │ Estimates:                                             │
                  │   θ̂(t) = Filtered angular position                     │
                  │   ω̂(t) = Filtered angular velocity (noise-free)        │
                  │   τ̂_L(t) = Estimated external load torque / stall      │
                  └────────────────────────────────────────────────────────┘
```

### 8.1 Trajectory Generation (S-Curve & Trapezoidal Profiling)
* Real-time generation of target position $\theta^*(t)$, angular velocity $\omega^*(t)$, and acceleration $\alpha^*(t)$.
* Finite acceleration and deceleration limits prevent wheel slip, mechanical backlash shock, and instantaneous current spikes.

### 8.2 Luenberger State Observer (State & Disturbance Estimation)
Discrete-time linear motor state observer updated every $1\text{ ms}$:

$$\begin{bmatrix} \hat{\theta}_{k+1} \\ \hat{\omega}_{k+1} \\ \hat{\tau}_{L,k+1} \end{bmatrix} = \mathbf{A}_d \begin{bmatrix} \hat{\theta}_k \\ \hat{\omega}_k \\ \hat{\tau}_{L,k} \end{bmatrix} + \mathbf{B}_d V_k + \mathbf{L} \left( y_k - \hat{\theta}_k \right)$$

* Produces jitter-free velocity estimates $\hat{\omega}_k$ even at single-tick low speeds.
* Real-time load torque estimation $\hat{\tau}_L$ enables zero-delay **sensorless stall detection** and active force feedback.

### 8.3 Cascaded Control & Feedforward Loop
$$\text{Duty}(t) = K_{\text{pos}} \left( \theta^*(t) - \hat{\theta}(t) \right) + K_{\text{vel}} \left( \omega^*(t) - \hat{\omega}(t) \right) + K_{\text{ff\_acc}} \alpha^*(t) + K_{\text{fric}} \operatorname{sgn}(\omega^*(t))$$

---

## 9. Hardware Peripherals & Conflict Analysis `[RECOMMENDATION / DERIVED]`

### 9.1 ⚠️ Hardware PWM Slice 5 Contention
* **Pin Overlap:**
  * `GP10` / `GP11` (Servo Ports 3 & 4) $\rightarrow$ RP2040 PWM Slice 5 (Channels A & B).
  * `GP26` / `GP27` (Motor 2 Drivers) $\rightarrow$ RP2040 PWM Slice 5 (Channels A & B).
* **Resolution Strategy:**
  1. **Primary Solution (Recommended):** Motor 2 uses Hardware PWM Slice 5 at $25\text{ kHz}$. Servos 1–4 are driven via a **PIO-based 4-channel PWM state machine** or a timer-driven interrupt. This allows independent, sub-microsecond pulse timing for all 4 servos while keeping all 4 motors at $25\text{ kHz}$.
  2. **Fallback:** If servos 3 & 4 are disabled, Slice 5 operates purely in high-frequency motor mode.

---

## 10. C/C++ Header Definitions Reference (`evn_alpha.h`)

```c
#pragma once

#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "hardware/pwm.h"
#include "hardware/pio.h"
#include "hardware/uart.h"
#include "hardware/gpio.h"
#include "hardware/flash.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ========================================================================== */
/* SYSTEM CLOCK CONFIGURATION (200 MHz Profile)                               */
/* ========================================================================== */
#define EVN_SYS_CLOCK_HZ             200000000UL
#define EVN_MOTOR_PWM_FREQ           25000UL
#define EVN_MOTOR_PWM_WRAP           ((EVN_SYS_CLOCK_HZ / EVN_MOTOR_PWM_FREQ) - 1) // 7999
#define EVN_CONTROL_LOOP_HZ          1000UL                                        // 1 kHz PID

/* ========================================================================== */
/* WINBOND W25Q128JV FLASH GEOMETRY                                           */
/* ========================================================================== */
#define EVN_FLASH_TOTAL_SIZE_BYTES   (16 * 1024 * 1024)                            // 16 MB
#define EVN_FLASH_PAGE_SIZE          256                                           // Page Program
#define EVN_FLASH_SECTOR_SIZE        4096                                          // Sector Erase
#define EVN_FLASH_BLOCK_SIZE         65536                                         // Block Erase
#define EVN_FLASH_CONFIG_OFFSET      (EVN_FLASH_TOTAL_SIZE_BYTES - EVN_FLASH_BLOCK_SIZE)

/* ========================================================================== */
/* UI HARDWARE (GP24, GP25)                                                   */
/* ========================================================================== */
#define EVN_PIN_BTN                  24  // Active-Low Momentary Pushbutton
#define EVN_PIN_LED                  25  // Active-High User LED

/* ========================================================================== */
/* SERVO PORTS (GP2, GP3, GP10, GP11)                                         */
/* ========================================================================== */
#define EVN_PIN_SERVO_1              2   // PWM Slice 1A
#define EVN_PIN_SERVO_2              3   // PWM Slice 1B
#define EVN_PIN_SERVO_3              10  // PWM Slice 5A (PIO PWM Recommended)
#define EVN_PIN_SERVO_4              11  // PWM Slice 5B (PIO PWM Recommended)

/* ========================================================================== */
/* MOTOR PORTS (DRV8833 & PIO Quadrature Encoders)                            */
/* ========================================================================== */
// Motor 1
#define EVN_PIN_M1_ENC_A             18
#define EVN_PIN_M1_ENC_B             19
#define EVN_PIN_M1_DRV_A             29  // PWM Slice 6B
#define EVN_PIN_M1_DRV_B             28  // PWM Slice 6A

// Motor 2
#define EVN_PIN_M2_ENC_A             17
#define EVN_PIN_M2_ENC_B             16
#define EVN_PIN_M2_DRV_A             27  // PWM Slice 5B
#define EVN_PIN_M2_DRV_B             26  // PWM Slice 5A

// Motor 3
#define EVN_PIN_M3_ENC_A             14
#define EVN_PIN_M3_ENC_B             15
#define EVN_PIN_M3_DRV_A             23  // PWM Slice 3B
#define EVN_PIN_M3_DRV_B             22  // PWM Slice 3A

// Motor 4
#define EVN_PIN_M4_ENC_A             13
#define EVN_PIN_M4_ENC_B             12
#define EVN_PIN_M4_DRV_A             21  // PWM Slice 2B
#define EVN_PIN_M4_DRV_B             20  // PWM Slice 2A

/* ========================================================================== */
/* I2C & MULTIPLEXER MAPPING                                                  */
/* ========================================================================== */
#define EVN_I2C0_SDA                 4
#define EVN_I2C0_SCL                 5
#define EVN_I2C1_SDA                 6
#define EVN_I2C1_SCL                 7

#define EVN_I2C_DEFAULT_BAUD         400000
#define EVN_TCA9548A_ADDR            0x70
#define EVN_BQ25887_ADDR             0x6A
#define EVN_BQ25887_PORT             16

/* ========================================================================== */
/* SERIAL UART PORTS                                                          */
/* ========================================================================== */
#define EVN_UART0_TX                 0
#define EVN_UART0_RX                 1
#define EVN_UART1_TX                 8
#define EVN_UART1_RX                 9
#define EVN_UART_DEFAULT_BAUD        115200

/* ========================================================================== */
/* CORE INITIALIZATION ROUTINES                                               */
/* ========================================================================== */

static inline void evn_board_init(void) {
    // 1. Initialize User LED & Button
    gpio_init(EVN_PIN_LED);
    gpio_set_dir(EVN_PIN_LED, GPIO_OUT);
    gpio_put(EVN_PIN_LED, 0);

    gpio_init(EVN_PIN_BTN);
    gpio_set_dir(EVN_PIN_BTN, GPIO_IN);
    gpio_pull_up(EVN_PIN_BTN);

    // 2. Initialize Primary I2C Bus (Wire, Ports 1-8)
    i2c_init(i2c0, EVN_I2C_DEFAULT_BAUD);
    gpio_set_function(EVN_I2C0_SDA, GPIO_FUNC_I2C);
    gpio_set_function(EVN_I2C0_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(EVN_I2C0_SDA);
    gpio_pull_up(EVN_I2C0_SCL);

    // 3. Initialize Secondary I2C Bus (Wire 1, Ports 9-16)
    i2c_init(i2c1, EVN_I2C_DEFAULT_BAUD);
    gpio_set_function(EVN_I2C1_SDA, GPIO_FUNC_I2C);
    gpio_set_function(EVN_I2C1_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(EVN_I2C1_SDA);
    gpio_pull_up(EVN_I2C1_SCL);
}

#ifdef __cplusplus
}
#endif
```