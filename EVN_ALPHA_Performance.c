#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hal/hal_led.h"
#include "hal/hal_button.h"
#include "hal/hal_i2c.h"
#include "hal/hal_battery.h"
#include "hal/hal_motor.h"
#include "hal/hal_encoder.h"
#include "motion/core1.h"
#include "motion/motion_engine.h"
#include "bench/bench_cycles.h"

/* ==========================================================================
 * Phase 7 motion-engine test.
 *
 * Setup (per user):
 *   Port 1, 2 = EV3 Large (unloaded)
 *   Port 3, 4 = EV3 Medium (wheels on, off-ground)
 *
 * Test: on start-char, each motor runs a trapezoidal move +360° then back to
 * 0°, using the full pipeline (trajectory → cascaded PID+FF → observer → PWM).
 * We log commanded vs observed angle/speed each 100 ms, and flag stalls.
 * ========================================================================== */

#define BUTTON_POLL_US    1000ULL
#define BATTERY_US        20000ULL
#define REPORT_US         100000ULL   // 10 Hz status report

/* Encoder edges per output revolution (ground truth: EVN evn_motor_defs.h).
 * LEGO_PPR=180 pulses/rev of the encoder wheel; EVN counts all 4 edges → 720
 * edges/rev at the output shaft for EV3 Large/Medium and NXT. Exposed for
 * calibration via the motion engine's counts_per_rev. */
static const float CPR[4] = { 720.0f, 720.0f, 720.0f, 720.0f };

static void wait_for_start(void) {
    printf("\n*** Send any character to start the motion test ***\n");
    bool led = false;
    while (getchar_timeout_us(0) == PICO_ERROR_TIMEOUT) {
        hal_led_set(led = !led);
        busy_wait_ms(250);
    }
    hal_led_set(false);
    printf("Start received.\n");
}

static void print_battery(void) {
    evn_battery_state_t b;
    if (hal_battery_get(&b))
        printf("Battery: %.3f V (cells %.3f / %.3f)\n",
               b.vbatt_mv/1000.0f, b.vcell1_mv/1000.0f, b.vcell2_mv/1000.0f);
}

int main(void) {
    stdio_init_all();

    /* bounded console wait so the banner always lands */
    uint64_t deadline = time_us_64() + 3000000ULL;
    while (!stdio_usb_connected() && time_us_64() < deadline) tight_loop_contents();

    hal_led_init();
    hal_button_init();
    for (int i = 0; i < 3; i++) { hal_led_set(true); busy_wait_ms(80); hal_led_set(false); busy_wait_ms(80); }

    printf("hal_i2c_init: %s\n", hal_i2c_init() == EVN_I2C_OK ? "OK" : "MUX ERROR");
    printf("hal_battery_init: %s\n", hal_battery_init() ? "OK" : "NOT FOUND");

    /* standard-peripheral model table: M1,M2 = EV3 Large; M3,M4 = EV3 Medium */
    static const evn_motor_model_t *models[4];
    models[0] = evn_motor_model_get(EVN_MOTOR_MODEL_EV3_LARGE);
    models[1] = evn_motor_model_get(EVN_MOTOR_MODEL_EV3_LARGE);
    models[2] = evn_motor_model_get(EVN_MOTOR_MODEL_EV3_MEDIUM);
    models[3] = evn_motor_model_get(EVN_MOTOR_MODEL_EV3_MEDIUM);

    hal_motor_init_mask(0xF);
    hal_encoder_init_mask(0xF);
    evn_motion_init(models, CPR, 0xF);
    printf("motion_init: 4 axes (M1/M2=EV3-L, M3/M4=EV3-M)\n");

    bench_init();
    evn_core1_start();
    printf("core1: 1 kHz loop + motion engine running\n");
    print_battery();

    wait_for_start();

    /* command: +360° then back to 0°, 180 deg/s, 900 deg/s^2 */
    for (int i = 0; i < 4; i++)
        evn_motion_move_to(i, 360.0f, 180.0f, 900.0f);
    printf("Commanded +360deg on all 4 axes.\n");

    uint64_t next_button = time_us_64();
    uint64_t next_batt = time_us_64();
    uint64_t next_report = time_us_64();
    bool returned = false;

    while (true) {
        uint64_t now = time_us_64();

        if ((int64_t)(now - next_button) >= 0) {
            next_button = now + BUTTON_POLL_US;
            hal_button_update();
            if (hal_button_get_event()) {  // emergency coast all
                for (int i = 0; i < 4; i++) evn_motion_coast(i);
                printf(">> BUTTON: coast all\n");
            }
        }

        if ((int64_t)(now - next_batt) >= 0) {
            next_batt = now + BATTERY_US;
            hal_battery_service();
        }

        if ((int64_t)(now - next_report) >= 0) {
            next_report = now + REPORT_US;
            printf("---\n");
            bool all_done = true;
            for (int i = 0; i < 4; i++) {
                float ang, spd; bool stall, done;
                evn_motion_get_state(i, &ang, &spd, &stall, &done);
                float tgt, tt;
                evn_motion_get_debug(i, &tgt, &tt);
                printf("M%d: %7.1f deg  %6.1f d/s  tgt=%5.0f tt=%.2fs  %s%s\n", i+1,
                       (double)ang, (double)spd, (double)tgt, (double)tt,
                       stall ? "STALL " : "", done ? "done" : "moving");
                if (!done) all_done = false;
            }
            /* when all reached +360, command return to 0 once */
            if (all_done && !returned) {
                returned = true;
                for (int i = 0; i < 4; i++) evn_motion_move_to(i, 0.0f, 180.0f, 900.0f);
                printf("All reached +360. Commanding return to 0.\n");
            } else if (all_done && returned) {
                /* finished both legs — coast ALL motors for safety, then report */
                for (int i = 0; i < 4; i++) evn_motion_coast(i);
                hal_motor_coast_all();
                evn_core1_status_t cs;
                if (evn_core1_get_status(&cs)) {
                    printf("=== MOTION TEST COMPLETE (all coasted) ===\n");
                    printf("Core1: %u ticks, period %u-%u us, exec max %u us\n",
                           (unsigned)cs.tick_count, (unsigned)cs.period_min_us,
                           (unsigned)cs.period_max_us, (unsigned)cs.exec_max_us);
                }
                print_battery();
            }
        }

        tight_loop_contents();
    }
}
