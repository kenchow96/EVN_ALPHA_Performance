#ifndef MOTION_OBSERVER_H
#define MOTION_OBSERVER_H

#include <stdint.h>
#include <stdbool.h>

#include "motor_models.h"

/* ==========================================================================
 * EVN ALPHA — Luenberger motor state observer.
 *
 * Faithful integer-math port of the Pybricks pbio observer (lib/pbio/src/
 * observer.c, BSD/MIT). Estimates angle, speed, and current from the applied
 * voltage and the measured encoder angle, and detects sensorless stalls from
 * the model/reality divergence (feedback voltage).
 *
 * All math is fixed-point integer (no floats on the 1 kHz RT path). Units are
 * the Pybricks internal units (see motor_models.h).
 *
 * The 1 kHz Core 1 controller advances this 5 ms discrete model every fifth
 * tick using mean applied voltage. Zero heap, not-in-flash.
 * ========================================================================== */

/* Prescale constants + numeric bounds (from pbio observer.c — do not change;
 * they are coupled to the model constants). */
#define EVN_OBS_MAX_SPEED_MDEPS   2500000
#define EVN_OBS_MAX_ACCEL         25000000
#define EVN_OBS_MAX_CURRENT       30000
#define EVN_OBS_MAX_VOLTAGE_MV    12000
#define EVN_OBS_MAX_TORQUE_UNM    1000000

#define EVN_OBS_PRESCALE_SPEED    858
#define EVN_OBS_PRESCALE_ACCEL    85
#define EVN_OBS_PRESCALE_CURRENT  71582
#define EVN_OBS_PRESCALE_VOLTAGE  178956
#define EVN_OBS_PRESCALE_TORQUE   2147

/* Configurable observer behaviour (per-motor). */
typedef struct {
    int32_t  stall_speed_limit;             /* mdeg/s below which stall may flag */
    uint32_t stall_time_ms;                 /* min sustained stall before flag */
    int32_t  feedback_voltage_negligible;   /* mV below which no stall info */
    int32_t  feedback_voltage_stall_ratio;  /* 0-100: stall threshold ratio */
    int32_t  feedback_gain_low;             /* mV/deg for small errors */
    int32_t  feedback_gain_high;            /* mV/deg for large errors */
    int32_t  feedback_gain_threshold;       /* mdeg error to switch gain */
    int32_t  coulomb_friction_speed_cutoff; /* mdeg/s friction linearisation */
} evn_observer_settings_t;

typedef struct {
    const evn_motor_model_t *model;
    evn_observer_settings_t settings;

    /* state estimates */
    int32_t angle_mdeg;    /* estimated angle */
    int32_t speed_mdegs;   /* estimated speed */
    int32_t current;       /* estimated current (0.1 mA) */

    /* stall state */
    bool     stalled;
    uint32_t stall_start_ms;
} evn_observer_t;

void evn_observer_init(evn_observer_t *obs, const evn_motor_model_t *model,
                       const evn_observer_settings_t *settings, int32_t start_angle_mdeg);

/* Advance the observer one control step. time_ms = wall clock; angle_mdeg =
 * measured encoder angle; voltage_mv = applied motor voltage (signed). */
void evn_observer_update(evn_observer_t *obs, uint32_t time_ms,
                         int32_t angle_mdeg, int32_t voltage_mv);

/* Estimated state. */
void evn_observer_get_state(const evn_observer_t *obs, int32_t *angle_mdeg,
                            int32_t *speed_mdegs, int32_t *current);

/* Sensorless stall: true if stalled >= stall_time. stall_duration_ms out. */
bool evn_observer_is_stalled(const evn_observer_t *obs, uint32_t time_ms,
                             uint32_t *stall_duration_ms);

/* Feedback voltage keeping the model synced to measurement (mV). Public so
 * the controller can use it as the load/disturbance signal. */
int32_t evn_observer_feedback_voltage(const evn_observer_t *obs, int32_t angle_mdeg);

/* Model conversions (torque in µN·m, voltage in mV). */
int32_t evn_observer_torque_to_voltage(const evn_motor_model_t *m, int32_t torque_unm);
int32_t evn_observer_voltage_to_torque(const evn_motor_model_t *m, int32_t voltage_mv);

/* Feedforward torque for a reference speed+acceleration (µN·m). */
int32_t evn_observer_feedforward_torque(const evn_motor_model_t *m,
                                        int32_t rate_ref_mdegs, int32_t accel_ref);

#endif /* MOTION_OBSERVER_H */
