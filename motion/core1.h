#ifndef MOTION_CORE1_H
#define MOTION_CORE1_H

#include <stdint.h>
#include <stdbool.h>

/* ==========================================================================
 * Core 1 real-time control skeleton — deterministic 1 kHz loop.
 *
 * Core 1 owns the time-critical path (encoder service now; the Phase 7 motion
 * engine later). The loop is driven by a Core-1-owned hardware alarm so the
 * period is clock-accurate; each tick is measured with the RP2040 hardware
 * microsecond timer. Sub-microsecond proof requires an external logic analyzer.
 *
 * Core 1 never printf()s or touches I2C/UART hardware — it publishes a
 * lock-free status block that Core 0 reads and prints on demand.
 * ========================================================================== */

#define EVN_CORE1_LOOP_HZ   1000u
#define EVN_CORE1_PERIOD_US (1000000u / EVN_CORE1_LOOP_HZ)

/* Lock-free status published by Core 1, read by Core 0. seq is odd while a
 * write is in progress (seqlock-style; readers retry on odd/changed seq). */
typedef struct {
    volatile uint32_t seq;
    volatile uint32_t tick_count;        /* total 1 kHz ticks */
    volatile int32_t  period_jitter_us;  /* last tick: actual - target (µs) */
    volatile uint32_t period_min_us;     /* min observed period (µs) */
    volatile uint32_t period_max_us;     /* max observed period (µs, jitter peak) */
    volatile uint32_t exec_max_us;       /* worst-case loop-body cost (µs) */
    volatile uint32_t tick_rate_milli_hz;/* measured loop rate ×1000 */
    volatile uint32_t missed_tick_count; /* deadlines skipped before ISR re-arm */
} evn_core1_status_t;

/* Launch Core 1 and start the 1 kHz loop. Call once from Core 0 main, after
 * bench_cycles_init(). Safe to call before other Core 0 services start. */
void evn_core1_start(void);

/* Core 0: snapshot the Core 1 status into *out (lock-free, retries on torn
 * read). Returns true on a clean read. */
bool evn_core1_get_status(evn_core1_status_t *out);

/* Core 0: reset the min/max/rate statistics (e.g. after a settle period). */
void evn_core1_reset_stats(void);

/* The Core 1 loop body. Phase 1: encoder service. Phase 7 will add the
 * trajectory→PID→observer pipeline here. Marked not-in-flash (0-wait SRAM)
 * per spec §4 execution-determinism requirement. */
void evn_core1_tick(void);

#endif /* MOTION_CORE1_H */
