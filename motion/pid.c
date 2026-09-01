#include "pid.h"

void evn_pid_init(evn_pid_t *p) {
    /* EV3 motors, references mdeg / mdeg/s, duty [-1,1]. Tuned to break
     * stiction and track: ~10 deg error -> near-full duty; velocity loop
     * tracks the trapezoid; small integral clears residual. */
    p->kp_pos = 8.0e-5f;     /* duty per mdeg (10 deg err -> 0.8 duty) */
    p->ki_pos = 1.0e-6f;     /* duty per (mdeg·s) integral */
    p->kp_vel = 1.0e-6f;     /* duty per mdeg/s error (180 deg/s -> 0.18 duty) */
    p->endpoint_kp_vel = 0.0f;
    p->kd_vel = 0.0f;
    p->kff_accel = 0.0f;
    p->out_min = -1.0f;
    p->out_max =  1.0f;
    p->i_limit = 0.20f;
    p->vbus_comp = 7400.0f;  /* regulate feedback voltage around nominal pack */
    p->use_enc_speed = 1;  /* velocity loop on true encoder speed */
    p->deadzone_mdeg = 400.0f;  /* 0.4 deg: hold without hunting on enc noise */
    p->min_duty = 0.12f;        /* stiction-break floor (12% duty) */
    p->start_duty = 0.12f;
    p->startup_release_speed_mdegs = 0.0f;
    p->startup_ramp_ticks = 200u;
    p->motion_stuck = false;
    p->vel_window = PID_SPEED_WINDOW;
    evn_pid_reset(p, 0.0f);
}

void evn_pid_reset(evn_pid_t *p, float initial_position) {
    p->integrator = 0.0f;
    p->prev_vel_meas = 0.0f;
    p->first = true;
    p->motion_start_position = initial_position;
    p->pos_hist_idx = 0;
    p->stick_ticks = 0;
    p->last_vel_smooth = 0.0f;
    for (int i = 0; i < PID_SPEED_WINDOW; i++) p->pos_hist[i] = initial_position;
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
    if (dt <= 0.0f) return 0.0f;
    /* the slot W back from the newest write */
    int back = (p->pos_hist_idx - W + PID_SPEED_WINDOW) % PID_SPEED_WINDOW;
    float oldest_pos = p->pos_hist[back];
    return (pos_meas - oldest_pos) / ((W - 1) * dt);
}

float evn_pid_update(evn_pid_t *p,
                     float pos_ref, float vel_ref, float accel_ref,
                     float pos_meas, float vel_meas, float dt,
                     float feedforward_duty, uint32_t vbus_mv) {
    if (dt <= 0.0f) return 0.0f;

    float pos_err = pos_ref - pos_meas;
    float ae = pos_err < 0.0f ? -pos_err : pos_err;
    bool in_deadzone = p->deadzone_mdeg > 0.0f && ae < p->deadzone_mdeg;

    /* velocity D on the (already windowed) measured speed — no derivative kick */
    float d_vel = 0.0f;
    if (!p->first) d_vel = -(vel_meas - p->prev_vel_meas) / dt;
    p->prev_vel_meas = vel_meas;
    p->first = false;

    /* velocity P uses the windowed speed passed in from the caller
     * (evn_pid_speed_of), so quantization noise doesn't bang the duty cycle */
    float vel_err_smooth = vel_ref - vel_meas;
    if (in_deadzone) vel_err_smooth = 0.0f;
    p->last_vel_smooth = vel_meas;
    float abs_vel_ref = vel_ref < 0.0f ? -vel_ref : vel_ref;

    float kp_vel = p->kp_vel;
    if (p->endpoint_kp_vel > kp_vel && abs_vel_ref < 5000.0f && ae < 5000.0f)
        kp_vel = p->endpoint_kp_vel;
    float feedback_no_i = p->kp_pos * pos_err
                        + kp_vel * vel_err_smooth
                        + p->kd_vel * d_vel
                        + p->kff_accel * accel_ref;

    float integral_limit = in_deadzone ? 0.15f * p->i_limit : p->i_limit;
    float integral_delta = p->ki_pos * pos_err * dt;
    float candidate_integral = p->integrator + integral_delta;
    if (candidate_integral > integral_limit) candidate_integral = integral_limit;
    if (candidate_integral < -integral_limit) candidate_integral = -integral_limit;

    /* battery-voltage compensation: scale duty so torque tracks the reference
     * regardless of pack voltage sag. duty_scaled = duty * V_nominal / V_now. */
    float voltage_scale = 1.0f;
    if (p->vbus_comp > 0.0f && vbus_mv > 0) {
        voltage_scale = p->vbus_comp / (float)vbus_mv;
    }

    float candidate_duty = (feedback_no_i + candidate_integral) * voltage_scale
                         + feedforward_duty;
    bool winds_up_high = candidate_duty > p->out_max && integral_delta > 0.0f;
    bool winds_up_low = candidate_duty < p->out_min && integral_delta < 0.0f;
    if (!winds_up_high && !winds_up_low) p->integrator = candidate_integral;

    float duty = (feedback_no_i + p->integrator) * voltage_scale
               + feedforward_duty;

    /* stiction break: only when the error has PERSISTED in the approach band for
     * ~30 ms (genuinely stuck). The integral term does the smooth final creep;
     * the floor just breaks static friction on a real stick, then fades. This
     * avoids a duty kick at the deadzone boundary (which caused a limit cycle). */
    float abs_speed = vel_meas < 0.0f ? -vel_meas : vel_meas;
    float displacement = pos_meas - p->motion_start_position;
    if (displacement < 0.0f) displacement = -displacement;
    bool initial_starting = abs_vel_ref > 5000.0f &&
                            (displacement < 100.0f ||
                             (p->startup_release_speed_mdegs > 0.0f &&
                              displacement < 5000.0f &&
                              abs_speed < p->startup_release_speed_mdegs));
    bool restarting = abs_vel_ref > 5000.0f && p->motion_stuck;
    bool starting = initial_starting || restarting;
    bool approaching = ae > p->deadzone_mdeg &&
                       abs_vel_ref < 5000.0f && abs_speed < 5000.0f;
    if (starting || approaching) {
        p->stick_ticks++;
    } else {
        p->stick_ticks = 0;
    }
    int threshold = starting ? 5 : 30;
    if (p->stick_ticks >= threshold) {
        int ramp_ticks = p->stick_ticks - threshold + 1;
        int ramp_duration = initial_starting ? p->startup_ramp_ticks :
                    (restarting ? 200 : 100);
        float ramp = (float)ramp_ticks / (float)ramp_duration;
        if (ramp > 1.0f) ramp = 1.0f;
        float floor_d = (starting ? p->start_duty : p->min_duty) * ramp;
        float abs_duty = duty < 0.0f ? -duty : duty;
        float direction = starting ? vel_ref : pos_err;
        if (floor_d > 0.0f && abs_duty < floor_d)
            duty = direction < 0.0f ? -floor_d : floor_d;
    }

    if (duty > p->out_max) duty = p->out_max;
    if (duty < p->out_min) duty = p->out_min;
    return duty;
}
