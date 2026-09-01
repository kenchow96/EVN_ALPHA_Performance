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

    /* commanded state (Core 0 → Core 1 handover) */
    volatile uint32_t cmd_seq;
    volatile bool     cmd_active;
    volatile float    cmd_target_deg;
    volatile float    cmd_max_vel_degs;
    volatile float    cmd_max_accel;

    /* live status (Core 1 → Core 0) */
    volatile uint32_t stat_seq;
    volatile int32_t  stat_angle_mdeg;
    volatile int32_t  stat_speed_mdegs;
    volatile bool     stat_stalled;
    volatile bool     stat_done;
} evn_axis_t;

/* Initialise the engine: claim motor+encoder masks and attach a standard
 * model + CPR to each axis. `models[i]` / `cpr[i]` correspond to motor i. */
void evn_motion_init(const evn_motor_model_t *const models[4],
                     const float counts_per_rev[4], uint8_t motor_mask);

/* Command a trapezoidal move to `target_deg` (degrees at output). */
void evn_motion_move_to(uint8_t axis, float target_deg,
                        float max_vel_degs, float max_accel_degs2);

/* Stop an axis (coast) / hold position (active brake + hold loop). */
void evn_motion_coast(uint8_t axis);
void evn_motion_hold(uint8_t axis);

/* Read live axis state (degrees, deg/s, stalled, done). */
bool evn_motion_get_state(uint8_t axis, float *angle_deg, float *speed_degs,
                          bool *stalled, bool *done);

/* The Core 1 tick — call from evn_core1_tick() every 1 ms. */
void __not_in_flash_func(evn_motion_tick)(void);

#endif /* MOTION_ENGINE_H */
