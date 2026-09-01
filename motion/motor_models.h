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
 * Units (Pybricks internal, integer math):
 *   angle  : millidegrees (mdeg)
 *   speed  : mdeg/s
 *   current: 0.1 mA (10000 = 1 A)
 *   torque : µN·m (1e6 = 1 N·m)
 *   voltage: mV
 *
 * The d_*_d_* fields are the discrete state-space gains used by the observer
 * (see motion/observer.c). torque_friction is the Coulomb friction (µN·m).
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
