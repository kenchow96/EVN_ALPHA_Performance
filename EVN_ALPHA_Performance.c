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

static void print_battery(void) {
    evn_battery_state_t b;
    if (hal_battery_get(&b))
        printf("Battery: %.3f V (cells %.3f / %.3f)\n",
               b.vbatt_mv/1000.0f, b.vcell1_mv/1000.0f, b.vcell2_mv/1000.0f);
}

/* test state machine shared with the command handler */
static int s_state = 3;   /* 0=OUT 1=RETURN 3=DONE (start idle) */

/* Run the full +360 -> 0 trapezoidal test on all axes. */
static void start_full_test(void) {
    for (int i = 0; i < 4; i++)
        evn_motion_move_to(i, 360.0f, 180.0f, 900.0f);
    s_state = 0;   /* OUT */
    printf(">> full test: +360 deg on all axes\n");
}

/* Move every axis by a small relative delta (for CPR validation). */
static void move_relative_all(float delta_deg) {
    for (int i = 0; i < 4; i++) {
        float ang, spd; bool stall, done;
        evn_motion_get_state(i, &ang, &spd, &stall, &done);
        evn_motion_move_to(i, ang + delta_deg, 90.0f, 450.0f);   // slow, gentle
    }
    printf(">> relative move %+.1f deg on all axes (CPR check)\n", (double)delta_deg);
}

/* Serial command loop (tuning without reflash). Commands (line-based):
 *   r            -> run full +360/0 test
 *   q            -> +90 deg relative move (CPR check)
 *   c            -> coast all (safety)
 *   g kp ki kv kd kff   -> set gains (floats)
 *   o ssl st neg ratio  -> set observer stall params (ints)
 */
static char s_cmd[96];
static int  s_cmd_len = 0;

static void handle_command(void) {
    s_cmd[s_cmd_len] = '\0';
    char *p = s_cmd;
    while (*p == ' ' || *p == '\t') p++;
    if (*p == 0) return;

    switch (p[0]) {
    case 'r': start_full_test(); break;
    case 'q': move_relative_all(90.0f); break;
    case 'Q': move_relative_all(-90.0f); break;
    case 'c': for (int i = 0; i < 4; i++) evn_motion_coast(i); hal_motor_coast_all(); printf(">> coast all\n"); break;
    case 'g': {
        float kp, ki, kv, kd, kff;
        if (sscanf(p + 1, "%f %f %f %f %f", &kp, &ki, &kv, &kd, &kff) == 5) {
            evn_motion_set_gains(kp, ki, kv, kd, kff);
            printf(">> gains kp=%g ki=%g kv=%g kd=%g kff=%g\n", (double)kp,(double)ki,(double)kv,(double)kd,(double)kff);
        } else printf("?? usage: g kp ki kv kd kff\n");
        break;
    }
    case 'o': {
        int ssl, st, neg, ratio;
        if (sscanf(p + 1, "%d %d %d %d", &ssl, &st, &neg, &ratio) == 4) {
            evn_motion_set_observer(ssl, st, neg, ratio);
            printf(">> observer ssl=%d st=%d neg=%d ratio=%d\n", ssl, st, neg, ratio);
        } else printf("?? usage: o ssl st neg ratio\n");
        break;
    }
    default: printf("?? unknown cmd '%c'\n", p[0]); break;
    }
}

static void poll_serial(void) {
    int ch;
    while ((ch = getchar_timeout_us(0)) != PICO_ERROR_TIMEOUT) {
        if (ch == '\r' || ch == '\n') {
            if (s_cmd_len > 0) { handle_command(); s_cmd_len = 0; }
        } else if (s_cmd_len < (int)sizeof(s_cmd) - 1) {
            s_cmd[s_cmd_len++] = (char)ch;
        }
    }
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

    printf("\nEVN motion console. cmds: r=run +360/0  q=+90deg  Q=-90deg  c=coast  g=set gains  o=set observer\n");

    uint64_t next_button = time_us_64();
    uint64_t next_batt = time_us_64();
    uint64_t next_report = time_us_64();

    /* test state machine: OUT (to +360) -> RETURN (to 0) -> DONE (latched).
     * Driven by the 'r' command via s_state. */
    enum { ST_OUT = 0, ST_RETURN = 1, ST_DONE = 3 };

    while (true) {
        uint64_t now = time_us_64();

        poll_serial();   // host-driven commands (run/tune/coast)

        if ((int64_t)(now - next_button) >= 0) {
            next_button = now + BUTTON_POLL_US;
            hal_button_update();
            if (hal_button_get_event()) {  // emergency coast all
                for (int i = 0; i < 4; i++) evn_motion_coast(i);
                hal_motor_coast_all();
                s_state = 3;   // DONE
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

            if (s_state == ST_OUT && all_done) {
                for (int i = 0; i < 4; i++) evn_motion_move_to(i, 0.0f, 180.0f, 900.0f);
                printf(">>> all at +360. Commanding return to 0.\n");
                s_state = ST_RETURN;
            } else if (s_state == ST_RETURN && all_done) {
                for (int i = 0; i < 4; i++) evn_motion_coast(i);   // safety: coast all
                hal_motor_coast_all();
                evn_core1_status_t cs;
                if (evn_core1_get_status(&cs)) {
                    printf("=== MOTION TEST COMPLETE (all coasted) ===\n");
                    printf("Core1: %u ticks, period %u-%u us, exec max %u us\n",
                           (unsigned)cs.tick_count, (unsigned)cs.period_min_us,
                           (unsigned)cs.period_max_us, (unsigned)cs.exec_max_us);
                }
                print_battery();
                s_state = ST_DONE;   // latched — never re-fires
            }
            /* ST_DONE: idle forever, motors coasted */
        }

        tight_loop_contents();
    }
}
