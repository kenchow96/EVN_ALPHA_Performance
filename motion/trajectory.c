#include "trajectory.h"

#include <math.h>

/* Trapezoidal and quintic minimum-jerk point-to-point profiles. */

void evn_trajectory_start(evn_trajectory_t *tr, float start, float target,
                          float max_vel, float max_accel) {
    evn_trajectory_start_type(tr, start, target, max_vel, max_accel,
                              EVN_TRAJECTORY_TRAPEZOID);
}

void evn_trajectory_start_type(evn_trajectory_t *tr, float start, float target,
                               float max_vel, float max_accel,
                               evn_trajectory_type_t type) {
    tr->max_vel = max_vel;
    tr->max_accel = max_accel;
    tr->start_pos = start;
    tr->target_pos = target;
    tr->type = type;

    float dist = target - start;
    tr->dir = (dist >= 0.0f) ? 1.0f : -1.0f;
    float d = fabsf(dist);

    if (d < 1e-6f || max_vel <= 0.0f || max_accel <= 0.0f) {
        tr->active = false;
        tr->done = true;
        tr->t = 0.0f;
        tr->accel_time = tr->coast_time = tr->total_time = 0.0f;
        tr->peak_vel = 0.0f;
        return;
    }

    if (type == EVN_TRAJECTORY_MINIMUM_JERK) {
        /* s(u)=10u^3-15u^4+6u^5. Its normalized peak velocity is
         * 1.875 and peak acceleration is 10/sqrt(3). */
        float velocity_time = 1.875f * d / max_vel;
        float accel_time = sqrtf(5.773502692f * d / max_accel);
        tr->total_time = velocity_time > accel_time ? velocity_time : accel_time;
        tr->accel_time = 0.5f * tr->total_time;
        tr->coast_time = tr->accel_time;
        tr->peak_vel = 1.875f * d / tr->total_time;
        tr->t = 0.0f;
        tr->active = true;
        tr->done = false;
        return;
    }

    /* time to reach max_vel */
    float t_acc = max_vel / max_accel;
    /* distance covered during accel + decel at max_vel */
    float d_acc = max_accel * t_acc * t_acc;   /* = max_vel^2 / max_accel (both phases) */

    if (d >= d_acc) {
        /* trapezoid: reaches max_vel */
        float d_coast = d - d_acc;
        tr->accel_time = t_acc;
        tr->coast_time = t_acc + d_coast / max_vel;
        tr->total_time = tr->coast_time + t_acc;
        tr->peak_vel = max_vel;
    } else {
        /* triangle: never reaches max_vel */
        float t_pk = sqrtf(d / max_accel);   /* time to peak */
        tr->accel_time = t_pk;
        tr->coast_time = t_pk;
        tr->total_time = 2.0f * t_pk;
        tr->peak_vel = max_accel * t_pk;
    }

    tr->t = 0.0f;
    tr->active = true;
    tr->done = false;
}

void evn_trajectory_update(evn_trajectory_t *tr, float dt,
                           float *pos_ref, float *vel_ref, float *accel_ref) {
    if (!tr->active) {
        *pos_ref = tr->target_pos;
        *vel_ref = 0.0f;
        *accel_ref = 0.0f;
        return;
    }

    float t = tr->t;
    float a = tr->max_accel * tr->dir;
    float v_pk = tr->peak_vel * tr->dir;
    float d = tr->target_pos - tr->start_pos;

    float p, v, acc;

    if (tr->type == EVN_TRAJECTORY_MINIMUM_JERK && t < tr->total_time) {
        float u = t / tr->total_time;
        float u2 = u * u;
        float u3 = u2 * u;
        float u4 = u3 * u;
        float u5 = u4 * u;
        float inv_time = 1.0f / tr->total_time;
        p = tr->start_pos + d * (10.0f * u3 - 15.0f * u4 + 6.0f * u5);
        v = d * inv_time * (30.0f * u2 - 60.0f * u3 + 30.0f * u4);
        acc = d * inv_time * inv_time * (60.0f * u - 180.0f * u2 + 120.0f * u3);
    } else if (tr->type == EVN_TRAJECTORY_MINIMUM_JERK) {
        acc = 0.0f;
        v = 0.0f;
        p = tr->target_pos;
        tr->active = false;
        tr->done = true;
    } else if (t < tr->accel_time) {
        /* accelerating */
        acc = a;
        v = a * t;
        p = tr->start_pos + 0.5f * a * t * t;
    } else if (t < tr->coast_time) {
        /* constant velocity */
        acc = 0.0f;
        v = v_pk;
        float t1 = tr->accel_time;
        p = tr->start_pos + 0.5f * a * t1 * t1 + v_pk * (t - t1);
    } else if (t < tr->total_time) {
        /* decelerating */
        float td = t - tr->coast_time;
        acc = -a;
        v = v_pk - a * td;
        float t1 = tr->accel_time;
        float p_coast_start = tr->start_pos + 0.5f * a * t1 * t1 + v_pk * (tr->coast_time - t1);
        p = p_coast_start + v_pk * td - 0.5f * a * td * td;
    } else {
        /* finished */
        acc = 0.0f;
        v = 0.0f;
        p = tr->target_pos;
        tr->active = false;
        tr->done = true;
    }

    /* clamp position to not overshoot the target */
    if ((tr->dir > 0.0f && p > tr->target_pos) || (tr->dir < 0.0f && p < tr->target_pos)) {
        p = tr->target_pos;
    }

    *pos_ref = p;
    *vel_ref = v;
    *accel_ref = acc;

    tr->t += dt;
}

bool evn_trajectory_active(const evn_trajectory_t *tr) { return tr->active; }
bool evn_trajectory_done(const evn_trajectory_t *tr)   { return tr->done; }
