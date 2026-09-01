#include "motion_engine.h"

#include "core1.h"
#include "../hal/hal_battery.h"
#include "../bench/bench_cycles.h"

#include "pico/stdlib.h"
#include "hardware/sync.h"   /* __dmb */
#include <stdio.h>

/* 1 kHz tick. dt in seconds. */
#define MOTION_DT (1.0f / 1000.0f)

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
        /* Per-model starting gains. EV3 Medium validated on hardware;
         * EV3 Large (more torque/inertia) needs a softer loop for stability. */
        if (a->model == evn_motor_model_get(EVN_MOTOR_MODEL_EV3_LARGE)) {
            a->pid.kp_pos = 2.5e-4f; a->pid.kp_vel = 3.0e-5f;
            a->pid.ki_pos = 1.0e-6f; a->pid.kff_accel = 5.0e-6f;
        } else {   /* EV3 Medium / NXT */
            a->pid.kp_pos = 5.0e-4f; a->pid.kp_vel = 6.0e-5f;
            a->pid.ki_pos = 2.0e-6f; a->pid.kff_accel = 1.0e-5f;
        }
        a->traj.active = false;
        a->traj.done = true;
        a->cmd_seq = 0;
        a->cmd_consumed_seq = 0xFFFFFFFFu;   /* sentinel: no command consumed yet */
        a->cmd_active = false;
        a->stat_seq = 0;
        a->stat_stalled = false;
        a->stat_done = true;
    }
}

void evn_motion_move_to(uint8_t axis, float target_deg,
                        float max_vel_degs, float max_accel_degs2) {
    if (!(s_mask & (1u << axis))) return;
    evn_axis_t *a = &s_axis[axis];

    /* seqlock handover (Core 0 writes, Core 1 reads) */
    a->cmd_seq++;
    __dmb();
    a->cmd_target_deg  = target_deg;
    a->cmd_max_vel_degs = max_vel_degs;
    a->cmd_max_accel   = max_accel_degs2;
    a->cmd_active      = true;
    __dmb();
    a->cmd_seq++;
    printf("[move_to] axis %d target=%.1f seq=%u\n", axis, (double)target_deg, (unsigned)a->cmd_seq);
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

void evn_motion_set_gains(float kp_pos, float ki_pos, float kp_vel, float kd_vel, float kff_accel) {
    for (int i = 0; i < 4; i++) {
        if (!(s_mask & (1u << i))) continue;
        s_axis[i].pid.kp_pos = kp_pos;
        s_axis[i].pid.ki_pos = ki_pos;
        s_axis[i].pid.kp_vel = kp_vel;
        s_axis[i].pid.kd_vel = kd_vel;
        s_axis[i].pid.kff_accel = kff_accel;
    }
}

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
            __dmb();
            if (a->cmd_seq == c0) {          /* stable read */
                a->cmd_consumed_seq = c0;    /* mark consumed */
                if (active) {
                    int32_t sub = hal_encoder_get_position_substep(a->encoder);
                    float cur_mdeg = (float)sub * (360000.0f / axis_substeps_per_rev(i));
                    evn_trajectory_start(&a->traj, cur_mdeg, tdeg * 1000.0f,
                                         mvel * 1000.0f, macc * 1000.0f);
                    evn_pid_reset(&a->pid);
                    a->stat_done = false;
                    a->stat_target_mdeg = (int32_t)(tdeg * 1000.0f);
                    a->stat_total_time = a->traj.total_time;
                } else {
                    hal_motor_coast(a->motor);
                    a->traj.active = false;
                    a->traj.done = true;
                    a->stat_done = true;
                }
            }
        }

        if (!a->traj.active) {
            /* idle: keep observer roughly synced, motor coasted */
            a->stat_seq++;
            __dmb();
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
        float pos_ref, vel_ref, accel_ref;
        evn_trajectory_update(&a->traj, MOTION_DT, &pos_ref, &vel_ref, &accel_ref);

        /* --- observer update driven by the PREVIOUS tick's applied voltage --- */
        evn_observer_update(&a->observer, s_time_ms, angle_mdeg, a->last_applied_mv);
        int32_t th_hat, w_hat, i_hat;
        evn_observer_get_state(&a->observer, &th_hat, &w_hat, &i_hat);

        /* --- cascaded PID + feedforward --- */
        float duty = evn_pid_update(&a->pid, pos_ref, vel_ref, accel_ref,
                              (float)th_hat, (float)w_hat, MOTION_DT, vbus_mv);
        hal_motor_set(a->motor, duty);
        a->last_applied_mv = (int32_t)(duty * (float)vbus_mv);

        /* --- stall + status publish --- */
        uint32_t stall_ms;
        bool stalled = evn_observer_is_stalled(&a->observer, s_time_ms, &stall_ms);

        a->stat_seq++;
        __dmb();
        a->stat_angle_mdeg = th_hat;
        a->stat_speed_mdegs = w_hat;
        a->stat_stalled = stalled;
        a->stat_done = a->traj.done;
        __dmb();
        a->stat_seq++;
    }
}
