#ifndef HAL_BATTERY_H
#define HAL_BATTERY_H

#include <stdint.h>
#include <stdbool.h>

/* ==========================================================================
 * EVN ALPHA Battery Telemetry — TI BQ25887 (I2C port 16, addr 0x6A)
 *
 * Provides cell/pack voltage in millivolts. Reads go through the I2C mux
 * (hal_i2c) on Core 0; a lock-free double-buffered cache (I2C Spec §5.1)
 * exposes the latest sample to any consumer (incl. Core 1 control loop) in
 * < 1 µs with no I2C transaction.
 *
 * Register map (from EVN Arduino EVNAlpha.cpp — ground truth):
 *   PART_INFO   0x25  ID = (val & 0b01111000) >> 3 == 0x05
 *   CHG_CTRL1   0x05  watchdog enable = 0b10011101
 *   ADC_CONTROL 0x15  one-shot trigger = 0b11110000
 *   VBAT_ADC    0x1D  16-bit mV, MSB first (2-cell pack)
 *   VCELLTOP    0x1F  16-bit mV, MSB first (top cell)
 *   VCELLBOT    0x26  16-bit mV, MSB first (bottom cell)
 * ========================================================================== */

typedef struct {
    uint32_t seq;          /* sequence counter: incremented after each complete
                              update; odd = write in progress (lock-free read
                              protocol: read seq, read data, re-read seq, retry
                              if changed or odd) */
    uint16_t vbatt_mv;     /* total pack voltage */
    uint16_t vcell1_mv;    /* top cell */
    uint16_t vcell2_mv;    /* bottom cell (vbatt - vcell1 from BQ cellbot) */
    uint32_t timestamp_us; /* time_us_32() of last successful update */
    bool     present;      /* BQ25887 detected and ID-verified */
} evn_battery_state_t;

/* Probe port 16 for the BQ25887, verify part ID, enable watchdog + ADC.
 * Returns true if the chip is present and initialised. Call from Core 0 after
 * hal_i2c_init(). Safe to call when absent (returns false, present=false). */
bool hal_battery_init(void);

/* Core 0 dispatcher — NON-BLOCKING two-phase state machine.
 * Call at ~50 Hz. Phase 1 triggers the one-shot ADC and records a timestamp;
 * phase 2 (on a later call, once the settle time has elapsed) reads the ADC
 * registers and publishes to the cache. No busy-waiting (project rule).
 * Returns true when a fresh sample is published. */
bool hal_battery_service(void);

/* Lock-free snapshot read (< 1 µs, no I2C). Copies the latest published
 * state into *out. Returns true if a valid sample has ever been published
 * (i.e. battery present and at least one successful read). */
bool hal_battery_get(evn_battery_state_t *out);

/* Fast accessors (read the cache; < 1 µs). Return 0 if no valid sample. */
uint16_t hal_battery_voltage_mv(void);   /* total pack */
uint16_t hal_battery_cell1_mv(void);     /* top cell */
uint16_t hal_battery_cell2_mv(void);     /* bottom cell */

/* Convenience: pack voltage as float volts. */
float hal_battery_voltage_v(void);

#endif /* HAL_BATTERY_H */
