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
    p->vel_window = PID_SPEED_WINDOW;
    evn_pid_reset(p);
}

void evn_pid_reset(evn_pid_t *p) {
    p->integrator = 0.0f;
    p->prev_vel_meas = 0.0f;
    p->first = true;
    p->pos_hist_idx = 0;
    p->pos_hist_full = false;
    p->stick_ticks = 0;
    for (int i = 0; i < PID_SPEED_WINDOW; i++) p->pos_hist[i] = 0.0f;
}

/* Windowed speed estimate (Pybricks-style): push pos_meas into the ring buffer
 * and return the average rate over the window in mdeg/s. dt is the sample
 * period in seconds. Low-noise without the per-tick quantization spikes. */
float evn_pid_speed_of(evn_pid_t *p, float pos_meas, float dt) {
    int W = p->vel_window;
    if (W < 2) W = 2;
    if (W > PID_SPEED_WINDOW) W = PID_SPEED_WINDOW;
    p->pos_hist[p->pos_hist_idx] = pos_meas;
    p->pos_hist_idx = (p->pos_hist_idx + 1) % PID_SPEED_WINDOW;
    if (p->pos_hist_idx == 0) p->pos_hist_full = true;
    if (dt <= 0.0f) return 0.0f;
    /* the slot W back from the newest write */
    int back = (p->pos_hist_idx - W + PID_SPEED_WINDOW) % PID_SPEED_WINDOW;
    float oldest_pos = p->pos_hist[back];
    return (pos_meas - oldest_pos) / (W * dt);
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

    /* velocity D on the (already windowed) measured speed — no derivative kick */
    float d_vel = 0.0f;
    if (!p->first) d_vel = -(vel_meas - p->prev_vel_meas) / dt;
    p->prev_vel_meas = vel_meas;
    p->first = false;

    /* velocity P uses the windowed speed passed in from the caller
     * (evn_pid_speed_of), so quantization noise doesn't bang the duty cycle */
    float vel_err_smooth = vel_ref - vel_meas;
    if (p->deadzone_mdeg > 0.0f && ae < p->deadzone_mdeg) vel_err_smooth = 0.0f;
    p->last_vel_smooth = vel_meas;

    float duty = p->kp_pos * pos_err
               + p->ki_pos * p->integrator
               + p->kp_vel * vel_err_smooth
               + p->kd_vel * d_vel
               + p->kff_accel * accel_ref;

    /* battery-voltage compensation: scale duty so torque tracks the reference
     * regardless of pack voltage sag. duty_scaled = duty * V_nominal / V_now. */
    if (p->vbus_comp > 0.0f && vbus_mv > 0) {
        duty *= (p->vbus_comp / (float)vbus_mv);
    }

    /* stiction break: only when the error has PERSISTED in the approach band for
     * ~30 ms (genuinely stuck). The integral term does the smooth final creep;
     * the floor just breaks static friction on a real stick, then fades. This
     * avoids a duty kick at the deadzone boundary (which caused a limit cycle). */
    if (p->min_duty > 0.0f && ae > p->deadzone_mdeg) {
        if (ae < 3.0f * p->deadzone_mdeg) {   /* approach band */
            p->stick_ticks++;
        } else {
            p->stick_ticks = 0;               /* far away: no floor needed (P handles it) */
        }
        if (p->stick_ticks >= 30) {
            float floor_d = p->min_duty;
            if (duty >= 0.0f && duty < floor_d) duty = floor_d;
            else if (duty < 0.0f && duty > -floor_d) duty = -floor_d;
        }
    } else {
        p->stick_ticks = 0;
    }

    if (duty > p->out_max) duty = p->out_max;
    if (duty < p->out_min) duty = p->out_min;
    return duty;
}
