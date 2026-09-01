# EVN Alpha High-Performance I2C & Real-Time Control Architecture

## 1. Executive Summary

The EVN Alpha utilizes an RP2040 MCU (Dual Cortex-M0+) driving 16 physical I2C ports distributed across two 8-channel multiplexers (`i2c0` and `i2c1`). 

This architecture guarantees:
1. **Deterministic Motor Control & Telemetry:** 1 kHz motor PID loops with real-time battery voltage compensation (Port 16) completely isolated from user code execution.
2. **Maximum I2C Throughput:** Parallel dual-bus transactions using DMA and stateful multiplexer caching.
3. **Hot-Plug Flexibility:** Support for arbitrary 7-bit I2C devices without pre-defined driver whitelists.
4. **Zero-Edit Third-Party Compatibility:** Transparent interception of standard off-the-shelf libraries (e.g., Adafruit, SparkFun, standard Arduino/MicroPython drivers) using scoped port guards and synthetic bus proxies.
5. **Robust Fault Isolation:** Hardware watchdog integration, automatic stuck-bus clearing, and strict lock timeouts to eliminate starvation and bus deadlocks.

---

## 2. System Topology & Dual-Core Task Allocation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                CORE 0                                       │
│                         (System & Control Core)                             │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Hardware Timer ISR (Priority Level 0) - Fixed 1 kHz (1 ms)            │  │
│  │  ├─ Read Cached Battery Voltage (Port 16 SRAM buffer in < 1 µs)       │  │
│  │  ├─ Compute Motor PID & Voltage Scaling                               │  │
│  │  ├─ Update PWM Hardware Registers                                     │  │
│  │  └─ Feed Hardware Watchdog Timer                                      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ I2C Bus Governor & DMA Engines (Main Thread / Background IRQ)         │  │
│  │  ├─ Worker 0 (i2c0): Drives Ports 1–8  (Mux 0 @ 0x70)                │  │
│  │  ├─ Worker 1 (i2c1): Drives Ports 9–16 (Mux 1 @ 0x70)                │  │
│  │  ├─ Port 16 Telemetry Dispatcher (50 Hz scheduled job)                │  │
│  │  └─ Dynamic Bus Error Recovery & Timeout Engine                      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Lock-Free Shared SRAM & IPC Queues
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                                CORE 1                                       │
│                         (User Application Space)                            │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ User Scripts / Robotics Control Logic / State Machines                │  │
│  ├───────────────────────────────────────────────────────────────────────┤  │
│  │ Unmodified 3rd-Party Sensor Drivers (Adafruit, SparkFun, etc.)        │  │
│  ├───────────────────────────────────────────────────────────────────────┤  │
│  │ Scoped Port Guard / Synthetic Bus Proxies (`EVNPortWire`)             │  │
│  │  └─ Packages read/write sequences ──► Pushes to Transaction Queue     │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Parallel Asynchronous Dual-DMA I2C Engine

The RP2040 features two independent hardware I2C controllers. By dividing the 16 physical ports evenly, the system can execute simultaneous hardware transfers across both sides of the board.

### 3.1 Port Mapping Table

| Physical Port | Hardware Bus | Controller | Multiplexer Address | MUX Channel Bitmask |
| :--- | :--- | :--- | :--- | :--- |
| **Port 1 – 8** | `i2c0` (GPIO 16/17) | Core 0 Worker 0 | `0x70` | `1 << (Port - 1)` |
| **Port 9 – 16** | `i2c1` (GPIO 14/15) | Core 0 Worker 1 | `0x70` | `1 << (Port - 9)` |

*Note: Port 16 is permanently mapped to `i2c1`, Channel 7 (`1 << 7`), dedicated to high-frequency battery telemetry.*

---

### 3.2 Transaction Lifecycle & Stateful Caching

```
User Transaction Submit
         │
         ▼
┌──────────────────┐
│ Priority Filter  │ ──► [ Priority 0: Port 16 Telemetry / Motor Safety ]
└────────┬─────────┘     [ Priority 1: Standard User Sensor Read/Write  ]
         │
         ▼
┌───────────────────────────────────────────────┐
│ Target Controller Dispatch (`i2c0` vs `i2c1`) │
└────────┬──────────────────────────────┬───────┘
         │                              │
         ▼ (Worker 0)                   ▼ (Worker 1)
┌─────────────────────────────┐ ┌─────────────────────────────┐
│ Check MUX 0 Cached Channel  │ │ Check MUX 1 Cached Channel  │
└────────┬────────────────────┘ └────────┬────────────────────┘
         │                               │
    Same │ Different                Same │ Different
 Channel │ Channel               Channel │ Channel
         ▼       │                       ▼       │
   (Skip MUX)    ▼                 (Skip MUX)    ▼
         │   (Write 0x70)                │   (Write 0x70)
         │       │                       │       │
         └───┬───┘                       └───┬───┘
             ▼                               ▼
  [ Launch DMA Read/Write ]       [ Launch DMA Read/Write ]
```

1. **State Caching:** The engine stores `active_channel_mux0` and `active_channel_mux1`. If consecutive calls target the same physical port, the channel select transaction (`0x70`) is skipped entirely, saving $15\text{–}30\%$ of total bus time.
2. **Direct Memory Access (DMA):** Multi-byte reads (such as 8-byte color bursts from TCS34725 or 6-byte IMU bursts) are transferred directly from the I2C RX FIFO to SRAM, firing an interrupt only upon completion.

---

## 4. 3rd-Party Library Interception Layer

To support unmodified third-party sensor libraries that perform multi-step register handshakes (e.g., write command $\rightarrow$ repeated start $\rightarrow$ read data), the system provides two non-invasive abstractions.

### 4.1 Synthetic Bus Wrapper (`EVNPortWire`)

```cpp
#include "pico/stdlib.h"
#include <Wire.h>

class EVNPortWire : public TwoWire {
private:
    uint8_t physical_port;
    uint32_t timeout_us;

public:
    EVNPortWire(uint8_t port, uint32_t timeout = 5000) 
        : physical_port(port), timeout_us(timeout) {}

    virtual void beginTransmission(uint8_t address) override {
        // Initializes transaction buffer bound to target physical port
        evn_tx_buffer_begin(this->physical_port, address);
    }

    virtual uint8_t endTransmission(bool sendStop = true) override {
        // Commits transaction bundle to Core 0 I2C queue synchronously
        return evn_tx_buffer_commit(this->physical_port, sendStop, this->timeout_us);
    }

    virtual uint8_t requestFrom(uint8_t address, uint8_t quantity, bool sendStop = true) override {
        // Enqueues read job and yields Core 1 thread until DMA completes
        return evn_queue_read_sync(this->physical_port, address, quantity, sendStop, this->timeout_us);
    }
};

// --- User Application Usage ---
// Sensor library remains 100% stock and unmodified:
EVNPortWire Port4Wire(4);
Adafruit_TCS34725 rgbSensor = Adafruit_TCS34725(TCS34725_INTEGRATIONTIME_2_4MS, TCS34725_GAIN_4X);

void setup() {
    rgbSensor.begin(TCS34725_ADDRESS, &Port4Wire);
}
```

---

### 4.2 Scoped Port Guards (Atomic Sessions with Leased Timeouts)

For libraries using standard global functions or context managers:

```cpp
// RAII Scope Guard Implementation
class EVNPortGuard {
private:
    uint8_t port;
    bool acquired;

public:
    EVNPortGuard(uint8_t target_port, uint32_t lease_timeout_ms = 15) : port(target_port) {
        // Request atomic exclusive bus lock with a hard expiration lease
        acquired = evn_i2c_acquire_lock(this->port, lease_timeout_ms);
    }

    ~EVNPortGuard() {
        if (acquired) {
            evn_i2c_release_lock(this->port);
        }
    }
};

// Usage:
void read_custom_sensor() {
    {
        EVNPortGuard session(5, 10); // Lock Port 5 for max 10ms
        unmodified_vendor_driver_read();
    } // Lock automatically released here
}
```

---

## 5. Telemetry & Real-Time Motor Compensation

Unregulated battery supply causes motor speed to drift as voltage sags under load. 

### 5.1 Lockless Double-Buffered Telemetry Cache

```c
typedef struct {
    float battery_voltage;
    uint32_t last_timestamp_us;
    uint32_t read_sequence_id;
} battery_telemetry_t;

// Atomic double-buffer in shared SRAM
static volatile battery_telemetry_t telemetry_buffers[2];
static volatile uint8_t active_telemetry_idx = 0;

// Core 0 Background Worker (Writes new sample)
void update_battery_cache(float raw_voltage) {
    uint8_t next_idx = 1 - active_telemetry_idx;
    telemetry_buffers[next_idx].battery_voltage = raw_voltage;
    telemetry_buffers[next_idx].last_timestamp_us = time_us_32();
    telemetry_buffers[next_idx].read_sequence_id++;
    
    // Atomic index switch
    active_telemetry_idx = next_idx;
}

// Core 0 1kHz PID Timer ISR (Reads instantly without bus lock)
static inline float get_battery_voltage_fast(void) {
    return telemetry_buffers[active_telemetry_idx].battery_voltage;
}
```

### 5.2 Voltage Scaling Formula (1 kHz PID Loop)

$$\text{PWM}_{\text{adjusted}} = \text{clamp}\left(\text{PWM}_{\text{target}} \times \left( \frac{V_{\text{nominal}}}{\max(V_{\text{actual}}, V_{\text{cutoff}})} \right), -100\%, +100\%\right)$$

* $V_{\text{nominal}}$: Calibrated target supply voltage (e.g., $7.4\,\text{V}$).
* $V_{\text{cutoff}}$: Low-voltage safety threshold (e.g., $6.0\,\text{V}$) to prevent division-by-zero or over-discharging.

---

## 6. Fault Tolerance, Safety & Bus Recovery Matrix

| Fault Condition | Impact | Detection Mechanism | Automated Recovery Action |
| :--- | :--- | :--- | :--- |
| **Hanging User Code** | Core 1 stuck in loop | Core 1 watchdog / Task lease | Core 0 control & PID loop continue running unaffected. |
| **Monopolized Bus Lock** | Telemetry starved | Software Lease Timer ($>15\,\text{ms}$) | Governor forcibly breaks lock, logs warning, and executes Port 16 read. |
| **Unresponsive / Missing Chip** | Bus stall | Hardware I2C Timeout (`IC_TAR` / SCL timer) | DMA aborts after $2\,\text{ms}$, returns `ERR_TIMEOUT`, drops queue job. |
| **Mid-Transfer Disconnect** | SDA held low by slave | Bus state check before start | Governor executes 9-pulse SCL clock sequence on active port to free the line. |
| **Global Interrupt Hang** | Motor runaway risk | RP2040 Hardware Watchdog ($50\,\text{ms}$) | Watchdog resets entire system safely if 1 kHz PID ISR fails to execute. |

---

## 7. C/C++ Reference API Signatures

```c
#ifndef EVN_ALPHA_I2C_H
#define EVN_ALPHA_I2C_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#define EVN_PORT_MIN   1
#define EVN_PORT_MAX   16
#define EVN_PORT_BATTERY 16

typedef enum {
    EVN_OK = 0,
    EVN_ERR_TIMEOUT,
    EVN_ERR_NACK,
    EVN_ERR_BUS_LOCKED,
    EVN_ERR_INVALID_PORT
} evn_status_t;

// Initialization
void evn_system_init(void);

// Raw Generic I2C Access (Non-blocking queue submission)
evn_status_t evn_i2c_transfer(uint8_t port, 
                              uint8_t dev_addr, 
                              const uint8_t *tx_buf, 
                              size_t tx_len, 
                              uint8_t *rx_buf, 
                              size_t rx_len, 
                              uint32_t timeout_us);

// Port Scoping / Bus Locks
bool evn_i2c_acquire_lock(uint8_t port, uint32_t lease_timeout_ms);
void evn_i2c_release_lock(uint8_t port);

// Instantaneous System Telemetry (< 1 µs read latency)
float evn_battery_get_voltage(void);

#endif // EVN_ALPHA_I2C_H
```