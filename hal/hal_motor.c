#include "hal_motor.h"

#include "pico/stdlib.h"
#include "hardware/pwm.h"
#include "hardware/gpio.h"
#include "hardware/clocks.h"
#include "hardware/structs/pwm.h"

/* --------------------------------------------------------------------------
 * Motor PWM on a 200 MHz clock. WRAP = sysclk/freq - 1 (derived at init).
 * Default 40 kHz → WRAP 4999 (~12.3-bit resolution).
 * -------------------------------------------------------------------------- */
static uint32_t s_wrap = 4999u;
static uint32_t s_freq = EVN_MOTOR_PWM_FREQ_HZ;

/* Per-motor pin pair {IN1, IN2} (ground truth — Hardware Reference §5). */
static const uint8_t s_in1[4] = { 29, 27, 23, 21 };
static const uint8_t s_in2[4] = { 28, 26, 22, 20 };

/* Per-motor drive-direction polarity (default +1). */
static int8_t s_dir[4] = { +1, +1, +1, +1 };

/* Precomputed slice number + channel for each pin, for register-level writes. */
static uint8_t s_slice[4];
/* channel of IN1 and IN2 within the slice (0=A, 1=B) */
static uint8_t s_ch1[4], s_ch2[4];
static uint8_t s_populated = 0x0;   /* bitmask of initialised motors */

static inline void pwm_write_reg(uint slice, uint channel, uint16_t level) {
    /* CC register: A in low half, B in high half. */
    uint32_t cc = pwm_hw->slice[slice].cc;
    if (channel) cc = (cc & 0x0000FFFFu) | ((uint32_t)level << 16);
    else         cc = (cc & 0xFFFF0000u) |  (uint32_t)level;
    pwm_hw->slice[slice].cc = cc;
}

static void drive_motor(uint8_t i, uint16_t lvl1, uint16_t lvl2) {
    pwm_write_reg(s_slice[i], s_ch1[i], lvl1);
    pwm_write_reg(s_slice[i], s_ch2[i], lvl2);
}

bool hal_motor_init_mask(uint8_t mask) {
    s_wrap = (clock_get_hz(clk_sys) / s_freq) - 1u;
    for (int i = 0; i < 4; i++) {
        if (!(mask & (1u << i))) continue;
        uint8_t p1 = s_in1[i], p2 = s_in2[i];
        gpio_set_function(p1, GPIO_FUNC_PWM);
        gpio_set_function(p2, GPIO_FUNC_PWM);

        uint slice = pwm_gpio_to_slice_num(p1);
        s_slice[i] = (uint8_t)slice;
        s_ch1[i] = (uint8_t)pwm_gpio_to_channel(p1);
        s_ch2[i] = (uint8_t)pwm_gpio_to_channel(p2);

        pwm_config cfg = pwm_get_default_config();
        pwm_config_set_wrap(&cfg, (uint16_t)s_wrap);
        pwm_config_set_clkdiv_int(&cfg, 1);
        pwm_init(slice, &cfg, true);

        drive_motor(i, 0, 0);   /* start coasted */
        s_populated |= (uint8_t)(1u << i);
    }
    return true;
}

bool hal_motor_init(void) {
    return hal_motor_init_mask(0xFu);
}

void hal_motor_set_pwm_freq(uint32_t freq_hz) {
    s_freq = freq_hz;
    s_wrap = (clock_get_hz(clk_sys) / s_freq) - 1u;
    for (int i = 0; i < 4; i++) {
        if (!(s_populated & (1u << i))) continue;
        pwm_set_wrap(s_slice[i], (uint16_t)s_wrap);
    }
}

void hal_motor_set(evn_motor_id_t id, float duty) {
    if (duty >  1.0f) duty =  1.0f;
    if (duty < -1.0f) duty = -1.0f;
    duty *= s_dir[id];   /* apply per-motor direction convention */

    uint16_t lvl = (uint16_t)((duty < 0 ? -duty : duty) * (float)s_wrap);

    if (duty > 0.0f)      drive_motor(id, lvl, 0);    /* forward: IN1=PWM */
    else if (duty < 0.0f) drive_motor(id, 0, lvl);    /* reverse: IN2=PWM */
    else                  drive_motor(id, 0, 0);      /* coast */
}

void hal_motor_brake(evn_motor_id_t id) {
    drive_motor(id, (uint16_t)s_wrap, (uint16_t)s_wrap);  /* both high */
}

void hal_motor_coast(evn_motor_id_t id) {
    drive_motor(id, 0, 0);                              /* both low */
}

void hal_motor_brake_all(void) { for (int i = 0; i < 4; i++) if (s_populated & (1u<<i)) hal_motor_brake((evn_motor_id_t)i); }
void hal_motor_coast_all(void) { for (int i = 0; i < 4; i++) if (s_populated & (1u<<i)) hal_motor_coast((evn_motor_id_t)i); }

uint16_t hal_motor_get_level(evn_motor_id_t id) {
    return (uint16_t)pwm_get_counter(s_slice[id]);
}

void hal_motor_set_direction(evn_motor_id_t id, int8_t dir) {
    s_dir[id] = (dir < 0) ? -1 : +1;
}
