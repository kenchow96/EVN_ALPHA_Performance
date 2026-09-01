#include "hal_i2c.h"

#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "hardware/gpio.h"
#include "hardware/structs/sio.h"

/* --------------------------------------------------------------------------
 * Pin map (Hardware Reference §5 — ground truth, do not change here)
 * -------------------------------------------------------------------------- */
#define PIN_I2C0_SDA 4
#define PIN_I2C0_SCL 5
#define PIN_I2C1_SDA 6
#define PIN_I2C1_SCL 7

/* Default per-transaction timeout if caller passes 0 (5 ms per I2C Spec §4.1) */
#define DEFAULT_TIMEOUT_US 5000U

/* Mux channel-cache: 0xFF = nothing selected. One entry per bus. */
static uint8_t s_cached_channel[2] = { 0xFFu, 0xFFu };

/* Bus most recently chosen by hal_i2c_select_port(). Raw write/read/probe
 * helpers target this bus; callers pipeline per-bus so this is unambiguous
 * in single-threaded Core 0 use. */
static i2c_inst_t *s_last_bus = i2c0;

static inline i2c_inst_t *bus_for_port(uint8_t port) {
    return (port <= 8u) ? i2c0 : i2c1;
}

static inline uint8_t channel_mask_for_port(uint8_t port) {
    /* Hardware Reference §7.3: mask = 1 << ((port - 1) mod 8) */
    return (uint8_t)(1u << ((port - 1u) & 7u));
}

static inline uint8_t bus_index(i2c_inst_t *bus) {
    return (bus == i2c0) ? 0u : 1u;
}

static uint32_t clamp_timeout(uint32_t timeout_us) {
    return (timeout_us == 0u) ? DEFAULT_TIMEOUT_US : timeout_us;
}

/* Forward decl: defined below, used by hal_i2c_init/scan/debug. */
static int probe_read(i2c_inst_t *bus, uint8_t addr);

/* Achieved baud from i2c_init (return value), kept for diagnostics. */
static uint32_t s_baud[2] = { 0u, 0u };

/* Map SDK return codes (byte count or PICO_ERROR_GENERIC) to status. */
static evn_i2c_status_t map_result(int ret, size_t expected) {
    if (ret == (int)expected) return EVN_I2C_OK;
    if (ret == PICO_ERROR_TIMEOUT) return EVN_I2C_ERR_TIMEOUT;
    return EVN_I2C_ERR_NACK_ADDR;
}

evn_i2c_status_t hal_i2c_init(void) {
    /* Both controllers at 400 kHz, pins per ground-truth table. */
    s_baud[0] = i2c_init(i2c0, EVN_I2C_BAUD_HZ);
    s_baud[1] = i2c_init(i2c1, EVN_I2C_BAUD_HZ);

    gpio_set_function(PIN_I2C0_SDA, GPIO_FUNC_I2C);
    gpio_set_function(PIN_I2C0_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(PIN_I2C0_SDA);
    gpio_pull_up(PIN_I2C0_SCL);

    gpio_set_function(PIN_I2C1_SDA, GPIO_FUNC_I2C);
    gpio_set_function(PIN_I2C1_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(PIN_I2C1_SDA);
    gpio_pull_up(PIN_I2C1_SCL);

    hal_i2c_deselect_all();

    /* Verify both muxes ACK at 0x70 via 1-byte read probe. */
    int r0 = probe_read(i2c0, EVN_I2C_MUX_ADDR);
    int r1 = probe_read(i2c1, EVN_I2C_MUX_ADDR);

    if (r0 != 1 || r1 != 1) {
        return EVN_I2C_ERR_MUX;
    }
    return EVN_I2C_OK;
}

void hal_i2c_deselect_all(void) {
    uint8_t zero = 0u;
    i2c_write_timeout_us(i2c0, EVN_I2C_MUX_ADDR, &zero, 1, false, DEFAULT_TIMEOUT_US);
    i2c_write_timeout_us(i2c1, EVN_I2C_MUX_ADDR, &zero, 1, false, DEFAULT_TIMEOUT_US);
    s_cached_channel[0] = 0xFFu;
    s_cached_channel[1] = 0xFFu;
}

evn_i2c_status_t hal_i2c_select_port(uint8_t port) {
    if (port < 1u || port > EVN_I2C_PORT_COUNT) {
        return EVN_I2C_ERR_INVALID_PORT;
    }

    i2c_inst_t *bus = bus_for_port(port);
    uint8_t idx = bus_index(bus);
    uint8_t mask = channel_mask_for_port(port);
    s_last_bus = bus;

    /* Stateful caching: skip the mux write when the channel is unchanged. */
    if (s_cached_channel[idx] != mask) {
        int ret = i2c_write_timeout_us(bus, EVN_I2C_MUX_ADDR, &mask, 1,
                                       false, DEFAULT_TIMEOUT_US);
        if (ret != 1) {
            return (ret == PICO_ERROR_TIMEOUT) ? EVN_I2C_ERR_TIMEOUT
                                               : EVN_I2C_ERR_MUX;
        }
        s_cached_channel[idx] = mask;
    }
    return EVN_I2C_OK;
}

evn_i2c_status_t hal_i2c_write(uint8_t addr, const uint8_t *data, size_t len,
                               bool nostop, uint32_t timeout_us) {
    int ret = i2c_write_timeout_us(s_last_bus, addr, data, len,
                                   nostop, clamp_timeout(timeout_us));
    return map_result(ret, len);
}

evn_i2c_status_t hal_i2c_read(uint8_t addr, uint8_t *data, size_t len,
                              uint32_t timeout_us) {
    int ret = i2c_read_timeout_us(s_last_bus, addr, data, len,
                                  false, clamp_timeout(timeout_us));
    return map_result(ret, len);
}

evn_i2c_status_t hal_i2c_write_read(uint8_t port, uint8_t addr,
                                    const uint8_t *tx, size_t tx_len,
                                    uint8_t *rx, size_t rx_len,
                                    uint32_t timeout_us) {
    evn_i2c_status_t st = hal_i2c_select_port(port);
    if (st != EVN_I2C_OK) return st;

    i2c_inst_t *bus = bus_for_port(port);
    uint32_t to = clamp_timeout(timeout_us);

    int ret = i2c_write_timeout_us(bus, addr, tx, tx_len, true, to);  /* repeated start */
    if (ret != (int)tx_len) return map_result(ret, tx_len);

    ret = i2c_read_timeout_us(bus, addr, rx, rx_len, false, to);
    return map_result(ret, rx_len);
}

/* Probe helper: try a 1-byte READ of a real buffer. A present slave ACKs its
 * address phase and we clock one data byte; an absent address NACKs and the
 * SDK returns PICO_ERROR_GENERIC. Using a real (non-NULL) buffer avoids the
 * SDK's zero-length-write fast path, which appears to complete without
 * clocking the bus on this setup. */
static int probe_read(i2c_inst_t *bus, uint8_t addr) {
    uint8_t dummy = 0;
    return i2c_read_timeout_us(bus, addr, &dummy, 1, false, DEFAULT_TIMEOUT_US);
}

bool hal_i2c_probe(uint8_t addr, uint32_t timeout_us) {
    (void)timeout_us;
    return probe_read(s_last_bus, addr) == 1;
}

void hal_i2c_scan_all(uint8_t counts[EVN_I2C_PORT_COUNT],
                      uint8_t found[EVN_I2C_PORT_COUNT][16]) {
    for (uint8_t port = 1; port <= EVN_I2C_PORT_COUNT; port++) {
        uint8_t n = 0;
        uint8_t *map = found[port - 1];
        for (int i = 0; i < 16; i++) map[i] = 0;

        if (hal_i2c_select_port(port) != EVN_I2C_OK) {
            counts[port - 1] = 0;
            continue;
        }

        i2c_inst_t *bus = bus_for_port(port);
        /* Skip reserved addresses (0x00–0x07, 0x78–0x7F) and the mux itself. */
        for (uint8_t addr = 0x08; addr < 0x78; addr++) {
            if (addr == EVN_I2C_MUX_ADDR) continue;
            if (probe_read(bus, addr) == 1) {
                map[addr >> 3] |= (uint8_t)(1u << (addr & 7u));
                n++;
            }
        }
        counts[port - 1] = n;
    }
    hal_i2c_deselect_all();
}

evn_i2c_status_t hal_i2c_recover_bus(void) {
    /* I2C Spec §6: a slave holding SDA low mid-transfer is freed by clocking
     * 9 SCL pulses then issuing a STOP. Bit-bang via SIO (temporarily steal
     * the pins from the I2C function), then restore. */
    static const uint8_t sda_pin[2] = { PIN_I2C0_SDA, PIN_I2C1_SDA };
    static const uint8_t scl_pin[2] = { PIN_I2C0_SCL, PIN_I2C1_SCL };
    bool stuck_any = false;

    for (int b = 0; b < 2; b++) {
        bool sda_low = (sio_hw->gpio_in & (1u << sda_pin[b])) == 0;
        bool scl_low = (sio_hw->gpio_in & (1u << scl_pin[b])) == 0;
        if (!sda_low && !scl_low) continue;
        stuck_any = true;

        gpio_set_function(sda_pin[b], GPIO_FUNC_SIO);
        gpio_set_function(scl_pin[b], GPIO_FUNC_SIO);
        sio_hw->gpio_oe_set = (1u << sda_pin[b]) | (1u << scl_pin[b]);
        sio_hw->gpio_set = (1u << sda_pin[b]);  /* release SDA (open-drain high) */

        for (int i = 0; i < 9; i++) {
            sio_hw->gpio_clr = (1u << scl_pin[b]);
            busy_wait_us(5);
            sio_hw->gpio_set = (1u << scl_pin[b]);
            busy_wait_us(5);
        }
        /* STOP: SDA low→high while SCL high */
        sio_hw->gpio_clr = (1u << sda_pin[b]);
        busy_wait_us(5);
        sio_hw->gpio_set = (1u << sda_pin[b]);
        busy_wait_us(5);

        /* Return pins to I2C function + pull-ups */
        gpio_set_function(sda_pin[b], GPIO_FUNC_I2C);
        gpio_set_function(scl_pin[b], GPIO_FUNC_I2C);
        sio_hw->gpio_oe_clr = (1u << sda_pin[b]) | (1u << scl_pin[b]);
        gpio_pull_up(sda_pin[b]);
        gpio_pull_up(scl_pin[b]);
    }

    if (stuck_any) {
        s_cached_channel[0] = 0xFFu;
        s_cached_channel[1] = 0xFFu;
        return EVN_I2C_ERR_BUS_STUCK;
    }
    return EVN_I2C_OK;
}

uint8_t hal_i2c_cached_channel(uint8_t bus_idx) {
    if (bus_idx > 1u) return 0xFFu;
    return s_cached_channel[bus_idx];
}
