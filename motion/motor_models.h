#ifndef MOTION_MOTOR_MODELS_H
#define MOTION_MOTOR_MODELS_H

#include <stdint.h>

/* ==========================================================================
 * EVN ALPHA — Standard Peripheral Motor Models (Luenberger observer).
 *
 * "Standard peripherals" are motors EVN has characterised and can guarantee
 * maximum performance for. The model constants are ported from the Pybricks
 * pbio observer (lib/pbio/src/motor/servo_settings.c, BSD/MIT, (c) Pybricks /
 * LEGO), which were generated from experimental data (philohome.com motor
 * comparison + Pybricks measurements).
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
 * Units (Pybricks internal, integer math):
 *   angle  : millidegrees (mdeg)
 *   speed  : mdeg/s
 *   current: 0.1 mA (10000 = 1 A)
 *   torque : µN·m (1e6 = 1 N·m)
 *   voltage: mV
 *
 * The d_*_d_* fields are 5 ms discrete state-space gains used by the observer
 * (see motion/observer.c). Do not run them at another cadence without
 * regenerating the matrices. torque_friction is the Coulomb friction (µN·m).
 * ========================================================================== */

typedef struct {
    int32_t d_angle_d_speed;
    int32_t d_speed_d_speed;
    int32_t d_current_d_speed;
    int32_t d_angle_d_current;
    int32_t d_speed_d_current;
    int32_t d_current_d_current;
    int32_t d_angle_d_voltage;
    int32_t d_speed_d_voltage;
    int32_t d_current_d_voltage;
    int32_t d_angle_d_torque;
    int32_t d_speed_d_torque;
    int32_t d_current_d_torque;
    int32_t d_voltage_d_torque;
    int32_t d_torque_d_voltage;
    int32_t d_torque_d_speed;
    int32_t d_torque_d_acceleration;
    int32_t torque_friction;
} evn_motor_model_t;

/* EVN standard peripherals. */
typedef enum {
    EVN_MOTOR_MODEL_EV3_LARGE = 0,
    EVN_MOTOR_MODEL_EV3_MEDIUM,
    EVN_MOTOR_MODEL_NXT,
    EVN_MOTOR_MODEL_COUNT
} evn_motor_model_id_t;

/* Get a motor model by id. */
const evn_motor_model_t *evn_motor_model_get(evn_motor_model_id_t id);

/* Human-readable name. */
const char *evn_motor_model_name(evn_motor_model_id_t id);

#endif /* MOTION_MOTOR_MODELS_H */
