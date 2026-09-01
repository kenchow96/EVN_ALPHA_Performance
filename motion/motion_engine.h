#ifndef MOTION_ENGINE_H
#define MOTION_ENGINE_H

#include <stdint.h>
#include <stdbool.h>

#include "pico/stdlib.h"   /* __not_in_flash_func */

#include "../hal/hal_motor.h"
#include "../hal/hal_encoder.h"
#include "motor_models.h"
#include "observer.h"
#include "trajectory.h"
#include "pid.h"

/* ==========================================================================
 * EVN ALPHA — Motion Engine (Core 1, 1 kHz).
 *
 * Per-motor closed-loop pipeline run every Core 1 tick:
 *   encoder substep → mdeg → observer (θ̂,ω̂,î) → trajectory (θ*,ω*,α*)
 *   → cascaded PID + feedforward → duty (battery-compensated) → DRV8833 PWM
 *
 * Configure each port with its standard-peripheral model + encoder scale, then
 * command moves. Threading: command API is called from Core 0 (user), the tick
 * runs on Core 1. A small request structure is handed over via seqlock.
 * ========================================================================== */

/* Encoder counts-per-degree at the motor shaft. Configured per motor from its
 * CPR × gear ratio. (Set via evn_motion_set_cpr; observer works in mdeg.) */
typedef struct {
    evn_motor_id_t         motor;
    evn_encoder_id_t       encoder;
    const evn_motor_model_t *model;
    float                  counts_per_rev;   /* encoder counts per output rev */

    evn_observer_t         observer;
    evn_trajectory_t       traj;
    evn_pid_t              pid;
    int32_t                last_applied_mv;   /* voltage applied last tick (drives observer) */
    int32_t                observer_voltage_sum_mv;
    uint8_t                observer_divider;
    float                  edge_speed_filtered;
    float                  edge_speed_alpha;
    float                  profile_vel_scale;
    float                  profile_accel_scale;

    /* commanded state (Core 0 → Core 1 handover) */
    volatile uint32_t cmd_seq;
    volatile bool     cmd_active;
    volatile float    cmd_target_deg;
    volatile float    cmd_max_vel_degs;
    volatile float    cmd_max_accel;
    volatile float    cmd_vel_scale;
    volatile float    cmd_accel_scale;
    volatile uint32_t cmd_auto_coast_ms;
    uint32_t          cmd_consumed_seq;   /* Core 1: last cmd_seq acted upon */

    /* live status (Core 1 → Core 0) */
    volatile uint32_t stat_seq;
    volatile int32_t  stat_angle_mdeg;
    volatile int32_t  stat_speed_mdegs;
    volatile bool     stat_stalled;
    volatile bool     stat_done;
    volatile int32_t  stat_target_mdeg;   /* debug: commanded target */
    volatile float    stat_total_time;    /* debug: computed profile duration */
    volatile float    stat_max_vel_degs;
    volatile float    stat_max_accel_degs2;
    volatile float    stat_vel_scale;
    volatile float    stat_accel_scale;

    bool              holding;   /* Core 1: keep regulating at target until coasted */
    uint32_t          auto_coast_deadline_ms;
    int32_t           prev_enc_mdeg;   /* Core 1: last encoder angle (for speed) */
} evn_axis_t;

/* Initialise the engine: claim motor+encoder masks and attach a standard
 * model + CPR to each axis. `models[i]` / `cpr[i]` correspond to motor i. */
void evn_motion_init(const evn_motor_model_t *const models[4],
                     const float counts_per_rev[4], uint8_t motor_mask);

/* Command a trapezoidal move to `target_deg` (degrees at output). */
void evn_motion_move_to(uint8_t axis, float target_deg,
                        float max_vel_degs, float max_accel_degs2);
void evn_motion_move_to_test(uint8_t axis, float target_deg,
                             float max_vel_degs, float max_accel_degs2,
                             uint32_t auto_coast_ms);

/* Stop an axis (coast) / hold position (active brake + hold loop). */
void evn_motion_coast(uint8_t axis);
void evn_motion_hold(uint8_t axis);

/* Read live axis state (degrees, deg/s, stalled, done). */
bool evn_motion_get_state(uint8_t axis, float *angle_deg, float *speed_degs,
                          bool *stalled, bool *done);

/* Debug: commanded target (deg) and computed profile duration (s). */
bool evn_motion_get_debug(uint8_t axis, float *target_deg, float *total_time_s);
bool evn_motion_get_profile(uint8_t axis, float *max_vel_degs,
                            float *max_accel_degs2);
bool evn_motion_get_profile_scale(uint8_t axis, float *vel_scale,
                                  float *accel_scale);

/* Runtime tuning (Core 0, e.g. from a serial console). Apply to all axes. */
void evn_motion_set_gains(float kp_pos, float ki_pos, float kp_vel, float kd_vel, float kff_accel);
/* Per-axis variant (tune one motor at a time). */
void evn_motion_set_gains_axis(uint8_t axis, float kp_pos, float ki_pos,
                               float kp_vel, float kd_vel, float kff_accel);
void evn_motion_set_stiction(uint8_t axis, float start_duty, float hold_duty);
void evn_motion_set_velocity_source(uint8_t axis, int source);
void evn_motion_set_edge_speed_alpha(uint8_t axis, float alpha);
float evn_motion_edge_speed_alpha(uint8_t axis);
void evn_motion_set_profile_scale(uint8_t axis, float vel_scale,
                                  float accel_scale);
/* Read an axis' current PID block (Core 0 debug/console use only). */
const evn_pid_t *evn_motion_axis_pid(uint8_t axis);
void evn_motion_set_observer(int32_t stall_speed_limit, int32_t stall_time_ms,
                             int32_t fb_negligible, int32_t fb_stall_ratio);
/* Model-based feedforward (friction + back-EMF + accel → voltage) toggle. */
void evn_motion_set_feedforward(bool on);
bool evn_motion_feedforward_on(void);

/* --- 1 kHz per-axis trace (tuning): record ref/meas/duty every tick --- */
#define EVN_TRACE_MAX 2500   /* rows × 32 B = 80 KB static */
void     evn_motion_trace_arm(uint8_t axis);   /* clear + start recording */
void     evn_motion_trace_stop(void);          /* stop recording (keep data) */
bool     evn_motion_trace_info(uint8_t *axis, uint32_t *count, bool *armed);
bool     evn_motion_trace_row(uint32_t i, int32_t *t_ms, int32_t *ref_mdeg,
                              int32_t *enc_mdeg, int32_t *hat_mdeg,
                              int32_t *vref_mdegs, int32_t *what_mdegs,
                              int32_t *duty_milli, int32_t *cur_01ma);

/* The Core 1 tick — call from evn_core1_tick() every 1 ms. */
void __not_in_flash_func(evn_motion_tick)(void);

#endif /* MOTION_ENGINE_H */
