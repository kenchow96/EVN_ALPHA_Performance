#include "bench_cycles.h"

#include "pico/stdlib.h"
#include "hardware/clocks.h"

void bench_cycles_init(void) {
    EVN_DEMCR |= EVN_DEMCR_TRCENA;          /* enable trace unit */
    EVN_DWT_CYCCNT = 0;
    EVN_DWT_CTRL |= EVN_DWT_CTRL_CYCCNTENA; /* start cycle counter */
}

uint32_t bench_cycles_to_us(uint32_t cycles) {
    uint32_t per_us = (clock_get_hz(clk_sys) + 500000u) / 1000000u;
    return per_us ? (cycles / per_us) : 0u;
}

void bench_stat_reset(bench_stat_t *s) {
    s->min_cycles = 0xFFFFFFFFu;
    s->max_cycles = 0;
    s->total_cycles = 0;
    s->samples = 0;
}

void bench_stat_add(bench_stat_t *s, uint32_t cycles) {
    if (cycles < s->min_cycles) s->min_cycles = cycles;
    if (cycles > s->max_cycles) s->max_cycles = cycles;
    s->total_cycles += cycles;
    s->samples++;
}

uint32_t bench_stat_mean(const bench_stat_t *s) {
    return s->samples ? (uint32_t)(s->total_cycles / s->samples) : 0u;
}
