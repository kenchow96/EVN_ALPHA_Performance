#include "core1.h"

#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "hardware/timer.h"
#include "hardware/irq.h"

#include "../bench/bench_cycles.h"
#include "../hal/hal_encoder.h"

/* --------------------------------------------------------------------------
 * Core 1 runs a deterministic 1 kHz loop driven by a hardware-timer repeating
 * alarm. The alarm ISR sets a volatile flag; the Core 1 main loop runs the
 * body and measures period jitter with the DWT cycle counter (5 ns resolution).
 *
 * The ISR does the absolute minimum (set flag + re-arm) so the body can be
 * measured cleanly and later extended with the Phase 7 motion pipeline.
 * -------------------------------------------------------------------------- */

static volatile bool     s_tick_flag = false;
static evn_core1_status_t s_status;
static volatile bool     s_reset_req = false;   /* Core 0 → Core 1 reset request */

/* Alarm ISR (runs on Core 1, the core that armed it). Re-arm + flag only. */
static int64_t __not_in_flash_func(core1_alarm_isr)(alarm_id_t id, void *ud) {
    (void)id; (void)ud;
    s_tick_flag = true;
    return EVN_CORE1_PERIOD_US;   /* repeat after 1 ms (hardware-timed) */
}

/* The Core 1 1 kHz loop body. Phase 1: encoder service. The motion engine
 * (trajectory → cascaded PID → observer) plugs in here in Phase 7.
 * __not_in_flash_func per spec §4 (0-wait SRAM, no flash-cache stalls). */
void __not_in_flash_func(evn_core1_tick)(void) {
    hal_encoder_service();
    /* Phase 7: trajectory_update(); pid_update(); observer_update(); */
}

static void __not_in_flash_func(core1_main)(void) {
    /* NOTE: bench_cycles_init() is done ONCE on Core 0 (CYCCNT is a shared
     * resource). Calling it again here would reset the counter mid-run and
     * corrupt period measurement. */

    const uint32_t target_us = EVN_CORE1_PERIOD_US;   /* 1000 µs */

    /* stats owned exclusively by Core 1; init here */
    s_status.seq = 0;
    s_status.tick_count = 0;
    s_status.period_min_us = 0xFFFFFFFFu;
    s_status.period_max_us = 0;
    s_status.exec_max_us = 0;
    s_status.period_jitter_us = 0;
    s_status.tick_rate_milli_hz = 0;

    /* prime: discard the first (arbitrary) period */
    bool have_period = false;
    uint64_t last_us = bench_now_us();
    add_alarm_in_us(EVN_CORE1_PERIOD_US, core1_alarm_isr, NULL, true);

    while (true) {
        if (!s_tick_flag) { tight_loop_contents(); continue; }
        s_tick_flag = false;

        /* Core-1-owned stats reset (requested from Core 0) */
        if (s_reset_req) {
            s_reset_req = false;
            s_status.period_min_us = 0xFFFFFFFFu;
            s_status.period_max_us = 0;
            s_status.exec_max_us = 0;
            s_status.tick_count = 0;
            have_period = false;
        }

        uint64_t now_us = bench_now_us();
        uint32_t period = (uint32_t)(now_us - last_us);
        last_us = now_us;

        uint32_t t0 = bench_now_us32();
        evn_core1_tick();
        uint32_t exec = bench_now_us32() - t0;

        /* publish (seqlock: odd = writing) */
        s_status.seq++;
        __dmb();
        s_status.tick_count++;
        if (have_period && period > 0) {
            s_status.period_jitter_us = (int32_t)period - (int32_t)target_us;
            if (period < s_status.period_min_us) s_status.period_min_us = period;
            if (period > s_status.period_max_us) s_status.period_max_us = period;
            if (exec > s_status.exec_max_us) s_status.exec_max_us = exec;
            s_status.tick_rate_milli_hz = 1000000u / period;   /* mHz */
        }
        __dmb();
        s_status.seq++;
        have_period = true;
    }
}

void evn_core1_start(void) {
    multicore_launch_core1(core1_main);
}

bool evn_core1_get_status(evn_core1_status_t *out) {
    uint32_t s0, s1;
    do {
        s0 = s_status.seq;
        if (s0 & 1u) continue;
        __dmb();
        *out = *(evn_core1_status_t *)&s_status;
        __dmb();
        s1 = s_status.seq;
    } while (s0 != s1 || (s0 & 1u));
    return true;
}

void evn_core1_reset_stats(void) {
    s_reset_req = true;   /* consumed on the Core 1 loop (single owner) */
}
