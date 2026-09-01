#include "pid.h"

void evn_pid_init(evn_pid_t *p) {
    /* Starting gains for EV3 motors, references in mdeg / mdeg/s, duty [-1,1].
     * Tuned so ~10 deg position error -> ~0.5 duty. */
    p->kp_pos = 5.0e-5f;     /* duty per mdeg error */
    p->ki_pos = 0.0f;
    p->kp_vel = 3.0e-6f;     /* duty per mdeg/s error */
    p->kd_vel = 0.0f;
    p->kff_accel = 0.0f;
    p->out_min = -1.0f;
    p->out_max =  1.0f;
    p->i_limit = 1.0e7f;
    p->vbus_comp = 0.0f;   /* disabled until calibrated */
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
