#include "hal_tuning_log.h"

#include <string.h>

#include "hardware/flash.h"
#include "hardware/regs/addressmap.h"
#include "hardware/sync.h"
#include "pico/multicore.h"
#include "pico/platform.h"

_Static_assert(sizeof(evn_tuning_superblock_t) == EVN_TUNING_PAGE_SIZE,
               "tuning superblock must fill one flash page");
_Static_assert(sizeof(evn_tuning_record_header_t) == EVN_TUNING_PAGE_SIZE,
               "tuning record header must fill one flash page");
_Static_assert(EVN_TUNING_FLASH_BASE_OFFSET % FLASH_SECTOR_SIZE == 0,
               "tuning base must be sector aligned");
_Static_assert(EVN_TUNING_SLOT_SIZE % FLASH_SECTOR_SIZE == 0,
               "tuning slot must be sector aligned");
_Static_assert(EVN_TUNING_FLASH_BASE_OFFSET + EVN_TUNING_SUPERBLOCK_SIZE +
                   EVN_TUNING_CASE_COUNT * EVN_TUNING_SLOT_SIZE <=
               EVN_TUNING_FLASH_LIMIT_OFFSET,
               "tuning slots overlap persistent calibration flash");

extern uint8_t __flash_binary_end;

static uint32_t slot_offset(uint32_t case_index) {
    return EVN_TUNING_FLASH_BASE_OFFSET + EVN_TUNING_SUPERBLOCK_SIZE +
           case_index * EVN_TUNING_SLOT_SIZE;
}

static bool flash_layout_safe(void) {
    uintptr_t binary_end = (uintptr_t)&__flash_binary_end;
    return binary_end < XIP_BASE + EVN_TUNING_FLASH_BASE_OFFSET;
}

static bool __not_in_flash_func(safe_erase)(uint32_t offset, size_t count) {
    if (!multicore_lockout_ready()) return false;
    multicore_lockout_start_blocking();
    uint32_t interrupts = save_and_disable_interrupts();
    flash_range_erase(offset, count);
    restore_interrupts(interrupts);
    multicore_lockout_end_blocking();
    return true;
}

static bool __not_in_flash_func(safe_program)(uint32_t offset,
                                               const uint8_t *data,
                                               size_t count) {
    if (!multicore_lockout_ready()) return false;
    multicore_lockout_start_blocking();
    uint32_t interrupts = save_and_disable_interrupts();
    flash_range_program(offset, data, count);
    restore_interrupts(interrupts);
    multicore_lockout_end_blocking();
    return true;
}

uint32_t hal_tuning_log_crc32(uint32_t crc, const void *data, size_t length) {
    const uint8_t *bytes = (const uint8_t *)data;
    crc = ~crc;
    for (size_t index = 0; index < length; index++) {
        crc ^= bytes[index];
        for (uint32_t bit = 0; bit < 8; bit++)
            crc = (crc >> 1) ^ (0xEDB88320u & (uint32_t)-(int32_t)(crc & 1u));
    }
    return ~crc;
}

static bool superblock_valid(const evn_tuning_superblock_t *superblock,
                             uint32_t run_id) {
    if (superblock->magic != EVN_TUNING_SUPER_MAGIC ||
        superblock->schema_version != EVN_TUNING_SCHEMA_VERSION ||
        superblock->run_id != run_id ||
        superblock->case_count != EVN_TUNING_CASE_COUNT ||
        superblock->flash_base_offset != EVN_TUNING_FLASH_BASE_OFFSET ||
        superblock->slot_size != EVN_TUNING_SLOT_SIZE)
        return false;
    evn_tuning_superblock_t copy = *superblock;
    uint32_t expected = copy.crc32;
    copy.crc32 = 0;
    return hal_tuning_log_crc32(0, &copy, sizeof copy) == expected;
}

bool hal_tuning_log_begin(uint32_t run_id) {
    if (!flash_layout_safe()) return false;
    const evn_tuning_superblock_t *stored =
        (const evn_tuning_superblock_t *)(XIP_BASE + EVN_TUNING_FLASH_BASE_OFFSET);
    if (superblock_valid(stored, run_id)) return true;

    evn_tuning_superblock_t superblock;
    memset(&superblock, 0xFF, sizeof superblock);
    superblock.magic = EVN_TUNING_SUPER_MAGIC;
    superblock.schema_version = EVN_TUNING_SCHEMA_VERSION;
    superblock.run_id = run_id;
    superblock.case_count = EVN_TUNING_CASE_COUNT;
    superblock.flash_base_offset = EVN_TUNING_FLASH_BASE_OFFSET;
    superblock.slot_size = EVN_TUNING_SLOT_SIZE;
    superblock.crc32 = 0;
    superblock.crc32 = hal_tuning_log_crc32(0, &superblock, sizeof superblock);

    return safe_erase(EVN_TUNING_FLASH_BASE_OFFSET, EVN_TUNING_SUPERBLOCK_SIZE) &&
           safe_program(EVN_TUNING_FLASH_BASE_OFFSET,
                        (const uint8_t *)&superblock, sizeof superblock);
}

bool hal_tuning_log_case_header(uint32_t case_index, uint32_t run_id,
                                evn_tuning_record_header_t *out) {
    if (!out || case_index >= EVN_TUNING_CASE_COUNT) return false;
    const evn_tuning_record_header_t *stored =
        (const evn_tuning_record_header_t *)(XIP_BASE + slot_offset(case_index));
    evn_tuning_record_header_t header = *stored;
    uint32_t expected = header.header_crc32;
    header.header_crc32 = 0;
    if (header.magic != EVN_TUNING_RECORD_MAGIC ||
        header.schema_version != EVN_TUNING_SCHEMA_VERSION ||
        header.run_id != run_id || header.case_index != case_index ||
        header.trace_rows > EVN_TUNING_MAX_TRACE_ROWS ||
        hal_tuning_log_crc32(0, &header, sizeof header) != expected)
        return false;
    *out = *stored;
    return true;
}

bool hal_tuning_log_erase_case(uint32_t case_index) {
    if (case_index >= EVN_TUNING_CASE_COUNT || !flash_layout_safe()) return false;
    return safe_erase(slot_offset(case_index), EVN_TUNING_SLOT_SIZE);
}

bool hal_tuning_log_program_trace(uint32_t case_index, const void *data,
                                  uint32_t rows) {
    if (!data || case_index >= EVN_TUNING_CASE_COUNT || rows == 0 ||
        rows > EVN_TUNING_MAX_TRACE_ROWS)
        return false;
    size_t bytes = rows * EVN_TUNING_TRACE_ROW_BYTES;
    size_t program_bytes = (bytes + EVN_TUNING_PAGE_SIZE - 1u) &
                           ~(EVN_TUNING_PAGE_SIZE - 1u);
    if (program_bytes > EVN_TUNING_SLOT_SIZE - EVN_TUNING_HEADER_SIZE)
        return false;
    return safe_program(slot_offset(case_index) + EVN_TUNING_HEADER_SIZE,
                        (const uint8_t *)data, program_bytes);
}

bool hal_tuning_log_commit_case(uint32_t case_index,
                                const evn_tuning_record_header_t *header) {
    if (!header || case_index >= EVN_TUNING_CASE_COUNT ||
        header->case_index != case_index ||
        header->trace_rows > EVN_TUNING_MAX_TRACE_ROWS)
        return false;
    evn_tuning_record_header_t committed = *header;
    committed.magic = EVN_TUNING_RECORD_MAGIC;
    committed.schema_version = EVN_TUNING_SCHEMA_VERSION;
    committed.header_crc32 = 0;
    committed.header_crc32 = hal_tuning_log_crc32(0, &committed, sizeof committed);
    return safe_program(slot_offset(case_index), (const uint8_t *)&committed,
                        sizeof committed);
}
