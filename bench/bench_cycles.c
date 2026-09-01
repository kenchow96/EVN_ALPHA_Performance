#include "bench_cycles.h"

void bench_init(void) {
    /* time_us_64()/time_us_32() are driven by the RP2040 hardware TIMER and
     * need no enabling. Present for symmetry/future-proofing. */
}

void bench_stat_reset(bench_stat_t *s) {
    s->min_us = 0xFFFFFFFFu;
    s->max_us = 0;
    s->total_us = 0;
    s->samples = 0;
}

void bench_stat_add(bench_stat_t *s, uint32_t us) {
    if (us < s->min_us) s->min_us = us;
    if (us > s->max_us) s->max_us = us;
    s->total_us += us;
    s->samples++;
}

uint32_t bench_stat_mean(const bench_stat_t *s) {
    return s->samples ? (uint32_t)(s->total_us / s->samples) : 0u;
}
