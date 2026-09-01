#ifndef MOTION_PID_H
#define MOTION_PID_H

#include <stdint.h>
#include <stdbool.h>

/* ==========================================================================
 * EVN ALPHA - Cascaded motor controller (position outer, velocity inner).
 *
 * Per spec section 8.3:
 *   duty = Kp*(pos_err) + Ki*integral(pos_err) + Kv*(vel_err) + Kd*d(vel_meas)
 *          + Kff*accel_ref
 *
 * pos/vel/accel references come from the trajectory profiler; the measured
 * position/speed come from the Luenberger observer. Output is a duty cycle in
 * [-1, +1] for hal_motor_set().
 *
 * Float math is acceptable here (4 axes @ 1 kHz on Cortex-M0+ has headroom;
 * measured Core 1 exec budget ~15 us of 1000 us for encoders alone).
 * ========================================================================== */

typedef struct {
    /* gains */
    float kp_pos;       /* position P (duty per unit error) */
    float ki_pos;       /* position I (anti-windup clamped) */
    float kp_vel;       /* velocity P */
    float kd_vel;       /* velocity D (on measurement, to avoid kick) */
    float kff_accel;    /* acceleration feedforward */

    /* limits */
    float out_min;      /* e.g. -1.0 */
    float out_max;      /* e.g. +1.0 */
    float i_limit;      /* integrator clamp */

    /* battery feedforward compensation scale (0 = disabled) */
    float vbus_comp;    /* nominal voltage (mV) for duty scaling */

    /* state */
    float integrator;
    float prev_vel_meas;
    bool  first;
} evn_pid_t;

void evn_pid_init(evn_pid_t *p);
void evn_pid_reset(evn_pid_t *p);

/* One control step.
 *   pos_ref, vel_ref, accel_ref : trajectory references
 *   pos_meas, vel_meas          : observer estimates (same units)
 *   dt                          : seconds
 *   vbus_mv                     : current battery voltage (mV) for compensation
 * Returns duty in [out_min, out_max]. */
float evn_pid_update(evn_pid_t *p,
                     float pos_ref, float vel_ref, float accel_ref,
                     float pos_meas, float vel_meas, float dt,
                     uint32_t vbus_mv);

#endif /* MOTION_PID_H */
