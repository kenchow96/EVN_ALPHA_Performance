#ifndef MOTION_TRAJECTORY_H
#define MOTION_TRAJECTORY_H

#include <stdint.h>
#include <stdbool.h>

/* ===========================================================================
 * EVN ALPHA — deterministic point-to-point trajectory profiler.
 *
 * Generates a reference state [ position, velocity, acceleration ] each tick
 * for a point-to-point move with trapezoidal velocity profile (finite
 * acceleration & deceleration). Runs on the 1 kHz Core 1 tick.
 *
 * Units are the caller's choice but must be consistent:
 *   position in "units", velocity in units/s, accel in units/s^2.
 * For the motion engine we use encoder substeps (256 = 1 encoder cycle).
 *
 * Integer/float hybrid: positions & velocities as float for smoothness of the
 * profile; cheap enough at 1 kHz on Cortex-M0+ for 4 axes.
 * ========================================================================== */

typedef enum {
    EVN_TRAJECTORY_TRAPEZOID = 0,
    EVN_TRAJECTORY_MINIMUM_JERK = 1,
} evn_trajectory_type_t;

typedef struct {
    /* constraints */
    float max_vel;      /* units/s (magnitude) */
    float max_accel;    /* units/s^2 (magnitude) */

    /* move endpoints */
    float start_pos;
    float target_pos;

    /* computed profile timing */
    float accel_time;   /* t1: end of accel phase */
    float coast_time;   /* t2: start of decel phase */
    float total_time;   /* t3: end of move */
    float peak_vel;     /* signed peak velocity actually reached */
    float dir;          /* +1 / -1 */

    /* progress */
    float t;            /* elapsed seconds since move start */
    evn_trajectory_type_t type;
    bool  active;
    bool  done;
} evn_trajectory_t;

/* Start a trapezoidal move from `start` to `target` (units), subject to
 * max_vel / max_accel. Computes the profile timing up front. */
void evn_trajectory_start(evn_trajectory_t *tr, float start, float target,
                          float max_vel, float max_accel);
void evn_trajectory_start_type(evn_trajectory_t *tr, float start, float target,
                               float max_vel, float max_accel,
                               evn_trajectory_type_t type);

/* Evaluate the reference at the current internal time and advance by dt.
 * Outputs position/velocity/acceleration references. */
void evn_trajectory_update(evn_trajectory_t *tr, float dt,
                           float *pos_ref, float *vel_ref, float *accel_ref);

/* Advance (never rewind) a trapezoid to the time corresponding to position.
 * Used only by the startup reference governor after physical breakaway. */
void evn_trajectory_advance_to_position(evn_trajectory_t *tr, float position);

bool evn_trajectory_active(const evn_trajectory_t *tr);
bool evn_trajectory_done(const evn_trajectory_t *tr);

#endif /* MOTION_TRAJECTORY_H */
