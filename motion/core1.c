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
    bench_cycles_init();                 /* enable DWT on Core 1 */

    /* stats init */
    s_status.seq = 0;
    s_status.tick_count = 0;
    s_status.period_min_us = 0xFFFFFFFFu;
    s_status.period_max_us = 0;

    /* prime: schedule first tick 1 ms out */
    uint32_t last_cyc = bench_cycles_now();
    add_alarm_in_us(EVN_CORE1_PERIOD_US, core1_alarm_isr, NULL, true);

    const uint32_t target_cycles = 200000u;   /* 200 MHz / 1 kHz */

    while (true) {
        if (!s_tick_flag) { tight_loop_contents(); continue; }
        s_tick_flag = false;

        uint32_t now_cyc = bench_cycles_now();
        uint32_t period  = now_cyc - last_cyc;
        last_cyc = now_cyc;

        uint32_t t0 = bench_cycles_now();
        evn_core1_tick();
        uint32_t exec = bench_cycles_now() - t0;

        /* publish (seqlock: odd = writing) */
        s_status.seq++;
        __dmb();
        s_status.tick_count++;
        int32_t jitter = (int32_t)period - (int32_t)target_cycles;
        s_status.period_jitter_us = jitter / 200;         /* cycles → µs */
        uint32_t per_us = period / 200u;
        if (per_us < s_status.period_min_us) s_status.period_min_us = per_us;
        if (per_us > s_status.period_max_us) s_status.period_max_us = per_us;
        if (exec > s_status.exec_max_cycles) s_status.exec_max_cycles = exec;
        __dmb();
        s_status.seq++;

        /* recompute measured rate each tick: 1e9 / period_cycles milli-Hz */
        if (period) s_status.tick_rate_milli_hz = 1000000000u / period;
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
    s_status.period_min_us = 0xFFFFFFFFu;
    s_status.period_max_us = 0;
    s_status.exec_max_cycles = 0;
    s_status.tick_count = 0;
}
