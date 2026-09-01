#include "hal_battery.h"
#include "hal_i2c.h"

#include "pico/stdlib.h"
#include "hardware/sync.h"

/* --------------------------------------------------------------------------
 * BQ25887 register map (ground truth from EVN Arduino EVNAlpha.h)
 * -------------------------------------------------------------------------- */
#define BQ_ADDR              0x6A
#define BQ_PORT              16
#define BQ_ID                0x05

#define REG_CHG_CONTROL1     0x05
#define REG_ADC_CONTROL      0x15
#define REG_VBAT_ADC1        0x1D
#define REG_VCELLTOP_ADC1    0x1F
#define REG_PART_INFO        0x25
#define REG_VCELLBOT_ADC1    0x26

#define CMD_ADC_CONTROL_ENABLE 0b11110000u
#define CMD_WATCHDOG_ENABLE    0b10011101u
#define MASK_PART_INFO         0b01111000u

#define BQ_TIMEOUT_US        5000U
/* ADC conversion settle time after one-shot trigger (Arduino uses 3 ms). */
#define BQ_ADC_SETTLE_US     5000U

/* Lock-free double-buffered cache (I2C Spec §5.1). Written by Core 0 only,
 * read by any core. seq odd = write in progress. */
static volatile evn_battery_state_t s_cache;

static bool read_reg(uint8_t reg, uint8_t *buf, size_t len) {
    return hal_i2c_write_read(BQ_PORT, BQ_ADDR, &reg, 1, buf, len,
                              BQ_TIMEOUT_US) == EVN_I2C_OK;
}

static bool write_reg(uint8_t reg, uint8_t val) {
    uint8_t tx[2] = { reg, val };
    evn_i2c_status_t st = hal_i2c_select_port(BQ_PORT);
    if (st != EVN_I2C_OK) return false;
    return hal_i2c_write(BQ_ADDR, tx, 2, false, BQ_TIMEOUT_US) == EVN_I2C_OK;
}

static bool read_adc16(uint8_t reg, uint16_t *out_mv) {
    uint8_t raw[2];
    if (!read_reg(reg, raw, 2)) return false;
    *out_mv = (uint16_t)((raw[0] << 8) | raw[1]);  /* MSB first, value in mV */
    return true;
}

bool hal_battery_init(void) {
    s_cache.seq = 0;
    s_cache.present = false;

    /* Verify part ID */
    uint8_t id_reg;
    if (!read_reg(REG_PART_INFO, &id_reg, 1)) {
        return false;
    }
    if (((id_reg & MASK_PART_INFO) >> 3) != BQ_ID) {
        return false;
    }

    /* Enable watchdog (may have been disabled by older libs), then ADC. */
    write_reg(REG_CHG_CONTROL1, CMD_WATCHDOG_ENABLE);
    write_reg(REG_ADC_CONTROL, CMD_ADC_CONTROL_ENABLE);

    s_cache.present = true;
    return true;
}

bool hal_battery_service(void) {
    if (!s_cache.present) return false;

    /* Trigger one-shot ADC and let it settle. busy_wait here is acceptable on
     * Core 0 (never on the Core 1 RT path); 3 ms matches the Arduino lib. */
    write_reg(REG_ADC_CONTROL, CMD_ADC_CONTROL_ENABLE);
    busy_wait_us(BQ_ADC_SETTLE_US);

    uint16_t vbatt, vcell1, vcellbot;
    if (!read_adc16(REG_VBAT_ADC1, &vbatt))        return false;
    if (!read_adc16(REG_VCELLTOP_ADC1, &vcell1))   return false;
    if (!read_adc16(REG_VCELLBOT_ADC1, &vcellbot)) return false;

    /* Publish: seq odd (write in progress) → data → seq even (stable). */
    uint32_t s = s_cache.seq;
    s_cache.seq = s + 1;                 /* make odd */
    __dmb();                             /* ordering barrier */
    s_cache.vbatt_mv     = vbatt;
    s_cache.vcell1_mv    = vcell1;
    s_cache.vcell2_mv    = vcellbot;     /* bottom cell direct from chip */
    s_cache.timestamp_us = time_us_32();
    __dmb();
    s_cache.seq = s + 2;                 /* make even = stable */
    return true;
}

bool hal_battery_get(evn_battery_state_t *out) {
    uint32_t s0, s1;
    do {
        s0 = s_cache.seq;
        if (s0 & 1u) continue;           /* write in progress, retry */
        __dmb();
        *out = *(const evn_battery_state_t *)&s_cache;
        __dmb();
        s1 = s_cache.seq;
    } while (s0 != s1);                  /* torn read, retry */
    return s_cache.present && (s0 != 0);
}

uint16_t hal_battery_voltage_mv(void) {
    evn_battery_state_t st;
    return hal_battery_get(&st) ? st.vbatt_mv : 0;
}

uint16_t hal_battery_cell1_mv(void) {
    evn_battery_state_t st;
    return hal_battery_get(&st) ? st.vcell1_mv : 0;
}

uint16_t hal_battery_cell2_mv(void) {
    evn_battery_state_t st;
    return hal_battery_get(&st) ? st.vcell2_mv : 0;
}

float hal_battery_voltage_v(void) {
    return (float)hal_battery_voltage_mv() / 1000.0f;
}

/* Debug: raw dump of key registers for diagnosing ADC/readback issues. */
bool hal_battery_debug_regs(uint8_t *part, uint8_t *adc_ctrl,
                            uint16_t *vbat, uint16_t *vtop, uint16_t *vbot) {
    if (!s_cache.present) return false;
    bool ok = true;
    ok &= read_reg(REG_PART_INFO, part, 1);
    ok &= read_reg(REG_ADC_CONTROL, adc_ctrl, 1);
    ok &= read_adc16(REG_VBAT_ADC1, vbat);
    ok &= read_adc16(REG_VCELLTOP_ADC1, vtop);
    ok &= read_adc16(REG_VCELLBOT_ADC1, vbot);
    return ok;
}
