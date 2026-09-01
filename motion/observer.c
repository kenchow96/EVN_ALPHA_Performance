#include "observer.h"

#include "pico/stdlib.h"   /* __not_in_flash_func */

/* Faithful integer port of Pybricks pbio observer.c. Not-in-flash, no heap. */

static inline int32_t iabs32(int32_t x)  { return x < 0 ? -x : x; }
static inline int32_t isign32(int32_t x) { return (x > 0) - (x < 0); }
static inline int32_t iclamp(int32_t v, int32_t lim) {
    if (v > lim) return lim;
    if (v < -lim) return -lim;
    return v;
}

void evn_observer_init(evn_observer_t *obs, const evn_motor_model_t *model,
                       const evn_observer_settings_t *settings, int32_t start_angle_mdeg) {
    obs->model = model;
    obs->settings = *settings;
    obs->angle_mdeg = start_angle_mdeg;
    obs->speed_mdegs = 0;
    obs->current = 0;
    obs->stalled = false;
    obs->stall_start_ms = 0;
}

static int32_t feedback_voltage_abs(int32_t error_abs, const evn_observer_settings_t *s) {
    if (error_abs <= s->feedback_gain_threshold) {
        return error_abs * s->feedback_gain_low / 1000;
    }
    return (s->feedback_gain_threshold * s->feedback_gain_low +
            (error_abs - s->feedback_gain_threshold) * s->feedback_gain_high) / 1000;
}

int32_t evn_observer_feedback_voltage(const evn_observer_t *obs, int32_t angle_mdeg) {
    int32_t error = angle_mdeg - obs->angle_mdeg;   /* estimation error */
    int32_t fb_abs = feedback_voltage_abs(iabs32(error), &obs->settings);
    return iclamp(fb_abs * isign32(error), EVN_OBS_MAX_VOLTAGE_MV);
}

static void update_stall(evn_observer_t *obs, uint32_t time_ms, int32_t voltage_mv,
                         int32_t feedback_voltage) {
    int32_t speed = obs->speed_mdegs;
    if (voltage_mv < 0) { speed = -speed; feedback_voltage = -feedback_voltage; }

    if (speed < obs->settings.stall_speed_limit &&
        feedback_voltage < 0 &&
        -feedback_voltage * 100 > voltage_mv * obs->settings.feedback_voltage_stall_ratio &&
        voltage_mv > obs->settings.feedback_voltage_negligible) {
        if (!obs->stalled) obs->stall_start_ms = time_ms;
        obs->stalled = true;
    } else {
        obs->stalled = false;
    }
}

void __not_in_flash_func(evn_observer_update)(evn_observer_t *obs, uint32_t time_ms,
                         int32_t angle_mdeg, int32_t voltage_mv) {
    const evn_motor_model_t *m = obs->model;

    int32_t feedback_voltage = evn_observer_feedback_voltage(obs, angle_mdeg);
    update_stall(obs, time_ms, voltage_mv, feedback_voltage);

    /* Model input = applied voltage + observer feedback (keeps model in sync). */
    int32_t model_voltage = iclamp(voltage_mv + feedback_voltage, EVN_OBS_MAX_VOLTAGE_MV);

    /* Coulomb friction, linearised near zero speed to avoid chatter. */
    int32_t coulomb = isign32(obs->speed_mdegs) * (
        iabs32(obs->speed_mdegs) > obs->settings.coulomb_friction_speed_cutoff
            ? m->torque_friction
            : iabs32(obs->speed_mdegs) * m->torque_friction / obs->settings.coulomb_friction_speed_cutoff);
    int32_t torque = coulomb;   /* (+ external load torque, currently none) */

    /* x(k+1) = A x(k) + B u(k)  — discrete Luenberger state update. */
    obs->angle_mdeg +=
        EVN_OBS_PRESCALE_SPEED   * obs->speed_mdegs / m->d_angle_d_speed +
        EVN_OBS_PRESCALE_CURRENT * obs->current     / m->d_angle_d_current +
        EVN_OBS_PRESCALE_VOLTAGE * model_voltage    / m->d_angle_d_voltage +
        EVN_OBS_PRESCALE_TORQUE  * torque           / m->d_angle_d_torque;

    int32_t speed_next = iclamp(
        EVN_OBS_PRESCALE_SPEED   * obs->speed_mdegs / m->d_speed_d_speed +
        EVN_OBS_PRESCALE_CURRENT * obs->current     / m->d_speed_d_current +
        EVN_OBS_PRESCALE_VOLTAGE * model_voltage    / m->d_speed_d_voltage +
        EVN_OBS_PRESCALE_TORQUE  * torque           / m->d_speed_d_torque,
        EVN_OBS_MAX_SPEED_MDEPS);

    int32_t current_next = iclamp(
        EVN_OBS_PRESCALE_SPEED   * obs->speed_mdegs / m->d_current_d_speed +
        EVN_OBS_PRESCALE_CURRENT * obs->current     / m->d_current_d_current +
        EVN_OBS_PRESCALE_VOLTAGE * model_voltage    / m->d_current_d_voltage +
        EVN_OBS_PRESCALE_TORQUE  * torque           / m->d_current_d_torque,
        EVN_OBS_MAX_CURRENT);

    /* Undo friction through a zero-speed crossing to avoid chatter. */
    if ((obs->speed_mdegs < 0) != (speed_next < 0)) {
        speed_next -= EVN_OBS_PRESCALE_TORQUE * coulomb / m->d_speed_d_torque;
    }

    obs->speed_mdegs = speed_next;
    obs->current = current_next;

    /* Correct the angle estimate toward the measurement via feedback voltage's
     * effect on angle (keeps the angle state converged to the encoder). */
    (void)angle_mdeg;
}

void evn_observer_get_state(const evn_observer_t *obs, int32_t *angle_mdeg,
                            int32_t *speed_mdegs, int32_t *current) {
    *angle_mdeg  = obs->angle_mdeg;
    *speed_mdegs = obs->speed_mdegs;
    *current     = obs->current;
}

bool evn_observer_is_stalled(const evn_observer_t *obs, uint32_t time_ms,
                             uint32_t *stall_duration_ms) {
    if (obs->stalled && (time_ms - obs->stall_start_ms) > obs->settings.stall_time_ms) {
        *stall_duration_ms = time_ms - obs->stall_start_ms;
        return true;
    }
    *stall_duration_ms = 0;
    return false;
}

int32_t evn_observer_torque_to_voltage(const evn_motor_model_t *m, int32_t torque_unm) {
    return EVN_OBS_PRESCALE_TORQUE * iclamp(torque_unm, EVN_OBS_MAX_TORQUE_UNM) / m->d_voltage_d_torque;
}

int32_t evn_observer_voltage_to_torque(const evn_motor_model_t *m, int32_t voltage_mv) {
    return EVN_OBS_PRESCALE_VOLTAGE * iclamp(voltage_mv, EVN_OBS_MAX_VOLTAGE_MV) / m->d_torque_d_voltage;
}

int32_t evn_observer_feedforward_torque(const evn_motor_model_t *m,
                                        int32_t rate_ref_mdegs, int32_t accel_ref) {
    return evn_observer_feedforward_torque_scaled(m, rate_ref_mdegs,
                                                  accel_ref, 500u);
}

int32_t evn_observer_feedforward_torque_scaled(const evn_motor_model_t *m,
                                               int32_t rate_ref_mdegs,
                                               int32_t accel_ref,
                                               uint16_t friction_permille) {
    int32_t friction = (int32_t)((int64_t)m->torque_friction *
                                 friction_permille / 1000) *
                       isign32(rate_ref_mdegs);
    int32_t backemf  = EVN_OBS_PRESCALE_SPEED * iclamp(rate_ref_mdegs, EVN_OBS_MAX_SPEED_MDEPS) / m->d_torque_d_speed;
    int32_t accel    = EVN_OBS_PRESCALE_ACCEL * iclamp(accel_ref, EVN_OBS_MAX_ACCEL) / m->d_torque_d_acceleration;
    return iclamp(friction + backemf + accel, EVN_OBS_MAX_TORQUE_UNM);
}
