#ifndef BENCH_CYCLES_H
#define BENCH_CYCLES_H

#include <stdint.h>
#include <stdbool.h>

/* ==========================================================================
 * bench_cycles — DWT CYCCNT cycle-count measurement harness.
 *
 * The RP2040's ARMv6-M DWT cycle counter runs at sysclk (200 MHz → 5 ns/count),
 * giving 5 ns resolution for jitter and execution-cost measurement. Zero heap,
 * safe from either core. Wraps every ~21 s; unsigned subtraction is wrap-safe.
 *
 * The SDK doesn't ship a DWT struct header, so we use the fixed ARMv6-M
 * addresses directly (architecture-defined, not board-specific).
 *
 *   bench_cycles_init();
 *   uint32_t t0 = bench_cycles_now();
 *   ... code under test ...
 *   uint32_t cycles = bench_cycles_now() - t0;
 * ========================================================================== */

/* ARMv6-M DWT registers (fixed addresses). */
#define EVN_DEMCR      (*(volatile uint32_t *)0xE000EDFCu)  /* Debug Exception & Monitor Ctrl */
#define EVN_DWT_CTRL   (*(volatile uint32_t *)0xE0001000u)  /* DWT Control */
#define EVN_DWT_CYCCNT (*(volatile uint32_t *)0xE0001004u)  /* Cycle counter */
#define EVN_DEMCR_TRCENA      (1u << 24)
#define EVN_DWT_CTRL_CYCCNTENA (1u << 0)

/* Enable the cycle counter. Idempotent. */
void bench_cycles_init(void);

/* cycles -> microseconds (uses measured sysclk). */
uint32_t bench_cycles_to_us(uint32_t cycles);

/* Running statistics for a periodic task's period or execution cost. */
typedef struct {
    uint32_t min_cycles;
    uint32_t max_cycles;
    uint64_t total_cycles;
    uint32_t samples;
} bench_stat_t;

void     bench_stat_reset(bench_stat_t *s);
void     bench_stat_add(bench_stat_t *s, uint32_t cycles);
uint32_t bench_stat_mean(const bench_stat_t *s);   /* 0 if no samples */

static inline uint32_t bench_cycles_now(void) { return EVN_DWT_CYCCNT; }

#endif /* BENCH_CYCLES_H */
