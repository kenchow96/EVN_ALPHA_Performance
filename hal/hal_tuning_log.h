#ifndef HAL_TUNING_LOG_H
#define HAL_TUNING_LOG_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/**
 * Run ID Format: 0xYYMMDDNN
 * - YY = Year (26 = 2026)
 * - MM = Month (09 = September)
 * - DD = Day (04 = 4th)
 * - NN = Sequence number for that day (2A, 2B, 2C... in hex)
 * 
 * Example: 0x2609042B = 2026-09-04, run #43 (0x2B = 43 decimal)
 * Increment for each autonomous run. Reusing a run ID causes firmware to skip completed cases.
 */
#define EVN_TUNING_RUN_ID             0x26090433u
#define EVN_TUNING_SCHEMA_VERSION     1u
#define EVN_TUNING_CASE_COUNT         16u
#define EVN_TUNING_FLASH_BASE_OFFSET  0x00F00000u
#define EVN_TUNING_FLASH_LIMIT_OFFSET 0x00FF0000u
#define EVN_TUNING_SUPERBLOCK_SIZE    0x00001000u
#define EVN_TUNING_SLOT_SIZE          0x0000E000u
#define EVN_TUNING_PAGE_SIZE          256u
#define EVN_TUNING_HEADER_SIZE        EVN_TUNING_PAGE_SIZE
#define EVN_TUNING_TRACE_ROW_BYTES    32u
#define EVN_TUNING_MAX_TRACE_ROWS \
    ((EVN_TUNING_SLOT_SIZE - EVN_TUNING_HEADER_SIZE) / EVN_TUNING_TRACE_ROW_BYTES)

#define EVN_TUNING_SUPER_MAGIC  0x31535645u
#define EVN_TUNING_RECORD_MAGIC 0x31525645u

typedef enum {
    EVN_TUNING_STATUS_COMPLETE = 1,
    EVN_TUNING_STATUS_BATTERY_ABORT = 2,
    EVN_TUNING_STATUS_INTERNAL_ERROR = 3,
} evn_tuning_status_t;

typedef struct {
    uint32_t magic;
    uint32_t schema_version;
    uint32_t run_id;
    uint32_t case_count;
    uint32_t flash_base_offset;
    uint32_t slot_size;
    uint32_t crc32;
    uint32_t reserved[57];
} evn_tuning_superblock_t;

typedef struct {
    uint32_t magic;
    uint32_t schema_version;
    uint32_t run_id;
    uint32_t case_index;
    uint32_t status;
    uint32_t trace_rows;
    uint32_t trace_crc32;
    uint32_t header_crc32;
    uint32_t axis;
    int32_t delta_mdeg;
    int32_t target_mdeg;
    uint32_t vmax_mdegs;
    uint32_t accel_mdegs2;
    float kp;
    float ki;
    float kv;
    float kd;
    float kff;
    float start_duty;
    float hold_duty;
    uint32_t speed_source;
    uint32_t speed_window;
    float speed_alpha;
    float vel_scale;
    float accel_scale;
    uint32_t battery_pack_mv;
    uint32_t battery_cell1_mv;
    uint32_t battery_cell2_mv;
    uint32_t battery_age_us;
    uint32_t core_tick_count;
    uint32_t core_period_min_us;
    uint32_t core_period_max_us;
    uint32_t core_exec_max_us;
    uint32_t core_missed_ticks;
    int32_t final_angle_mdeg;
    int32_t final_speed_mdegs;
    uint32_t motion_flags;
    uint32_t sample_div;
    uint32_t pwm_hz;
    uint32_t duration_us;
    uint32_t trajectory_type;
    uint32_t repeat_index;
    uint32_t startup_reference_governor;
    uint32_t friction_feedforward_permille;
    uint32_t startup_release_speed_mdegs;
    uint32_t edge_watchdog_enabled;
    float endpoint_kp_vel;
    uint32_t startup_ramp_ms;
    uint32_t restart_ramp_ms;
    uint32_t startup_pulse_on_ticks;
    uint32_t reserved[14];
} evn_tuning_record_header_t;

bool hal_tuning_log_begin(uint32_t run_id);
bool hal_tuning_log_case_header(uint32_t case_index, uint32_t run_id,
                                evn_tuning_record_header_t *out);
bool hal_tuning_log_erase_case(uint32_t case_index);
bool hal_tuning_log_program_trace(uint32_t case_index, const void *data,
                                  uint32_t rows);
bool hal_tuning_log_commit_case(uint32_t case_index,
                                const evn_tuning_record_header_t *header);
uint32_t hal_tuning_log_crc32(uint32_t crc, const void *data, size_t length);

#endif
