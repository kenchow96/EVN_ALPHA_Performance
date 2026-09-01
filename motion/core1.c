#include "core1.h"

#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "hardware/timer.h"
#include "hardware/irq.h"
#include "hardware/structs/timer.h"

#include "../bench/bench_cycles.h"
#include "../hal/hal_encoder.h"
#include "motion_engine.h"

/* --------------------------------------------------------------------------
 * Core 1 runs a deterministic 1 kHz loop driven by a hardware-timer repeating
 * alarm. The alarm ISR sets a volatile flag; the Core 1 main loop runs the
 * body and measures period jitter with the RP2040 microsecond timer.
 *
 * The ISR does the absolute minimum (set flag + re-arm) so the body can be
 * measured cleanly and later extended with the Phase 7 motion pipeline.
 * -------------------------------------------------------------------------- */

static volatile uint32_t s_tick_sequence = 0;
static volatile uint32_t s_missed_ticks = 0;
static uint32_t          s_next_alarm_us = 0;
static uint              s_alarm_num = 0;
static evn_core1_status_t s_status;
static volatile bool     s_reset_req = false;   /* Core 0 → Core 1 reset request */

/* Hardware-alarm callback installed on Core 1. Advance an absolute deadline so
 * callback latency cannot accumulate into long-term control-loop drift. */
static void __not_in_flash_func(core1_alarm_isr)(void) {
    uint32_t alarm_mask = 1u << s_alarm_num;
    timer_hw->intr = alarm_mask;

    uint32_t now_us = timer_hw->timerawl;
    do {
        s_next_alarm_us += EVN_CORE1_PERIOD_US;
        if ((int32_t)(s_next_alarm_us - now_us) <= 0) s_missed_ticks++;
    } while ((int32_t)(s_next_alarm_us - now_us) <= 0);

    timer_hw->alarm[s_alarm_num] = s_next_alarm_us;
    s_tick_sequence++;
}

/* The Core 1 1 kHz loop body. Phase 1: encoder service. Phase 7: motion engine.
 * __not_in_flash_func per spec §4 (0-wait SRAM, no flash-cache stalls). */
void __not_in_flash_func(evn_core1_tick)(void) {
    hal_encoder_service();
    evn_motion_tick();
}

static void __not_in_flash_func(core1_main)(void) {
    /* The hardware microsecond timer is shared and monotonic across cores. */

    const uint32_t target_us = EVN_CORE1_PERIOD_US;   /* 1000 µs */

    /* stats owned exclusively by Core 1; init here */
    s_status.seq = 0;
    s_status.tick_count = 0;
    s_status.period_min_us = 0xFFFFFFFFu;
    s_status.period_max_us = 0;
    s_status.exec_max_us = 0;
    s_status.period_jitter_us = 0;
    s_status.tick_rate_milli_hz = 0;
    s_status.missed_tick_count = 0;

    /* prime: discard the first (arbitrary) period */
    bool have_period = false;
    uint64_t last_us = bench_now_us();
    uint32_t processed_sequence = s_tick_sequence;
    s_alarm_num = (uint)hardware_alarm_claim_unused(true);
    uint alarm_irq = TIMER_IRQ_0 + s_alarm_num;
    uint32_t alarm_mask = 1u << s_alarm_num;
    irq_set_exclusive_handler(alarm_irq, core1_alarm_isr);
    irq_set_priority(alarm_irq, PICO_HIGHEST_IRQ_PRIORITY);
    timer_hw->intr = alarm_mask;
    hw_set_bits(&timer_hw->inte, alarm_mask);
    irq_set_enabled(alarm_irq, true);
    s_next_alarm_us = time_us_32() + EVN_CORE1_PERIOD_US;
    timer_hw->alarm[s_alarm_num] = s_next_alarm_us;

    while (true) {
        uint32_t pending_sequence = s_tick_sequence;
        if (processed_sequence == pending_sequence) { tight_loop_contents(); continue; }
        processed_sequence++;

        /* Core-1-owned stats reset (requested from Core 0) */
        if (s_reset_req) {
            s_reset_req = false;
            s_status.period_min_us = 0xFFFFFFFFu;
            s_status.period_max_us = 0;
            s_status.exec_max_us = 0;
            s_status.tick_count = 0;
            s_missed_ticks = 0;
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
            s_status.tick_rate_milli_hz = 1000000000u / period;
        }
        s_status.missed_tick_count = s_missed_ticks;
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
