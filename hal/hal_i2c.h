#ifndef HAL_I2C_H
#define HAL_I2C_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* ==========================================================================
 * EVN ALPHA I2C HAL — Dual TCA9548A Multiplexer Layer
 *
 * Hardware topology (Hardware Reference §7.3, I2C Spec §3.1):
 *   i2c0 (GP4/GP5) → TCA9548A #1 @ 0x70 → physical ports 1–8
 *   i2c1 (GP6/GP7) → TCA9548A #2 @ 0x70 → physical ports 9–16
 *   BQ25887 battery monitor @ 0x6A on port 16 (channel 7 of mux #2)
 *   Both buses run at 400 kHz.
 *
 * Features:
 *   - 1-based physical port selection with mux-channel state caching
 *     (consecutive transactions on the same port skip the mux select write,
 *      saving ~15–30% bus time per I2C Spec §3.2).
 *   - Blocking read/write with microsecond timeouts.
 *   - Stuck-bus recovery (9-pulse SCL clear) per I2C Spec §6.
 *   - 16-port device scanner.
 *
 * Ownership rule: ONLY Core 0 may use this module (see AGENTS.md dual-core
 * plan). Core 1 consumes sensor data via lock-free caches.
 * ========================================================================== */

#define EVN_I2C_PORT_COUNT   16
#define EVN_I2C_BAUD_HZ      400000UL
#define EVN_I2C_MUX_ADDR     0x70     /* TCA9548A, both muxes (one per bus) */
#define EVN_I2C_BQ25887_ADDR 0x6A     /* battery monitor, port 16 */
#define EVN_I2C_BATTERY_PORT 16

typedef enum {
    EVN_I2C_OK = 0,
    EVN_I2C_ERR_INVALID_PORT,   /* port outside 1..16 */
    EVN_I2C_ERR_MUX,            /* mux channel-select transaction failed */
    EVN_I2C_ERR_NACK_ADDR,      /* target device did not ACK its address */
    EVN_I2C_ERR_TIMEOUT,        /* transaction did not complete in time */
    EVN_I2C_ERR_BUS_STUCK       /* SDA or SCL held low; recovery attempted */
} evn_i2c_status_t;

/* Initialize both I2C controllers (400 kHz, GP4–GP7), deselect all mux
 * channels, and verify both TCA9548A muxes ACK at 0x70.
 * Returns EVN_I2C_OK if both muxes respond. */
evn_i2c_status_t hal_i2c_init(void);

/* Select a physical port (1–16). Maps to (bus, channel) and writes the
 * channel-select byte to the TCA9548A ONLY if that mux's cached channel
 * differs (stateful caching). */
evn_i2c_status_t hal_i2c_select_port(uint8_t port);

/* Deselect all channels on both muxes (safe idle state). */
void hal_i2c_deselect_all(void);

/* Blocking write/read on an already-selected port.
 * `nostop` = true issues a repeated-start (no STOP) for register handshakes.
 * `timeout_us` bounds the whole transaction. */
evn_i2c_status_t hal_i2c_write(uint8_t addr, const uint8_t *data, size_t len,
                               bool nostop, uint32_t timeout_us);
evn_i2c_status_t hal_i2c_read(uint8_t addr, uint8_t *data, size_t len,
                              uint32_t timeout_us);

/* Convenience: select port + write + read in one call (register read pattern).
 * Uses repeated-start between write and read phases. */
evn_i2c_status_t hal_i2c_write_read(uint8_t port, uint8_t addr,
                                    const uint8_t *tx, size_t tx_len,
                                    uint8_t *rx, size_t rx_len,
                                    uint32_t timeout_us);

/* Probe for an ACK at `addr` on an already-selected port (no data phase). */
bool hal_i2c_probe(uint8_t addr, uint32_t timeout_us);

/* Scan all 16 ports; for each port, fill `found` (indexed by 7-bit address,
 * 128 bits = 16 bytes) with ACKing addresses and return the count via the
 * array `counts[port-1]`. Total worst case ≈ 16 × 128 probes. */
void hal_i2c_scan_all(uint8_t counts[EVN_I2C_PORT_COUNT],
                      uint8_t found[EVN_I2C_PORT_COUNT][16]);

/* Attempt to free a stuck bus: 9 SCL clock pulses + STOP on both buses,
 * then re-init. Called automatically when a transaction times out with
 * SDA held low. Returns EVN_I2C_OK if lines are idle afterwards. */
evn_i2c_status_t hal_i2c_recover_bus(void);

/* Diagnostics: last error per bus, mux cache state. */
uint8_t hal_i2c_cached_channel(uint8_t bus_index); /* 0 or 1; 0xFF = none */

#endif /* HAL_I2C_H */
