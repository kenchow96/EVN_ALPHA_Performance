#include "motor_models.h"

/* Ported from Pybricks pbio servo_settings.c (EV3/NXT models).
 *
 * Motor specifications at 9V (from philohome.com/motors/motorcomp.htm):
 * ┌─────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
 * │ Motor           │ No-load  │ No-load  │ Stall    │ Stall    │ Rated    │
 * │                 │ Speed    │ Current  │ Torque   │ Current  │ Max Speed│
 * ├─────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
 * │ EV3 Large       │ 175 rpm  │ 60 mA    │ 43 N·cm  │ 1.8 A    │ 800 deg/s│
 * │ EV3 Medium      │ 260 rpm  │ 80 mA    │ 15 N·cm  │ 780 mA   │ 1200 deg/s│
 * │ NXT             │ 170 rpm  │ 60 mA    │ 50 N·cm  │ 2.0 A    │ 800 deg/s│
 * └─────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
 *
 * Conversions:
 *   175 rpm = 1050 deg/s (EV3 Large no-load)
 *   260 rpm = 1560 deg/s (EV3 Medium no-load)
 *   170 rpm = 1020 deg/s (NXT no-load)
 *   43 N·cm = 430 mN·m = 430,000 µN·m (EV3 Large stall torque)
 *   15 N·cm = 150 mN·m = 150,000 µN·m (EV3 Medium stall torque)
 *   50 N·cm = 500 mN·m = 500,000 µN·m (NXT stall torque)
 *
 * Pybricks rated_max_speed (from servo_settings.c):
 *   EV3 Large: 800 deg/s
 *   EV3 Medium: 1200 deg/s
 *   NXT: 800 deg/s
 */

static const evn_motor_model_t model_ev3_large = {
    .d_angle_d_speed = 88290,
    .d_speed_d_speed = 921,
    .d_current_d_speed = -61626,
    .d_angle_d_current = 5755278,
    .d_speed_d_current = 44574,
    .d_current_d_current = 21338185,
    .d_angle_d_voltage = 5240040,
    .d_speed_d_voltage = 21582,
    .d_current_d_voltage = 106130,
    .d_angle_d_torque = -1887437,
    .d_speed_d_torque = -9555,
    .d_current_d_torque = 861143,
    .d_voltage_d_torque = 107106,
    .d_torque_d_voltage = 3587,
    .d_torque_d_speed = 2083,
    .d_torque_d_acceleration = 1965,
    .torque_friction = 16476,
};

static const evn_motor_model_t model_ev3_medium = {
    .d_angle_d_speed = 89465,
    .d_speed_d_speed = 950,
    .d_current_d_speed = -197440,
    .d_angle_d_current = 1568301,
    .d_speed_d_current = 12886,
    .d_current_d_current = -5095199,
    .d_angle_d_voltage = 2220112,
    .d_speed_d_voltage = 9410,
    .d_current_d_voltage = 209263,
    .d_angle_d_torque = -399652,
    .d_speed_d_torque = -2034,
    .d_current_d_torque = 546357,
    .d_voltage_d_torque = 49219,
    .d_torque_d_voltage = 7806,
    .d_torque_d_speed = 7365,
    .d_torque_d_acceleration = 9355,
    .torque_friction = 24593,
};

static const evn_motor_model_t model_nxt = {
    .d_angle_d_speed = 88366,
    .d_speed_d_speed = 923,
    .d_current_d_speed = -60070,
    .d_angle_d_current = 5754836,
    .d_speed_d_current = 44630,
    .d_current_d_current = 27887153,
    .d_angle_d_voltage = 5236928,
    .d_speed_d_voltage = 21581,
    .d_current_d_voltage = 106485,
    .d_angle_d_torque = -2338784,
    .d_speed_d_torque = -11845,
    .d_current_d_torque = 1038248,
    .d_voltage_d_torque = 132663,
    .d_torque_d_voltage = 2896,
    .d_torque_d_speed = 1634,
    .d_torque_d_acceleration = 1587,
    .torque_friction = 20449,
};

static const evn_motor_model_t *const s_models[EVN_MOTOR_MODEL_COUNT] = {
    &model_ev3_large,
    &model_ev3_medium,
    &model_nxt,
};

static const char *const s_names[EVN_MOTOR_MODEL_COUNT] = {
    "EV3 Large",
    "EV3 Medium",
    "NXT",
};

const evn_motor_model_t *evn_motor_model_get(evn_motor_model_id_t id) {
    if (id < 0 || id >= EVN_MOTOR_MODEL_COUNT) return &model_ev3_medium;
    return s_models[id];
}

const char *evn_motor_model_name(evn_motor_model_id_t id) {
    if (id < 0 || id >= EVN_MOTOR_MODEL_COUNT) return "unknown";
    return s_names[id];
}
