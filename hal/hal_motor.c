#include "hal_motor.h"

#include "pico/stdlib.h"
#include "hardware/pwm.h"
#include "hardware/gpio.h"

/* --------------------------------------------------------------------------
 * Motor PWM @ 25 kHz on a 200 MHz clock: WRAP = 200e6/25e3 - 1 = 7999.
 * -------------------------------------------------------------------------- */
#define PWM_WRAP 7999u

/* Per-motor pin pair {IN1, IN2} (ground truth — Hardware Reference §5). */
static const uint8_t s_in1[4] = { 29, 27, 23, 21 };
static const uint8_t s_in2[4] = { 28, 26, 22, 20 };

/* Per-motor drive-direction polarity (default +1). Set via
 * hal_motor_set_direction() to match motor mounting / encoder wiring. */
static int8_t s_dir[4] = { +1, +1, +1, +1 };

static inline void pwm_write_level(uint gpio, uint16_t level) {
    pwm_set_gpio_level(gpio, level);
}

static void drive_pins(uint8_t in1, uint8_t in2, uint16_t lvl1, uint16_t lvl2) {
    pwm_write_level(in1, lvl1);
    pwm_write_level(in2, lvl2);
}

bool hal_motor_init(void) {
    for (int i = 0; i < 4; i++) {
        uint8_t p1 = s_in1[i], p2 = s_in2[i];
        gpio_set_function(p1, GPIO_FUNC_PWM);
        gpio_set_function(p2, GPIO_FUNC_PWM);

        uint slice = pwm_gpio_to_slice_num(p1);
        pwm_config cfg = pwm_get_default_config();
        pwm_config_set_wrap(&cfg, PWM_WRAP);
        /* clkdiv 1 → 200 MHz / (7999+1) = 25 kHz */
        pwm_config_set_clkdiv_int(&cfg, 1);
        pwm_init(slice, &cfg, true);

        drive_pins(p1, p2, 0, 0);   /* start coasted */
    }
    return true;
}

void hal_motor_set(evn_motor_id_t id, float duty) {
    if (duty >  1.0f) duty =  1.0f;
    if (duty < -1.0f) duty = -1.0f;
    duty *= s_dir[id];   /* apply per-motor direction convention */

    uint8_t in1 = s_in1[id], in2 = s_in2[id];
    uint16_t lvl = (uint16_t)((duty < 0 ? -duty : duty) * (float)PWM_WRAP);

    if (duty > 0.0f) {
        drive_pins(in1, in2, lvl, 0);        /* forward: IN1=PWM, IN2=0 */
    } else if (duty < 0.0f) {
        drive_pins(in1, in2, 0, lvl);        /* reverse: IN1=0, IN2=PWM */
    } else {
        drive_pins(in1, in2, 0, 0);          /* coast */
    }
}

void hal_motor_brake(evn_motor_id_t id) {
    drive_pins(s_in1[id], s_in2[id], PWM_WRAP, PWM_WRAP);  /* both high */
}

void hal_motor_coast(evn_motor_id_t id) {
    drive_pins(s_in1[id], s_in2[id], 0, 0);                /* both low */
}

void hal_motor_brake_all(void) { for (int i = 0; i < 4; i++) hal_motor_brake((evn_motor_id_t)i); }
void hal_motor_coast_all(void) { for (int i = 0; i < 4; i++) hal_motor_coast((evn_motor_id_t)i); }

uint16_t hal_motor_get_level(evn_motor_id_t id) {
    return (uint16_t)pwm_get_counter(pwm_gpio_to_slice_num(s_in1[id]));
}

void hal_motor_set_direction(evn_motor_id_t id, int8_t dir) {
    s_dir[id] = (dir < 0) ? -1 : +1;
}
