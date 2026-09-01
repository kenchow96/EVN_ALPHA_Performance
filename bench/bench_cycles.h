#ifndef BENCH_CYCLES_H
#define BENCH_CYCLES_H

#include <stdint.h>
#include <stdbool.h>

/* ==========================================================================
 * bench_cycles — high-resolution timing harness for RP2040.
 *
 * IMPORTANT (hardware fact): the RP2040's Cortex-M0+ does NOT implement the
 * optional DWT CYCCNT register — there is no on-chip cycle counter. The
 * highest-resolution timer available is the 64-bit microsecond TIMER
 * (time_us_64(), 1 µs resolution), which the SDK exposes and which runs from
 * a dedicated hardware timer (TIMER @ 0x40054000).
 *
 * Because the jitter target is < 1 µs, we measure loop period in microseconds
 * with time_us_64() (and time_us_32() for short deltas). A period reading of
 * exactly 1000 µs every tick = jitter < 1 µs (the resolution floor). This is
 * the validated RP2040 approach.
 *
 *   bench_init();
 *   uint64_t t0 = bench_now_us();
 *   ... work ...
 *   uint32_t us = (uint32_t)(bench_now_us() - t0);
 * ========================================================================== */

#include "pico/stdlib.h"   /* time_us_64 / time_us_32 */

void bench_init(void);

static inline uint64_t bench_now_us(void)   { return time_us_64(); }
static inline uint32_t bench_now_us32(void) { return time_us_32(); }

/* Running statistics (units: microseconds). */
typedef struct {
    uint32_t min_us;
    uint32_t max_us;
    uint64_t total_us;
    uint32_t samples;
} bench_stat_t;

void     bench_stat_reset(bench_stat_t *s);
void     bench_stat_add(bench_stat_t *s, uint32_t us);
uint32_t bench_stat_mean(const bench_stat_t *s);   /* 0 if no samples */

#endif /* BENCH_CYCLES_H */
