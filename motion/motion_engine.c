#include "motion_engine.h"

#include "core1.h"
#include "../hal/hal_battery.h"
#include "../bench/bench_cycles.h"

#include "pico/stdlib.h"
#include "hardware/sync.h"   /* __dmb */
#include <stdio.h>

/* 1 kHz tick. dt in seconds. */
#define MOTION_DT (1.0f / 1000.0f)
#define MOTION_NOMINAL_VBUS_MV 7400u
#define OBSERVER_PERIOD_TICKS 5u

/* Convert between encoder substeps and millidegrees.
 * Encoder edge counting: LEGO motors = 720 edges/rev (180 pulses × 4 edges,
 * both channels). The substep PIO counts 1 "step" per edge and interpolates
 * 256 substeps per quadrature cycle (= 4 edges). So:
 *   steps_per_rev    = counts_per_rev            (edges)
 *   substeps_per_rev = (counts_per_rev / 4) * 256
 *   mdeg_per_rev     = 360000 */
static evn_axis_t s_axis[4];
static uint8_t    s_mask = 0;
static uint32_t   s_time_ms = 0;
static bool       s_ff_on = true;   /* model-based feedforward (validated ON) */

/* --- 1 kHz trace (tuning): one axis at a time, static buffer, no heap --- */
typedef struct {
    int32_t t_ms, ref_mdeg, enc_mdeg, hat_mdeg, vref_mdegs, what_mdegs, duty_milli, cur_01ma;
} evn_trace_row_t;
static evn_trace_row_t s_trace[EVN_TRACE_MAX];
static volatile uint8_t  s_trace_axis = 0;
static volatile uint32_t s_trace_count = 0;
static volatile bool     s_trace_armed = false;
static uint8_t           s_trace_divider = 0;

void evn_motion_trace_arm(uint8_t axis) {
    if (axis > 3) return;
    s_trace_armed = false;
    __dmb();
    s_trace_axis = axis;
    s_trace_count = 0;
    s_trace_divider = 0;
    __dmb();
    s_trace_armed = true;
}

void evn_motion_trace_stop(void) {
    s_trace_armed = false;
    __dmb();
}

bool evn_motion_trace_info(uint8_t *axis, uint32_t *count, bool *armed) {
    __dmb();
    *axis = s_trace_axis;
    *count = s_trace_count;
    *armed = s_trace_armed;
    return true;
}

bool evn_motion_trace_row(uint32_t i, int32_t *t_ms, int32_t *ref_mdeg,
                          int32_t *enc_mdeg, int32_t *hat_mdeg,
                          int32_t *vref_mdegs, int32_t *what_mdegs,
                          int32_t *duty_milli, int32_t *cur_01ma) {
    if (i >= s_trace_count) return false;
    const evn_trace_row_t *r = &s_trace[i];
    *t_ms = r->t_ms; *ref_mdeg = r->ref_mdeg; *enc_mdeg = r->enc_mdeg;
    *hat_mdeg = r->hat_mdeg; *vref_mdegs = r->vref_mdegs;
    *what_mdegs = r->what_mdegs; *duty_milli = r->duty_milli;
    *cur_01ma = r->cur_01ma;
    return true;
}

static float axis_substeps_per_rev(uint8_t i) {
    return (s_axis[i].counts_per_rev / 4.0f) * 256.0f;
}

void evn_motion_init(const evn_motor_model_t *const models[4],
                     const float counts_per_rev[4], uint8_t motor_mask) {
    s_mask = motor_mask;
    for (int i = 0; i < 4; i++) {
        if (!(motor_mask & (1u << i))) continue;
        evn_axis_t *a = &s_axis[i];
        a->motor = (evn_motor_id_t)i;
        a->encoder = (evn_encoder_id_t)i;
        a->model = models[i];
        a->counts_per_rev = counts_per_rev[i];

        /* default observer settings (Pybricks-derived) */
        a->observer.settings = (evn_observer_settings_t){
            .stall_speed_limit = 50000,            /* 50 deg/s in mdeg/s */
            .stall_time_ms = 50,
            .feedback_voltage_negligible = 500,    /* mV */
            .feedback_voltage_stall_ratio = 50,
            .feedback_gain_low = 45,
            .feedback_gain_high = 200,
            .feedback_gain_threshold = 5000,       /* 5 deg in mdeg */
            .coulomb_friction_speed_cutoff = 20000,/* 20 deg/s */
        };
        evn_observer_init(&a->observer, a->model, &a->observer.settings, 0);
        evn_pid_init(&a->pid);
        /* Per-model gains, validated on hardware (2026-09-01): position loop on
         * the true encoder + edge-timed encoder speed + model feedforward + a
         * 0.4 deg hold deadzone + a 12% stiction-break floor. EV3 Medium tracks
         * to 0.000 deg; EV3 Large needs the stronger kp/ki to break stiction
         * and converge to ~0.04 deg. */
        if (a->model == evn_motor_model_get(EVN_MOTOR_MODEL_EV3_MEDIUM)) {
            a->pid.kp_pos = 8.0e-5f; a->pid.kp_vel = 8.0e-7f;
            a->pid.ki_pos = 8.0e-7f; a->pid.kff_accel = 0.0f;
            a->pid.start_duty = 0.65f; a->pid.min_duty = 0.45f;
        } else {   /* EV3 Large / NXT */
            a->pid.kp_pos = 8.0e-5f; a->pid.kp_vel = 1.0e-6f;
            a->pid.ki_pos = 1.0e-6f; a->pid.kff_accel = 0.0f;
            a->pid.start_duty = 0.12f; a->pid.min_duty = 0.12f;
        }
        a->last_applied_mv = 0;
        a->observer_voltage_sum_mv = 0;
        a->observer_divider = 0;
        a->edge_speed_filtered = 0.0f;
        a->edge_speed_alpha = 0.05f;
        a->profile_vel_scale = 1.0f;
        a->profile_accel_scale = 1.0f;
        a->trajectory_type = EVN_TRAJECTORY_TRAPEZOID;
        a->startup_reference_governor = false;
        a->active_startup_reference_governor = false;
        a->friction_feedforward_permille = 500u;
        a->active_friction_feedforward_permille = 500u;
        a->edge_watchdog_enabled = false;
        a->active_edge_watchdog_enabled = false;
        a->traj.active = false;
        a->traj.done = true;
        a->cmd_seq = 0;
        a->cmd_consumed_seq = 0xFFFFFFFFu;   /* sentinel: no command consumed yet */
        a->cmd_active = false;
        a->stat_seq = 0;
        a->stat_stalled = false;
        a->stat_done = true;
        a->holding = false;
        a->auto_coast_deadline_ms = 0;
    }
}

void evn_motion_move_to_test(uint8_t axis, float target_deg,
                             float max_vel_degs, float max_accel_degs2,
                             uint32_t auto_coast_ms) {
    if (!(s_mask & (1u << axis))) return;
    evn_axis_t *a = &s_axis[axis];

    /* seqlock handover (Core 0 writes, Core 1 reads) */
    a->cmd_seq++;
    __dmb();
    a->cmd_target_deg  = target_deg;
    a->cmd_max_vel_degs = max_vel_degs;
    a->cmd_max_accel   = max_accel_degs2;
    a->cmd_vel_scale   = a->profile_vel_scale;
    a->cmd_accel_scale = a->profile_accel_scale;
    a->cmd_trajectory_type = a->trajectory_type;
    a->cmd_startup_reference_governor = a->startup_reference_governor;
    a->cmd_friction_feedforward_permille = a->friction_feedforward_permille;
    a->cmd_edge_watchdog_enabled = a->edge_watchdog_enabled;
    a->cmd_auto_coast_ms = auto_coast_ms;
    a->cmd_active      = true;
    __dmb();
    a->cmd_seq++;
    /* NOTE: no printf here — this runs in the command path and must not touch
     * blocking stdio (dual-core USB deadlock). */
}

void evn_motion_move_to(uint8_t axis, float target_deg,
                        float max_vel_degs, float max_accel_degs2) {
    evn_motion_move_to_test(axis, target_deg, max_vel_degs, max_accel_degs2, 0);
}

void evn_motion_coast(uint8_t axis) {
    if (!(s_mask & (1u << axis))) return;
    evn_axis_t *a = &s_axis[axis];
    a->cmd_seq++;
    __dmb();
    a->cmd_active = false;
    __dmb();
    a->cmd_seq++;
}

void evn_motion_hold(uint8_t axis) {
    /* hold current position: command a move to the current measured angle */
    if (!(s_mask & (1u << axis))) return;
    evn_axis_t *a = &s_axis[axis];
    float cur_deg = (float)a->stat_angle_mdeg / 1000.0f;
    evn_motion_move_to(axis, cur_deg, 200.0f, 1000.0f);
}

bool evn_motion_get_state(uint8_t axis, float *angle_deg, float *speed_degs,
                          bool *stalled, bool *done) {
    if (!(s_mask & (1u << axis))) return false;
    evn_axis_t *a = &s_axis[axis];
    uint32_t s0, s1;
    do {
        s0 = a->stat_seq;
        if (s0 & 1u) continue;
        __dmb();
        *angle_deg = (float)a->stat_angle_mdeg / 1000.0f;
        *speed_degs = (float)a->stat_speed_mdegs / 1000.0f;
        *stalled = a->stat_stalled;
        *done = a->stat_done;
        __dmb();
        s1 = a->stat_seq;
    } while (s0 != s1 || (s0 & 1u));
    return true;
}

/* Debug: read commanded target (deg) + computed profile duration (s). */
bool evn_motion_get_debug(uint8_t axis, float *target_deg, float *total_time_s) {
    if (!(s_mask & (1u << axis))) return false;
    evn_axis_t *a = &s_axis[axis];
    *target_deg = (float)a->stat_target_mdeg / 1000.0f;
    *total_time_s = a->stat_total_time;
    return true;
}

bool evn_motion_get_profile(uint8_t axis, float *max_vel_degs,
                            float *max_accel_degs2) {
    if (!(s_mask & (1u << axis))) return false;
    evn_axis_t *a = &s_axis[axis];
    *max_vel_degs = a->stat_max_vel_degs;
    *max_accel_degs2 = a->stat_max_accel_degs2;
    return true;
}

bool evn_motion_get_profile_scale(uint8_t axis, float *vel_scale,
                                  float *accel_scale) {
    if (!(s_mask & (1u << axis))) return false;
    evn_axis_t *a = &s_axis[axis];
    *vel_scale = a->stat_vel_scale;
    *accel_scale = a->stat_accel_scale;
    return true;
}

void evn_motion_set_gains(float kp_pos, float ki_pos, float kp_vel, float kd_vel, float kff_accel) {
    for (int i = 0; i < 4; i++) {
        if (!(s_mask & (1u << i))) continue;
        evn_motion_set_gains_axis(i, kp_pos, ki_pos, kp_vel, kd_vel, kff_accel);
    }
}

void evn_motion_set_gains_axis(uint8_t axis, float kp_pos, float ki_pos,
                               float kp_vel, float kd_vel, float kff_accel) {
    if (axis > 3 || !(s_mask & (1u << axis))) return;
    evn_pid_t *p = &s_axis[axis].pid;
    p->kp_pos = kp_pos;
    p->ki_pos = ki_pos;
    p->kp_vel = kp_vel;
    p->kd_vel = kd_vel;
    p->kff_accel = kff_accel;
}

void evn_motion_set_stiction(uint8_t axis, float start_duty, float hold_duty) {
    if (axis > 3 || !(s_mask & (1u << axis))) return;
    if (start_duty < 0.0f) start_duty = 0.0f;
    if (start_duty > 1.0f) start_duty = 1.0f;
    if (hold_duty < 0.0f) hold_duty = 0.0f;
    if (hold_duty > 1.0f) hold_duty = 1.0f;
    s_axis[axis].pid.start_duty = start_duty;
    s_axis[axis].pid.min_duty = hold_duty;
}

void evn_motion_set_velocity_source(uint8_t axis, int source) {
    if (axis > 3 || !(s_mask & (1u << axis))) return;
    if (source < 0) source = 0;
    if (source > 3) source = 3;
    s_axis[axis].pid.use_enc_speed = source;
}

void evn_motion_set_speed_window(uint8_t axis, int samples) {
    if (axis > 3 || !(s_mask & (1u << axis))) return;
    if (samples < 2) samples = 2;
    if (samples > PID_SPEED_WINDOW) samples = PID_SPEED_WINDOW;
    s_axis[axis].pid.vel_window = samples;
}

int evn_motion_speed_window(uint8_t axis) {
    if (axis > 3 || !(s_mask & (1u << axis))) return 0;
    return s_axis[axis].pid.vel_window;
}

void evn_motion_set_edge_speed_alpha(uint8_t axis, float alpha) {
    if (axis > 3 || !(s_mask & (1u << axis))) return;
    if (alpha < 0.001f) alpha = 0.001f;
    if (alpha > 1.0f) alpha = 1.0f;
    s_axis[axis].edge_speed_alpha = alpha;
}

float evn_motion_edge_speed_alpha(uint8_t axis) {
    if (axis > 3 || !(s_mask & (1u << axis))) return 0.0f;
    return s_axis[axis].edge_speed_alpha;
}

void evn_motion_set_profile_scale(uint8_t axis, float vel_scale,
                                  float accel_scale) {
    if (axis > 3 || !(s_mask & (1u << axis))) return;
    if (vel_scale < 0.1f) vel_scale = 0.1f;
    if (vel_scale > 1.0f) vel_scale = 1.0f;
    if (accel_scale < 0.1f) accel_scale = 0.1f;
    if (accel_scale > 1.0f) accel_scale = 1.0f;
    s_axis[axis].profile_vel_scale = vel_scale;
    s_axis[axis].profile_accel_scale = accel_scale;
}

void evn_motion_set_trajectory_type(uint8_t axis, evn_trajectory_type_t type) {
    if (axis > 3 || !(s_mask & (1u << axis))) return;
    if (type != EVN_TRAJECTORY_TRAPEZOID &&
        type != EVN_TRAJECTORY_MINIMUM_JERK) return;
    s_axis[axis].trajectory_type = type;
}

void evn_motion_set_startup_reference_governor(uint8_t axis, bool enabled) {
    if (axis > 3 || !(s_mask & (1u << axis))) return;
    s_axis[axis].startup_reference_governor = enabled;
}

void evn_motion_set_friction_feedforward(uint8_t axis, uint16_t permille) {
    if (axis > 3 || !(s_mask & (1u << axis)) || permille > 2000u) return;
    s_axis[axis].friction_feedforward_permille = permille;
}

void evn_motion_set_startup_release_speed(uint8_t axis, float speed_degs) {
    if (axis > 3 || !(s_mask & (1u << axis)) ||
        speed_degs < 0.0f || speed_degs > 100.0f) return;
    s_axis[axis].pid.startup_release_speed_mdegs = speed_degs * 1000.0f;
}

void evn_motion_set_edge_watchdog(uint8_t axis, bool enabled) {
    if (axis > 3 || !(s_mask & (1u << axis))) return;
    s_axis[axis].edge_watchdog_enabled = enabled;
}

const evn_pid_t *evn_motion_axis_pid(uint8_t axis) {
    if (axis > 3) return NULL;
    return &s_axis[axis].pid;
}

void evn_motion_set_feedforward(bool on) { s_ff_on = on; }
bool evn_motion_feedforward_on(void) { return s_ff_on; }

void evn_motion_set_observer(int32_t stall_speed_limit, int32_t stall_time_ms,
                             int32_t fb_negligible, int32_t fb_stall_ratio) {
    for (int i = 0; i < 4; i++) {
        if (!(s_mask & (1u << i))) continue;
        evn_observer_settings_t *s = &s_axis[i].observer.settings;
        s->stall_speed_limit = stall_speed_limit;
        s->stall_time_ms = stall_time_ms;
        s->feedback_voltage_negligible = fb_negligible;
        s->feedback_voltage_stall_ratio = fb_stall_ratio;
    }
}

void __not_in_flash_func(evn_motion_tick)(void) {
    s_time_ms++;

    /* battery voltage for feedforward compensation (lock-free cache) */
    uint32_t vbus_mv = hal_battery_voltage_mv();
    if (vbus_mv == 0) vbus_mv = MOTION_NOMINAL_VBUS_MV;

    for (int i = 0; i < 4; i++) {
        if (!(s_mask & (1u << i))) continue;
        evn_axis_t *a = &s_axis[i];

        /* --- consume a NEW command exactly once (seqlock read) --- */
        uint32_t c0 = a->cmd_seq;
        if (!(c0 & 1u) && c0 != a->cmd_consumed_seq) {
            __dmb();
            bool  active = a->cmd_active;
            float tdeg   = a->cmd_target_deg;
            float mvel   = a->cmd_max_vel_degs;
            float macc   = a->cmd_max_accel;
            float vel_scale = a->cmd_vel_scale;
            float accel_scale = a->cmd_accel_scale;
            evn_trajectory_type_t trajectory_type = a->cmd_trajectory_type;
            bool startup_reference_governor = a->cmd_startup_reference_governor;
            uint16_t friction_feedforward_permille =
                a->cmd_friction_feedforward_permille;
            bool edge_watchdog_enabled = a->cmd_edge_watchdog_enabled;
            uint32_t auto_coast_ms = a->cmd_auto_coast_ms;
            __dmb();
            if (a->cmd_seq == c0) {          /* stable read */
                a->cmd_consumed_seq = c0;    /* mark consumed */
                if (active) {
                    int32_t sub = hal_encoder_get_position_substep(a->encoder);
                    float cur_mdeg = (float)sub * (360000.0f / axis_substeps_per_rev(i));
                    /* re-sync observer to the measured shaft state on engage
                     * (clears drift accumulated while coasted) */
                    evn_observer_init(&a->observer, a->model, &a->observer.settings,
                                      (int32_t)cur_mdeg);
                    evn_trajectory_start_type(&a->traj, cur_mdeg, tdeg * 1000.0f,
                                              mvel * vel_scale * 1000.0f,
                                              macc * accel_scale * 1000.0f,
                                              trajectory_type);
                    evn_pid_reset(&a->pid, cur_mdeg);
                    a->last_applied_mv = 0;
                    a->observer_voltage_sum_mv = 0;
                    a->observer_divider = 0;
                    a->edge_speed_filtered =
                        (float)hal_encoder_get_speed_substep(a->encoder) *
                        (360000.0f / axis_substeps_per_rev(i));
                    a->active_startup_reference_governor = startup_reference_governor;
                    a->active_friction_feedforward_permille =
                        friction_feedforward_permille;
                    a->active_edge_watchdog_enabled = edge_watchdog_enabled;
                    a->holding = true;
                    a->auto_coast_deadline_ms = auto_coast_ms ? s_time_ms + auto_coast_ms : 0;
                    a->stat_done = false;
                    a->stat_target_mdeg = (int32_t)(tdeg * 1000.0f);
                    a->stat_total_time = a->traj.total_time;
                    a->stat_max_vel_degs = mvel;
                    a->stat_max_accel_degs2 = macc;
                    a->stat_vel_scale = vel_scale;
                    a->stat_accel_scale = accel_scale;
                } else {
                    hal_motor_coast(a->motor);
                    a->traj.active = false;
                    a->traj.done = true;
                    a->holding = false;
                    a->auto_coast_deadline_ms = 0;
                    a->stat_done = true;
                    a->last_applied_mv = 0;
                    a->observer_voltage_sum_mv = 0;
                    a->observer_divider = 0;
                    a->edge_speed_filtered = 0.0f;
                }
            }
        }

        if (a->holding && a->auto_coast_deadline_ms != 0 &&
            (int32_t)(s_time_ms - a->auto_coast_deadline_ms) >= 0) {
            hal_motor_coast(a->motor);
            a->traj.active = false;
            a->traj.done = true;
            a->holding = false;
            a->auto_coast_deadline_ms = 0;
            a->stat_done = true;
        }

        if (!a->holding) {
            /* coasted: keep the published angle tracking the encoder so CPR
             * checks and relative moves see the true shaft position */
            int32_t sub = hal_encoder_get_position_substep(a->encoder);
            int32_t enc_mdeg = (int32_t)((float)sub * (360000.0f / axis_substeps_per_rev(i)));
            a->stat_seq++;
            __dmb();
            a->stat_angle_mdeg = enc_mdeg;
            a->stat_speed_mdegs = 0;
            a->stat_stalled = false;
            __dmb();
            a->stat_seq++;
            continue;
        }

        /* --- sense --- */
        int32_t sub = hal_encoder_get_position_substep(a->encoder);
        float scale = 360000.0f / axis_substeps_per_rev(i);
        int32_t angle_mdeg = (int32_t)((float)sub * scale);

        /* --- trajectory reference --- */
        float startup_displacement = (float)angle_mdeg - a->pid.motion_start_position;
        if (startup_displacement < 0.0f) startup_displacement = -startup_displacement;
        if (a->active_startup_reference_governor &&
            startup_displacement >= 100.0f && startup_displacement <= 5000.0f)
            evn_trajectory_advance_to_position(&a->traj, (float)angle_mdeg);
        float pos_ref, vel_ref, accel_ref;
        float trajectory_time = a->traj.t;
        evn_trajectory_update(&a->traj, MOTION_DT, &pos_ref, &vel_ref, &accel_ref);
        float abs_vel_ref = vel_ref < 0.0f ? -vel_ref : vel_ref;
        bool edge_watchdog_stuck = false;
        if (a->active_edge_watchdog_enabled && a->traj.active &&
            abs_vel_ref > 5000.0f) {
            uint32_t expected_edge_us = 500000000u / (uint32_t)abs_vel_ref;
            uint32_t edge_timeout_us = 2u * expected_edge_us + 2000u;
            if (edge_timeout_us < 10000u) edge_timeout_us = 10000u;
            if (edge_timeout_us > 250000u) edge_timeout_us = 250000u;
            edge_watchdog_stuck =
                hal_encoder_get_transition_age_us(a->encoder) > edge_timeout_us;
        }
        if (a->traj.active && a->pid.start_duty > 0.2f &&
            ((startup_displacement < 100.0f && abs_vel_ref > 5000.0f) ||
             edge_watchdog_stuck)) {
            a->traj.t = trajectory_time;
        }
        a->pid.motion_stuck = edge_watchdog_stuck;

        /* Model coefficients are discretized for 5 ms. Average the voltage
         * actually applied over five 1 ms control ticks before one update. */
        a->observer_voltage_sum_mv += a->last_applied_mv;
        a->observer_divider++;
        if (a->observer_divider >= OBSERVER_PERIOD_TICKS) {
            int32_t average_mv = a->observer_voltage_sum_mv / (int32_t)OBSERVER_PERIOD_TICKS;
            evn_observer_update(&a->observer, s_time_ms, angle_mdeg, average_mv);
            a->observer_voltage_sum_mv = 0;
            a->observer_divider = 0;
        }
        int32_t th_hat, w_hat, i_hat;
        evn_observer_get_state(&a->observer, &th_hat, &w_hat, &i_hat);

        /* velocity feedback: differentiate the HIGH-RES substep position over a
         * window (the substep PIO gives 1/256-count resolution — far finer than
         * the 360 counts/rev Pybricks assumes). Robust to the HAL edge-timed
         * speed's stop-latch dropouts. use_enc_speed==0 -> observer speed. */
        float pos_meas = (float)angle_mdeg;   /* position loop on true encoder */
        float vel_meas = (float)w_hat;
        float edge_speed = (float)hal_encoder_get_speed_substep(a->encoder) * scale;
        a->edge_speed_filtered += a->edge_speed_alpha *
                                  (edge_speed - a->edge_speed_filtered);
        float vel_for_pid;
        if (a->pid.use_enc_speed == 3) {
            vel_for_pid = a->edge_speed_filtered;
        } else if (a->pid.use_enc_speed == 2) {
            vel_for_pid = edge_speed;
        } else if (a->pid.use_enc_speed == 1) {
            vel_for_pid = evn_pid_speed_of(&a->pid, pos_meas, MOTION_DT);
        } else {
            vel_for_pid = vel_meas;
        }
        a->prev_enc_mdeg = angle_mdeg;

        /* Model feedforward is voltage-based and enters the PID before its
         * single saturation/anti-windup decision. */
        float feedforward_duty = 0.0f;
        if (s_ff_on && vbus_mv > 0) {
            int32_t t_ff = evn_observer_feedforward_torque_scaled(
                a->model, (int32_t)vel_ref, (int32_t)accel_ref,
                a->active_friction_feedforward_permille);
            int32_t v_ff = evn_observer_torque_to_voltage(a->model, t_ff);
            feedforward_duty = (float)v_ff / (float)vbus_mv;
        }

        float duty = evn_pid_update(&a->pid, pos_ref, vel_ref, accel_ref,
                              pos_meas, vel_for_pid, MOTION_DT,
                              feedforward_duty, vbus_mv);

        hal_motor_set(a->motor, duty);
        a->last_applied_mv = (int32_t)(duty * (float)vbus_mv);

        /* --- trace capture (armed axis only) --- */
        if (s_trace_armed && s_trace_axis == i) {
            bool capture = s_trace_divider == 0;
            if (++s_trace_divider >= EVN_TRACE_SAMPLE_DIV) s_trace_divider = 0;
            if (capture && s_trace_count < EVN_TRACE_MAX) {
                evn_trace_row_t *r = &s_trace[s_trace_count];
                r->t_ms = (int32_t)s_time_ms;
                r->ref_mdeg = (int32_t)pos_ref;
                r->enc_mdeg = angle_mdeg;
                r->hat_mdeg = th_hat;
                r->vref_mdegs = (int32_t)vel_ref;
                r->what_mdegs = (int32_t)a->pid.last_vel_smooth;
                r->duty_milli = (int32_t)(duty * 1000.0f);
                r->cur_01ma = i_hat;
                __dmb();
                s_trace_count++;
                if (s_trace_count >= EVN_TRACE_MAX) s_trace_armed = false;
            }
        }

        /* --- stall + status publish --- */
        uint32_t stall_ms;
        bool stalled = evn_observer_is_stalled(&a->observer, s_time_ms, &stall_ms);

        a->stat_seq++;
        __dmb();
        a->stat_angle_mdeg = angle_mdeg;   /* report TRUE encoder angle (not diverging θ̂) */
        a->stat_speed_mdegs = (int32_t)vel_for_pid;
        a->stat_stalled = stalled;
        a->stat_done = a->traj.done;
        __dmb();
        a->stat_seq++;
    }
}
