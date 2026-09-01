#include "pid.h"

void evn_pid_init(evn_pid_t *p) {
    /* Conservative defaults; tuned per-motor later. Units are encoder substeps
     * (256 = 1 encoder cycle) for position/velocity, duty [-1,1] output. */
    p->kp_pos = 0.0008f;
    p->ki_pos = 0.0f;
    p->kp_vel = 0.00002f;
    p->kd_vel = 0.0f;
    p->kff_accel = 0.0f;
    p->out_min = -1.0f;
    p->out_max =  1.0f;
    p->i_limit = 100000.0f;
    p->vbus_comp = 0.0f;   /* 0 = disabled until we have a nominal voltage */
    evn_pid_reset(p);
}

void evn_pid_reset(evn_pid_t *p) {
    p->integrator = 0.0f;
    p->prev_vel_meas = 0.0f;
    p->first = true;
}

float evn_pid_update(evn_pid_t *p,
                     float pos_ref, float vel_ref, float accel_ref,
                     float pos_meas, float vel_meas, float dt,
                     uint32_t vbus_mv) {
    if (dt <= 0.0f) return 0.0f;

    float pos_err = pos_ref - pos_meas;
    float vel_err = vel_ref - vel_meas;

    /* integral with anti-windup clamp */
    p->integrator += pos_err * dt;
    if (p->integrator >  p->i_limit) p->integrator =  p->i_limit;
    if (p->integrator < -p->i_limit) p->integrator = -p->i_limit;

    /* velocity D on measurement (avoid derivative kick on reference steps) */
    float d_vel = 0.0f;
    if (!p->first) d_vel = -(vel_meas - p->prev_vel_meas) / dt;
    p->prev_vel_meas = vel_meas;
    p->first = false;

    float duty = p->kp_pos * pos_err
               + p->ki_pos * p->integrator
               + p->kp_vel * vel_err
               + p->kd_vel * d_vel
               + p->kff_accel * accel_ref;

    /* battery-voltage compensation: scale duty so torque tracks the reference
     * regardless of pack voltage sag. duty_scaled = duty * V_nominal / V_now. */
    if (p->vbus_comp > 0.0f && vbus_mv > 0) {
        duty *= (p->vbus_comp / (float)vbus_mv);
    }

    if (duty > p->out_max) duty = p->out_max;
    if (duty < p->out_min) duty = p->out_min;
    return duty;
}
