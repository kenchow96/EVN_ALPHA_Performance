#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "tusb.h"
#include "hal/hal_led.h"
#include "hal/hal_button.h"
#include "hal/hal_i2c.h"
#include "hal/hal_battery.h"
#include "hal/hal_motor.h"
#include "hal/hal_encoder.h"
#include "motion/core1.h"
#include "motion/motion_engine.h"
#include "bench/bench_cycles.h"
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

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

static void con_printf(const char *fmt, ...);

static void print_battery(void) {
    evn_battery_state_t b;
    if (hal_battery_get(&b))
        con_printf("Battery: %.3f V (cells %.3f / %.3f)\n",
                   b.vbatt_mv/1000.0f, b.vcell1_mv/1000.0f, b.vcell2_mv/1000.0f);
}

/* Core 0 is the sole tud_task() owner (the SDK background worker is disabled).
 * Producers enqueue complete records; cdc_service drains only what TinyUSB can
 * accept, so a slow or closing host cannot block the scheduler or split rows. */
#define CDC_TX_QUEUE_SIZE 8192u
#define CDC_TX_QUEUE_MASK (CDC_TX_QUEUE_SIZE - 1u)
_Static_assert((CDC_TX_QUEUE_SIZE & CDC_TX_QUEUE_MASK) == 0, "CDC queue must be a power of two");

static char s_cdc_tx[CDC_TX_QUEUE_SIZE];
static uint32_t s_cdc_tx_head = 0;
static uint32_t s_cdc_tx_tail = 0;
static bool s_cdc_was_connected = false;

static uint32_t s_dump_idx = 0;
static uint32_t s_dump_n = 0;
static int32_t  s_dump_t0 = 0;
static bool     s_dump_active = false;

static uint32_t cdc_tx_free(void) {
    return CDC_TX_QUEUE_SIZE - (s_cdc_tx_head - s_cdc_tx_tail);
}

static bool cdc_write_paced(const char *buf, size_t len) {
    if (len > cdc_tx_free()) return false;

    for (size_t i = 0; i < len; i++) {
        s_cdc_tx[s_cdc_tx_head & CDC_TX_QUEUE_MASK] = buf[i];
        s_cdc_tx_head++;
    }
    return true;
}

static bool cdc_puts(const char *s) { return cdc_write_paced(s, strlen(s)); }

static void cdc_service(void) {
    tud_task();
    bool connected = tud_cdc_connected();
    if (!connected) {
        if (s_cdc_was_connected) {
            tud_cdc_write_clear();
            s_cdc_tx_tail = s_cdc_tx_head;
            s_dump_active = false;
        }
        s_cdc_was_connected = false;
        return;
    }
    s_cdc_was_connected = true;

    uint32_t available = tud_cdc_write_available();
    while (s_cdc_tx_tail != s_cdc_tx_head && available > 0) {
        uint32_t queued = s_cdc_tx_head - s_cdc_tx_tail;
        uint32_t contiguous = CDC_TX_QUEUE_SIZE - (s_cdc_tx_tail & CDC_TX_QUEUE_MASK);
        if (contiguous > queued) contiguous = queued;
        if (contiguous > available) contiguous = available;

        uint32_t written = tud_cdc_write(&s_cdc_tx[s_cdc_tx_tail & CDC_TX_QUEUE_MASK], contiguous);
        if (written == 0) break;
        s_cdc_tx_tail += written;
        available -= written;
    }
    tud_cdc_write_flush();
}

/* Non-blocking console printf for command/status responses. Uses the FIFO-paced
 * writer so the host port can never wedge, even if the host is slow to read. */
static void con_printf(const char *fmt, ...) {
    char buf[192];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    if (n > 0) cdc_write_paced(buf, (size_t)((n < (int)sizeof buf) ? n : (int)sizeof buf - 1));
}

/* test state machine shared with the command handler */
static int s_state = 3;   /* 0=OUT 1=RETURN 3=DONE (start idle) */
static bool s_report = false;  /* 10 Hz status report (default OFF to keep USB RX responsive) */

/* Run the full +360 -> 0 trapezoidal test on all axes. */
static void start_full_test(void) {
    for (int i = 0; i < 4; i++)
        evn_motion_move_to(i, 360.0f, 180.0f, 900.0f);
    s_state = 0;   /* OUT */
    con_printf(">> full test: +360 deg on all axes\n");
}

/* Move every axis by a small relative delta (for CPR validation). */
static void move_relative_all(float delta_deg) {
    for (int i = 0; i < 4; i++) {
        float ang, spd; bool stall, done;
        evn_motion_get_state(i, &ang, &spd, &stall, &done);
        evn_motion_move_to(i, ang + delta_deg, 90.0f, 450.0f);   // slow, gentle
    }
    con_printf(">> relative move %+.1f deg on all axes (CPR check)\n", (double)delta_deg);
}

/* Relative move at tune profile (180 deg/s, 900 deg/s^2), all or one axis. */
static void move_relative_tune(float delta_deg, int only_axis /* -1 = all */) {
    for (int i = 0; i < 4; i++) {
        if (only_axis >= 0 && i != only_axis) continue;
        float ang, spd; bool stall, done;
        evn_motion_get_state(i, &ang, &spd, &stall, &done);
        evn_motion_move_to(i, ang + delta_deg, 180.0f, 900.0f);
    }
    con_printf(">> tune move %+.1f deg %s\n", (double)delta_deg,
           only_axis >= 0 ? "(single axis)" : "(all axes)");
}

/* Dump the armed axis' 1 kHz trace as CSV (host parses TRACE BEGIN/END). */
static void dump_trace(void) {
    if (s_dump_active) {
        con_printf("?? trace dump already active\n");
        return;
    }
    evn_motion_trace_stop();
    uint8_t ax; uint32_t n; bool armed;
    evn_motion_trace_info(&ax, &n, &armed);
    const evn_pid_t *p = evn_motion_axis_pid(ax);
    float max_vel, max_accel;
    evn_motion_get_profile(ax, &max_vel, &max_accel);
    static const char columns[] =
        "t_ms,ref_mdeg,enc_mdeg,hat_mdeg,vref_mdegs,what_mdegs,duty_milli,cur_01ma\n";
    char header[192];
    int length = snprintf(header, sizeof header,
        "TRACE BEGIN axis=%u rows=%lu kp=%g ki=%g kv=%g kd=%g kff=%g ff=%d pwm=%lu vmax=%g accel=%g\n",
        ax + 1, (unsigned long)n,
        (double)p->kp_pos, (double)p->ki_pos, (double)p->kp_vel,
        (double)p->kd_vel, (double)p->kff_accel,
        evn_motion_feedforward_on() ? 1 : 0,
        (unsigned long)hal_motor_get_pwm_freq(),
        (double)max_vel, (double)max_accel);
    if (length <= 0) return;
    size_t header_len = (size_t)((length < (int)sizeof header) ? length : (int)sizeof header - 1);
    if (header_len + sizeof columns - 1 > cdc_tx_free()) {
        con_printf("?? USB TX busy; retry dump\n");
        return;
    }
    cdc_write_paced(header, header_len);
    cdc_write_paced(columns, sizeof columns - 1);
    s_dump_idx = 0; s_dump_n = n; s_dump_t0 = 0; s_dump_active = true;
}

/* Called every main-loop iteration; emits up to a few rows then returns so the
 * SDK USB task runs. */
static void dump_service(void) {
    if (!s_dump_active) return;
    for (int k = 0; k < 4 && s_dump_idx < s_dump_n; k++) {
        int32_t t, ref, enc, hat, vref, what, duty, cur;
        if (!evn_motion_trace_row(s_dump_idx, &t, &ref, &enc, &hat, &vref, &what, &duty, &cur)) { s_dump_idx = s_dump_n; break; }
        if (s_dump_idx == 0) s_dump_t0 = t;
        char line[96];
        int L = snprintf(line, sizeof line, "%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld\n",
               (long)(t - s_dump_t0), (long)ref, (long)enc, (long)hat,
               (long)vref, (long)what, (long)duty, (long)cur);
        if (L <= 0) { s_dump_idx = s_dump_n; break; }
        size_t line_len = (size_t)((L < (int)sizeof line) ? L : (int)sizeof line - 1);
        if (!cdc_write_paced(line, line_len)) break;
        s_dump_idx++;
    }
    if (s_dump_idx >= s_dump_n && cdc_puts("TRACE END\n")) s_dump_active = false;
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
    case 'c': for (int i = 0; i < 4; i++) evn_motion_coast(i); hal_motor_coast_all(); con_printf(">> coast all\n"); break;
    case 'm': {
        float d;
        if (sscanf(p + 1, "%f", &d) == 1) move_relative_tune(d, -1);
        else con_printf("?? usage: m degs\n");
        break;
    }
    case 'X': {
        int ax; float delta, max_vel, max_accel;
        if (sscanf(p + 1, "%d %f %f %f", &ax, &delta, &max_vel, &max_accel) == 4 &&
            ax >= 1 && ax <= 4 && max_vel > 0.0f && max_accel > 0.0f) {
            float angle, speed; bool stall, done;
            evn_motion_get_state((uint8_t)(ax - 1), &angle, &speed, &stall, &done);
            evn_motion_move_to_test((uint8_t)(ax - 1), angle + delta,
                                    max_vel, max_accel, 4000);
            con_printf(">> profile M%d delta=%+.1f vmax=%.1f accel=%.1f\n",
                       ax, (double)delta, (double)max_vel, (double)max_accel);
        } else con_printf("?? usage: X motor delta_deg max_vel max_accel\n");
        break;
    }
    case 'M': {
        int ax; float d;
        if (sscanf(p + 1, "%d %f", &ax, &d) == 2 && ax >= 1 && ax <= 4) move_relative_tune(d, ax - 1);
        else con_printf("?? usage: M motor degs\n");
        break;
    }
    case 't': {
        int ax;
        if (sscanf(p + 1, "%d", &ax) == 1 && ax >= 1 && ax <= 4) {
            evn_motion_trace_arm((uint8_t)(ax - 1));
            con_printf(">> trace armed on M%d (%u rows max)\n", ax, EVN_TRACE_MAX);
        } else con_printf("?? usage: t motor\n");
        break;
    }
    case 'd': dump_trace(); break;
    case 'p': s_report = !s_report; con_printf(">> 10Hz report %s\n", s_report ? "ON" : "OFF"); break;
    case 'b': {
        int ax; float start_duty, hold_duty;
        if (sscanf(p + 1, "%d %f %f", &ax, &start_duty, &hold_duty) == 3 &&
            ax >= 1 && ax <= 4 && start_duty >= 0.0f && start_duty <= 1.0f &&
            hold_duty >= 0.0f && hold_duty <= 1.0f) {
            evn_motion_set_stiction((uint8_t)(ax - 1), start_duty, hold_duty);
            con_printf(">> M%d stiction start=%.3f hold=%.3f\n", ax,
                       (double)start_duty, (double)hold_duty);
        } else con_printf("?? usage: b motor start_duty hold_duty\n");
        break;
    }
    case 'w': {
        unsigned long hz;
        if (sscanf(p + 1, "%lu", &hz) == 1 && (hz == 25000UL || hz == 40000UL)) {
            for (int i = 0; i < 4; i++) evn_motion_coast(i);
            hal_motor_coast_all();
            hal_motor_set_pwm_freq((uint32_t)hz);
            con_printf(">> motor PWM %lu Hz\n", hz);
        } else con_printf("?? usage: w 25000|40000\n");
        break;
    }
    case 'S': {
        for (int i = 0; i < 4; i++) {
            float ang, spd; bool stall, done;
            evn_motion_get_state(i, &ang, &spd, &stall, &done);
            float tgt, tt;
            evn_motion_get_debug(i, &tgt, &tt);
            con_printf("M%d: %7.1f deg  %6.1f d/s  tgt=%5.0f  %s%s\n", i+1,
                   (double)ang, (double)spd, (double)tgt,
                   stall ? "STALL " : "", done ? "done" : "moving");
        }
        evn_core1_status_t cs;
        if (evn_core1_get_status(&cs)) {
            con_printf("Core1: %u ticks, period %u-%u us, exec max %u us, missed %u\n",
                       (unsigned)cs.tick_count, (unsigned)cs.period_min_us,
                       (unsigned)cs.period_max_us, (unsigned)cs.exec_max_us,
                       (unsigned)cs.missed_tick_count);
        }
        break;
    }
    case 'f': {
        int on;
        if (sscanf(p + 1, "%d", &on) == 1) {
            evn_motion_set_feedforward(on != 0);
            con_printf(">> model feedforward %s\n", on ? "ON" : "OFF");
        } else con_printf("?? usage: f 0|1\n");
        break;
    }
    case 'g': {
        float kp, ki, kv, kd, kff;
        if (sscanf(p + 1, "%f %f %f %f %f", &kp, &ki, &kv, &kd, &kff) == 5) {
            evn_motion_set_gains(kp, ki, kv, kd, kff);
            con_printf(">> gains (all) kp=%g ki=%g kv=%g kd=%g kff=%g\n", (double)kp,(double)ki,(double)kv,(double)kd,(double)kff);
        } else con_printf("?? usage: g kp ki kv kd kff\n");
        break;
    }
    case 'G': {
        int ax; float kp, ki, kv, kd, kff;
        if (sscanf(p + 1, "%d %f %f %f %f %f", &ax, &kp, &ki, &kv, &kd, &kff) == 6 && ax >= 1 && ax <= 4) {
            evn_motion_set_gains_axis((uint8_t)(ax - 1), kp, ki, kv, kd, kff);
            con_printf(">> gains M%d kp=%g ki=%g kv=%g kd=%g kff=%g\n", ax, (double)kp,(double)ki,(double)kv,(double)kd,(double)kff);
        } else con_printf("?? usage: G motor kp ki kv kd kff\n");
        break;
    }
    case 'o': {
        int ssl, st, neg, ratio;
        if (sscanf(p + 1, "%d %d %d %d", &ssl, &st, &neg, &ratio) == 4) {
            evn_motion_set_observer(ssl, st, neg, ratio);
            con_printf(">> observer ssl=%d st=%d neg=%d ratio=%d\n", ssl, st, neg, ratio);
        } else con_printf("?? usage: o ssl st neg ratio\n");
        break;
    }
    case 'v': {
        float kv, kd;
        if (sscanf(p + 1, "%f %f", &kv, &kd) == 2) {
            for (int i = 0; i < 4; i++) {
                const evn_pid_t *cur = evn_motion_axis_pid(i);
                evn_motion_set_gains_axis(i, cur->kp_pos, cur->ki_pos, kv, kd, cur->kff_accel);
            }
            con_printf(">> velocity gains (all) kv=%g kd=%g\n", (double)kv, (double)kd);
        } else con_printf("?? usage: v kv kd\n");
        break;
    }
    case 'u': {
        int on;
        if (sscanf(p + 1, "%d", &on) == 1) {
            for (int i = 0; i < 4; i++) {
                const evn_pid_t *cur = evn_motion_axis_pid(i);
                evn_pid_t *pw = (evn_pid_t *)cur;
                pw->use_enc_speed = on ? 1 : 0;
            }
            con_printf(">> velocity source = %s\n", on ? "encoder" : "observer");
        } else con_printf("?? usage: u 0|1\n");
        break;
    }
    case 's': {  /* s <motor 1-4> <enc_sign +/-1> <motor_dir +/-1> */
        int m, es, md;
        if (sscanf(p + 1, "%d %d %d", &m, &es, &md) == 3 && m >= 1 && m <= 4) {
            hal_encoder_set_sign((evn_encoder_id_t)(m - 1), (int8_t)es);
            hal_motor_set_direction((evn_motor_id_t)(m - 1), (int8_t)md);
            con_printf(">> motor %d enc_sign=%d motor_dir=%d\n", m, es, md);
        } else con_printf("?? usage: s motor enc_sign motor_dir\n");
        break;
    }
    default: con_printf("?? unknown cmd '%c'\n", p[0]); break;
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
    while (!stdio_usb_connected() && time_us_64() < deadline) {
        tud_task();
        tight_loop_contents();
    }

    hal_led_init();
    hal_button_init();
    for (int i = 0; i < 3; i++) { hal_led_set(true); busy_wait_ms(80); hal_led_set(false); busy_wait_ms(80); }

    con_printf("hal_i2c_init: %s\n", hal_i2c_init() == EVN_I2C_OK ? "OK" : "MUX ERROR");
    con_printf("hal_battery_init: %s\n", hal_battery_init() ? "OK" : "NOT FOUND");

    /* standard-peripheral model table: M1,M2 = EV3 Large; M3,M4 = EV3 Medium */
    static const evn_motor_model_t *models[4];
    models[0] = evn_motor_model_get(EVN_MOTOR_MODEL_EV3_LARGE);
    models[1] = evn_motor_model_get(EVN_MOTOR_MODEL_EV3_LARGE);
    models[2] = evn_motor_model_get(EVN_MOTOR_MODEL_EV3_MEDIUM);
    models[3] = evn_motor_model_get(EVN_MOTOR_MODEL_EV3_MEDIUM);

    hal_motor_init_mask(0xF);
    hal_encoder_init_mask(0xF);
    evn_motion_init(models, CPR, 0xF);
    con_printf("motion_init: 4 axes (M1/M2=EV3-L, M3/M4=EV3-M)\n");

    bench_init();
    evn_core1_start();
    con_printf("core1: 1 kHz loop + motion engine running\n");
    print_battery();

    con_printf("\nEVN motion console. cmds: r=+360/0  q/Q=+-90  m/M=relative  X=profile  c=coast  g/G=gains  o=obs  f=ff  w=pwm  t/d=trace\n");

    uint64_t next_button = time_us_64();
    uint64_t next_batt = time_us_64();
    uint64_t next_report = time_us_64();

    /* test state machine: OUT (to +360) -> RETURN (to 0) -> DONE (latched).
     * Driven by the 'r' command via s_state. */
    enum { ST_OUT = 0, ST_RETURN = 1, ST_DONE = 3 };

    while (true) {
        uint64_t now = time_us_64();

        cdc_service();
        poll_serial();   // host-driven commands (run/tune/coast)

        dump_service();  // non-blocking trace dump (streams a few rows per loop)

        if ((int64_t)(now - next_button) >= 0) {
            next_button = now + BUTTON_POLL_US;
            hal_button_update();
            if (hal_button_get_event()) {  // emergency coast all
                for (int i = 0; i < 4; i++) evn_motion_coast(i);
                hal_motor_coast_all();
                s_state = 3;   // DONE
                con_printf(">> BUTTON: coast all\n");
            }
        }

        if ((int64_t)(now - next_batt) >= 0) {
            next_batt = now + BATTERY_US;
            hal_battery_service();
        }

        /* r-test state machine: runs every loop so completion is detected even
         * when the 10 Hz report is off. Only the status print is gated. */
        {
            bool do_print = ((int64_t)(now - next_report) >= 0 && s_report);
            if (do_print) { next_report = now + REPORT_US; con_printf("---\n"); }
            bool all_done = true;
            for (int i = 0; i < 4; i++) {
                float ang, spd; bool stall, done;
                evn_motion_get_state(i, &ang, &spd, &stall, &done);
                if (do_print) {
                    float tgt, tt;
                    evn_motion_get_debug(i, &tgt, &tt);
                    con_printf("M%d: %7.1f deg  %6.1f d/s  tgt=%5.0f tt=%.2fs  %s%s\n", i+1,
                           (double)ang, (double)spd, (double)tgt, (double)tt,
                           stall ? "STALL " : "", done ? "done" : "moving");
                }
                if (!done) all_done = false;
            }

            if (s_state == ST_OUT && all_done) {
                for (int i = 0; i < 4; i++) evn_motion_move_to(i, 0.0f, 180.0f, 900.0f);
                con_printf(">>> all at +360. Commanding return to 0.\n");
                s_state = ST_RETURN;
            } else if (s_state == ST_RETURN && all_done) {
                for (int i = 0; i < 4; i++) evn_motion_coast(i);   // safety: coast all
                hal_motor_coast_all();
                evn_core1_status_t cs;
                if (evn_core1_get_status(&cs)) {
                    con_printf("=== MOTION TEST COMPLETE (all coasted) ===\n");
                          con_printf("Core1: %u ticks, period %u-%u us, exec max %u us, missed %u\n",
                           (unsigned)cs.tick_count, (unsigned)cs.period_min_us,
                              (unsigned)cs.period_max_us, (unsigned)cs.exec_max_us,
                              (unsigned)cs.missed_tick_count);
                }
                print_battery();
                s_state = ST_DONE;   // latched — never re-fires
            }
            /* ST_DONE: idle forever, motors coasted */
        }

        tight_loop_contents();
    }
}
