#include "pid.h"

void evn_pid_init(evn_pid_t *p) {
    /* EV3 motors, references mdeg / mdeg/s, duty [-1,1]. Tuned to break
     * stiction and track: ~10 deg error -> near-full duty; velocity loop
     * tracks the trapezoid; small integral clears residual. */
    p->kp_pos = 2.5e-4f;     /* duty per mdeg (10 deg err -> ~0.9 duty) */
    p->ki_pos = 1.0e-6f;     /* duty per (mdeg·s) integral */
    p->kp_vel = 1.0e-5f;     /* duty per mdeg/s error */
    p->kd_vel = 0.0f;
    p->kff_accel = 0.0f;
    p->out_min = -1.0f;
    p->out_max =  1.0f;
    p->i_limit = 5.0e6f;     /* anti-windup (mdeg·s) */
    p->vbus_comp = 0.0f;   /* disabled until calibrated */
    p->use_enc_speed = 1;  /* velocity loop on true encoder speed */
    p->deadzone_mdeg = 400.0f;  /* 0.4 deg: hold without hunting on enc noise */
    p->min_duty = 0.12f;        /* stiction-break floor (12% duty) */
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

    /* deadband: inside the position tolerance, keep integrating so the loop
     * can break stiction and reach the exact target, but drop the (noisy)
     * velocity-P term and cap the integrator so it can't wind up into a limit
     * cycle. Outside the deadzone, full control. */
    float ae = pos_err < 0.0f ? -pos_err : pos_err;
    if (p->deadzone_mdeg > 0.0f && ae < p->deadzone_mdeg) {
        p->integrator += pos_err * dt;
        float icap = 0.15f * p->i_limit;   /* small budget in the deadzone */
        if (p->integrator >  icap) p->integrator =  icap;
        if (p->integrator < -icap) p->integrator = -icap;
        vel_err = 0.0f;   /* suppress velocity chatter on encoder quantization */
    } else {
        /* integral with anti-windup clamp */
        p->integrator += pos_err * dt;
        if (p->integrator >  p->i_limit) p->integrator =  p->i_limit;
        if (p->integrator < -p->i_limit) p->integrator = -p->i_limit;
    }

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

    /* stiction break: a persistent error beyond the deadzone gets at least
     * min_duty in the correcting direction so friction can't stall convergence */
    if (p->min_duty > 0.0f && ae > p->deadzone_mdeg) {
        if (duty >= 0.0f && duty < p->min_duty) duty = p->min_duty;
        else if (duty < 0.0f && duty > -p->min_duty) duty = -p->min_duty;
    }

    if (duty > p->out_max) duty = p->out_max;
    if (duty < p->out_min) duty = p->out_min;
    return duty;
}
