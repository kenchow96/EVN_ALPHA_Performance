#include "autonomous_tuning.h"

#include <string.h>

#include "pico/bootrom.h"
#include "pico/stdlib.h"

#include "../hal/hal_battery.h"
#include "../hal/hal_motor.h"
#include "../hal/hal_tuning_log.h"
#include "../motion/core1.h"
#include "../motion/motion_engine.h"

#ifndef EVN_AUTONOMOUS_TUNING
#define EVN_AUTONOMOUS_TUNING 0
#endif

#define TUNING_AXIS                 2u
#define TUNING_TRACE_US             3800000ULL
#define TUNING_BATTERY_WAIT_US      2000000ULL
#define TUNING_BATTERY_MAX_AGE_US   250000u
#define TUNING_BATTERY_MIN_PACK_MV  6500u
#define TUNING_BATTERY_MIN_CELL_MV  3000u
#define TUNING_FLASH_SETTLE_US      20000ULL
#define TUNING_CORE_PAUSE_TIMEOUT_US 10000u

typedef struct {
    evn_trajectory_type_t trajectory_type;
    bool startup_reference_governor;
    uint16_t friction_feedforward_permille;
    uint32_t startup_release_speed_mdegs;
    bool edge_watchdog_enabled;
    float endpoint_kp_vel;
    uint16_t startup_ramp_ms;
    uint16_t restart_ramp_ms;
    float start_duty;
    uint8_t repeat_index;
    float delta;
} tuning_case_t;

typedef enum {
    AUTO_DISABLED,
    AUTO_LOG_BEGIN,
    AUTO_FIND_CASE,
    AUTO_ERASE_CASE,
    AUTO_RESET_STATS,
    AUTO_WAIT_BATTERY,
    AUTO_RUN_MOTION,
    AUTO_CAPTURE,
    AUTO_WRITE_TRACE,
    AUTO_COMMIT,
    AUTO_FINISH,
} auto_state_t;

static const tuning_case_t s_cases[EVN_TUNING_CASE_COUNT] = {
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f,  800, 200, 0.65f, 0,  90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f,  800, 200, 0.65f, 0, -90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f, 1200, 200, 0.65f, 0,  90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f, 1200, 200, 0.65f, 0, -90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f,  800, 400, 0.65f, 0,  90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f,  800, 400, 0.65f, 0, -90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f, 1200, 400, 0.65f, 0,  90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f, 1200, 400, 0.65f, 0, -90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f,  800, 200, 0.65f, 1,  90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f,  800, 200, 0.65f, 1, -90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f, 1200, 200, 0.65f, 1,  90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f, 1200, 200, 0.65f, 1, -90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f,  800, 400, 0.65f, 1,  90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f,  800, 400, 0.65f, 1, -90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f, 1200, 400, 0.65f, 1,  90.0f},
    {EVN_TRAJECTORY_TRAPEZOID, true, 500, 10000, true, 0.5e-6f, 1200, 400, 0.65f, 1, -90.0f},
};

static auto_state_t s_state = AUTO_DISABLED;
static uint32_t s_case_index;
static uint32_t s_trace_row;
static uint32_t s_trace_crc;
static uint64_t s_deadline_us;
static evn_battery_state_t s_battery;
static evn_tuning_record_header_t s_header;
static uint8_t s_page[EVN_TUNING_PAGE_SIZE];

static void coast_all(void) {
    for (uint8_t axis = 0; axis < EVN_MOTOR_COUNT; axis++) evn_motion_coast(axis);
    hal_motor_coast_all();
}

static void finish(void) {
    coast_all();
    s_state = AUTO_FINISH;
    s_deadline_us = time_us_64() + 100000ULL;
}

static void prepare_header(evn_tuning_status_t status) {
    const tuning_case_t *test = &s_cases[s_case_index];
    memset(&s_header, 0, sizeof s_header);
    s_header.run_id = EVN_TUNING_RUN_ID;
    s_header.case_index = s_case_index;
    s_header.status = status;
    s_header.axis = TUNING_AXIS + 1u;
    s_header.delta_mdeg = (int32_t)(test->delta * 1000.0f);
    s_header.vmax_mdegs = 180000u;
    s_header.accel_mdegs2 = 900000u;
    s_header.kp = 1.2e-4f;
    s_header.ki = 8.0e-7f;
    s_header.kv = 5.0e-7f;
    s_header.start_duty = test->start_duty;
    s_header.hold_duty = 0.55f;
    s_header.speed_source = 1u;
    s_header.speed_window = 40u;
    s_header.speed_alpha = 0.05f;
    s_header.vel_scale = 0.85f;
    s_header.accel_scale = 0.40f;
    s_header.sample_div = EVN_TRACE_SAMPLE_DIV;
    s_header.pwm_hz = hal_motor_get_pwm_freq();
    s_header.trajectory_type = test->trajectory_type;
    s_header.repeat_index = test->repeat_index;
    s_header.startup_reference_governor = test->startup_reference_governor;
    s_header.friction_feedforward_permille =
        test->friction_feedforward_permille;
    s_header.startup_release_speed_mdegs =
        test->startup_release_speed_mdegs;
    s_header.edge_watchdog_enabled = test->edge_watchdog_enabled;
    s_header.endpoint_kp_vel = test->endpoint_kp_vel;
    s_header.startup_ramp_ms = test->startup_ramp_ms;
    s_header.restart_ramp_ms = test->restart_ramp_ms;
}

static void snapshot_battery(uint32_t age_us) {
    s_header.battery_pack_mv = s_battery.vbatt_mv;
    s_header.battery_cell1_mv = s_battery.vcell1_mv;
    s_header.battery_cell2_mv = s_battery.vcell2_mv;
    s_header.battery_age_us = age_us;
}

static void snapshot_motion(uint64_t started_us) {
    uint8_t axis;
    uint32_t rows;
    bool armed;
    evn_motion_trace_info(&axis, &rows, &armed);
    if (rows > EVN_TUNING_MAX_TRACE_ROWS) rows = EVN_TUNING_MAX_TRACE_ROWS;
    s_header.trace_rows = rows;
    float angle, speed;
    bool stalled, done;
    evn_motion_get_state(TUNING_AXIS, &angle, &speed, &stalled, &done);
    s_header.final_angle_mdeg = (int32_t)(angle * 1000.0f);
    s_header.final_speed_mdegs = (int32_t)(speed * 1000.0f);
    s_header.motion_flags = (done ? 1u : 0u) | (stalled ? 2u : 0u) |
                            (armed ? 4u : 0u);
    float target, duration;
    evn_motion_get_debug(TUNING_AXIS, &target, &duration);
    s_header.target_mdeg = (int32_t)(target * 1000.0f);
    s_header.duration_us = (uint32_t)(duration * 1000000.0f);
    (void)started_us;
    evn_core1_status_t core;
    if (evn_core1_get_status(&core)) {
        s_header.core_tick_count = core.tick_count;
        s_header.core_period_min_us = core.period_min_us;
        s_header.core_period_max_us = core.period_max_us;
        s_header.core_exec_max_us = core.exec_max_us;
        s_header.core_missed_ticks = core.missed_tick_count;
    }
}

static bool battery_ready(uint32_t *age_us) {
    if (!hal_battery_get(&s_battery)) return false;
    *age_us = time_us_32() - s_battery.timestamp_us;
    return *age_us <= TUNING_BATTERY_MAX_AGE_US;
}

static bool battery_safe(void) {
    return s_battery.vbatt_mv >= TUNING_BATTERY_MIN_PACK_MV &&
           s_battery.vcell1_mv >= TUNING_BATTERY_MIN_CELL_MV &&
           s_battery.vcell2_mv >= TUNING_BATTERY_MIN_CELL_MV;
}

static bool build_trace_page(void) {
    if (s_trace_row >= s_header.trace_rows) return false;
    memset(s_page, 0xFF, sizeof s_page);
    uint32_t rows = s_header.trace_rows - s_trace_row;
    if (rows > EVN_TUNING_PAGE_SIZE / EVN_TUNING_TRACE_ROW_BYTES)
        rows = EVN_TUNING_PAGE_SIZE / EVN_TUNING_TRACE_ROW_BYTES;
    int32_t *words = (int32_t *)s_page;
    for (uint32_t row = 0; row < rows; row++) {
        int32_t *dst = &words[row * 8u];
        if (!evn_motion_trace_row(s_trace_row + row, &dst[0], &dst[1], &dst[2],
                                  &dst[3], &dst[4], &dst[5], &dst[6], &dst[7]))
            return false;
    }
    s_trace_crc = hal_tuning_log_crc32(s_trace_crc, s_page,
                                       rows * EVN_TUNING_TRACE_ROW_BYTES);
    s_trace_row += rows;
    return true;
}

void autonomous_tuning_init(void) {
#if EVN_AUTONOMOUS_TUNING
    coast_all();
    s_case_index = 0;
    s_deadline_us = time_us_64() + TUNING_BATTERY_WAIT_US;
    s_state = AUTO_LOG_BEGIN;
#else
    s_state = AUTO_DISABLED;
#endif
}

bool autonomous_tuning_active(void) {
    return s_state != AUTO_DISABLED;
}

void autonomous_tuning_service(void) {
    if (s_state == AUTO_DISABLED) return;
    uint64_t now = time_us_64();

    switch (s_state) {
    case AUTO_LOG_BEGIN:
        coast_all();
        if (evn_core1_pause(TUNING_CORE_PAUSE_TIMEOUT_US)) {
            bool logged = hal_tuning_log_begin(EVN_TUNING_RUN_ID);
            bool resumed = evn_core1_resume(TUNING_CORE_PAUSE_TIMEOUT_US);
            if (logged && resumed) s_state = AUTO_FIND_CASE;
            else finish();
        } else if ((int64_t)(now - s_deadline_us) >= 0) {
            finish();
        }
        break;

    case AUTO_FIND_CASE: {
        evn_tuning_record_header_t existing;
        while (s_case_index < EVN_TUNING_CASE_COUNT &&
               hal_tuning_log_case_header(s_case_index, EVN_TUNING_RUN_ID, &existing) &&
               existing.status == EVN_TUNING_STATUS_COMPLETE)
            s_case_index++;
        if (s_case_index >= EVN_TUNING_CASE_COUNT) finish();
        else s_state = AUTO_ERASE_CASE;
        break;
    }

    case AUTO_ERASE_CASE:
        coast_all();
        if (!evn_core1_pause(TUNING_CORE_PAUSE_TIMEOUT_US)) {
            finish();
            break;
        }
        bool erased = hal_tuning_log_erase_case(s_case_index);
        bool resumed = evn_core1_resume(TUNING_CORE_PAUSE_TIMEOUT_US);
        if (!erased || !resumed) {
            finish();
            break;
        }
        evn_core1_reset_stats();
        s_deadline_us = now + TUNING_FLASH_SETTLE_US;
        s_state = AUTO_RESET_STATS;
        break;

    case AUTO_RESET_STATS:
        if ((int64_t)(now - s_deadline_us) >= 0) {
            s_deadline_us = now + TUNING_BATTERY_WAIT_US;
            s_state = AUTO_WAIT_BATTERY;
        }
        break;

    case AUTO_WAIT_BATTERY: {
        uint32_t age_us = 0;
        if (battery_ready(&age_us)) {
            prepare_header(battery_safe() ? EVN_TUNING_STATUS_COMPLETE :
                                           EVN_TUNING_STATUS_BATTERY_ABORT);
            snapshot_battery(age_us);
            if (!battery_safe()) {
                s_state = AUTO_COMMIT;
                break;
            }
            s_state = AUTO_RUN_MOTION;
        } else if ((int64_t)(now - s_deadline_us) >= 0) {
            prepare_header(EVN_TUNING_STATUS_BATTERY_ABORT);
            s_state = AUTO_COMMIT;
        }
        break;
    }

    case AUTO_RUN_MOTION: {
        const tuning_case_t *test = &s_cases[s_case_index];
        evn_motion_set_velocity_source(TUNING_AXIS, 1);
        evn_motion_set_speed_window(TUNING_AXIS, 40);
        evn_motion_set_edge_speed_alpha(TUNING_AXIS, 0.05f);
        evn_motion_set_profile_scale(TUNING_AXIS, 0.85f, 0.40f);
        evn_motion_set_trajectory_type(TUNING_AXIS, test->trajectory_type);
        evn_motion_set_startup_reference_governor(
            TUNING_AXIS, test->startup_reference_governor);
        evn_motion_set_friction_feedforward(
            TUNING_AXIS, test->friction_feedforward_permille);
        evn_motion_set_startup_release_speed(
            TUNING_AXIS, test->startup_release_speed_mdegs / 1000.0f);
        evn_motion_set_edge_watchdog(TUNING_AXIS, test->edge_watchdog_enabled);
        evn_motion_set_endpoint_velocity_gain(TUNING_AXIS, test->endpoint_kp_vel);
        evn_motion_set_startup_ramp_ms(TUNING_AXIS, test->startup_ramp_ms);
        evn_motion_set_restart_ramp_ms(TUNING_AXIS, test->restart_ramp_ms);
        evn_motion_set_gains_axis(TUNING_AXIS, 1.2e-4f, 8.0e-7f,
                      5.0e-7f, 0.0f, 0.0f);
        evn_motion_set_stiction(TUNING_AXIS, test->start_duty, 0.55f);
        float angle, speed;
        bool stalled, done;
        evn_motion_get_state(TUNING_AXIS, &angle, &speed, &stalled, &done);
        evn_motion_trace_arm(TUNING_AXIS);
        evn_motion_move_to_test(TUNING_AXIS, angle + test->delta,
                                180.0f, 900.0f, 4000u);
        s_deadline_us = now + TUNING_TRACE_US;
        s_state = AUTO_CAPTURE;
        break;
    }

    case AUTO_CAPTURE:
        if ((int64_t)(now - s_deadline_us) >= 0) {
            evn_motion_trace_stop();
            coast_all();
            snapshot_motion(now - TUNING_TRACE_US);
            if (s_header.core_missed_ticks != 0)
                s_header.status = EVN_TUNING_STATUS_INTERNAL_ERROR;
            if (s_header.trace_rows == 0) {
                s_header.status = EVN_TUNING_STATUS_INTERNAL_ERROR;
                s_state = AUTO_COMMIT;
            } else {
                s_trace_row = 0;
                s_trace_crc = 0;
                if (evn_core1_pause(TUNING_CORE_PAUSE_TIMEOUT_US))
                    s_state = AUTO_WRITE_TRACE;
                else
                    finish();
            }
        }
        break;

    case AUTO_WRITE_TRACE:
        coast_all();
        if (!build_trace_page() ||
            !hal_tuning_log_program_trace_page(
                s_case_index, 1u + (s_trace_row - 1u) /
                                  (EVN_TUNING_PAGE_SIZE / EVN_TUNING_TRACE_ROW_BYTES),
                s_page)) {
            s_header.status = EVN_TUNING_STATUS_INTERNAL_ERROR;
            s_header.trace_rows = 0;
            s_trace_crc = 0;
            s_state = AUTO_COMMIT;
            break;
        }
        if (s_trace_row >= s_header.trace_rows) {
            s_header.trace_crc32 = s_trace_crc;
            s_state = AUTO_COMMIT;
        }
        break;

    case AUTO_COMMIT:
        coast_all();
        if (!evn_core1_is_paused() &&
            !evn_core1_pause(TUNING_CORE_PAUSE_TIMEOUT_US)) {
            finish();
            break;
        }
        bool committed = hal_tuning_log_commit_case(s_case_index, &s_header);
        bool core_resumed = evn_core1_resume(TUNING_CORE_PAUSE_TIMEOUT_US);
        if (!committed || !core_resumed) {
            finish();
            break;
        }
        if (s_header.status != EVN_TUNING_STATUS_COMPLETE) {
            finish();
            break;
        }
        s_case_index++;
        s_state = AUTO_FIND_CASE;
        break;

    case AUTO_FINISH:
        coast_all();
        if ((int64_t)(now - s_deadline_us) >= 0) reset_usb_boot(0, 0);
        break;

    default:
        finish();
        break;
    }
}
