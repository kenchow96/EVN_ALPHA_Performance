#ifndef MOTION_PID_H
#define MOTION_PID_H

#include <stdint.h>
#include <stdbool.h>

/* Speed window length (samples at 1 kHz). 60 ms boxcar — wide enough that the
 * 0.5°/edge encoder quantization doesn't step the velocity estimate, narrow
 * enough to track the trapezoid accel. (Pybricks uses ~100 ms at 5 ms loop.) */
#define PID_SPEED_WINDOW 60

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
    float i_limit;      /* maximum integral contribution to duty */

    /* battery feedforward compensation scale (0 = disabled) */
    float vbus_comp;    /* nominal voltage (mV) for duty scaling */

    /* speed source: 0=observer, 1=windowed, 2=raw edge, 3=filtered edge */
    int   use_enc_speed;

    /* deadband (mdeg): inside this position error the integrator decays and the
     * velocity P term is dropped, so holding doesn't limit-cycle on encoder
     * quantization noise. 0 = disabled. */
    float deadzone_mdeg;

    /* stiction-break floor: when |pos_err| exceeds the deadzone, guarantee the
     * output duty reaches at least this magnitude in the correcting direction,
     * so the position loop can always overcome static friction. 0 = disabled. */
    float min_duty;
    float start_duty;

    /* state */
    float integrator;   /* accumulated integral contribution in duty units */
    float prev_vel_meas;
    bool  first;
    float motion_start_position;

    /* Pybricks-style windowed differentiator for a low-noise speed estimate
     * (averages position increments over a window, not per-tick). */
    float pos_hist[PID_SPEED_WINDOW];   /* ring buffer of pos_meas (mdeg) */
    int   pos_hist_idx;
    int   vel_window;                   /* active differentiator window (<= PID_SPEED_WINDOW) */
    float last_vel_smooth;              /* last windowed speed used (debug) */
    int   stick_ticks;                  /* consecutive ticks stuck in the approach band */
} evn_pid_t;

void evn_pid_init(evn_pid_t *p);
void evn_pid_reset(evn_pid_t *p, float initial_position);

/* Windowed (low-noise) speed estimate from position. Advances the ring buffer;
 * call once per tick before evn_pid_update so both see the same value. */
float evn_pid_speed_of(evn_pid_t *p, float pos_meas, float dt);

/* One control step.
 *   pos_ref, vel_ref, accel_ref : trajectory references
 *   pos_meas, vel_meas          : observer estimates (same units)
 *   dt                          : seconds
 *   vbus_mv                     : current battery voltage (mV) for compensation
 * Returns duty in [out_min, out_max]. */
float evn_pid_update(evn_pid_t *p,
                     float pos_ref, float vel_ref, float accel_ref,
                     float pos_meas, float vel_meas, float dt,
                     float feedforward_duty, uint32_t vbus_mv);

#endif /* MOTION_PID_H */
