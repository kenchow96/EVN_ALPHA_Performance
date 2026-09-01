#include "hal_encoder.h"

#include <string.h>
#include "pico/stdlib.h"
#include "hardware/pio.h"
#include "hardware/gpio.h"
#include "hardware/clocks.h"
#include "hardware/sync.h"

#include "quadrature.pio.h"   /* generated: evn_quad_substep */

/* --------------------------------------------------------------------------
 * Encoder pin/base map (ground truth — Hardware Reference §5).
 * PIO needs consecutive A/B pins with A at the IN/JMP base. For motors where
 * B is the lower pin (M2/M4) we run the PIO from the B pin as base and apply
 * a runtime sign-flip so "forward" stays consistent.
 * -------------------------------------------------------------------------- */
#define ENC_PIO pio0

typedef struct {
    uint8_t base_pin;
    int8_t  sign;      /* default direction polarity */
} enc_hw_t;

static const enc_hw_t s_hw[4] = {
    { 18, +1 },   /* M1: A=18 B=19 */
    { 16, -1 },   /* M2: A=17 B=16 (B lower → flipped) */
    { 14, +1 },   /* M3: A=14 B=15 */
    { 12, -1 },   /* M4: A=13 B=12 (B lower → flipped) */
};

/* --- substep state (ported from pico-examples quadrature_encoder_substep) -- */
typedef struct {
    uint calibration_data[4];
    uint clocks_per_us;
    uint idle_stop_samples;
    uint sm;

    uint prev_trans_pos, prev_trans_us;
    uint prev_step_us;
    uint prev_low, prev_high;
    uint idle_stop_sample_count;
    int  speed_2_20;
    int  stopped;

    int  speed;      /* substeps / second */
    uint position;   /* substeps (256 = 4 hardware steps = 1 cycle) */
    uint raw_step;   /* integer step count */
} substep_t;

static substep_t s_enc[4];
/* Runtime sign overrides. Defaults: M1/M3 +1 (A lower), M2/M4 -1 (B lower).
 * Per-installation direction/mounting tuning via the 's' serial command.
 * NOTE: port 2 motor showed a runaway not fixed by sign/dir flips — suspected
 * hardware (encoder/leads on port 2); see docs/ASSUMPTIONS.md C3. */
static int8_t    s_sign[4] = { +1, -1, +1, -1 };
static uint8_t   s_populated = 0;
static bool      s_loaded = false;

/* Idle decimation: a stopped encoder is fully re-estimated only every Nth
 * service call; between those we just peek whether raw_step changed. */
#define ENC_IDLE_DECIMATION 20u   /* 1 kHz service → 50 Hz when stopped */
static uint8_t s_idle_div[4];

/* --- low-level PIO helpers (ported) --- */

static void substep_program_init(uint sm, uint pin) {
    uint pin_state, position, ints;

    pio_gpio_init(ENC_PIO, pin);
    pio_gpio_init(ENC_PIO, pin + 1);
    pio_sm_set_consecutive_pindirs(ENC_PIO, sm, pin, 2, false);
    gpio_pull_up(pin);
    gpio_pull_up(pin + 1);

    pio_sm_config c = evn_quad_substep_program_get_default_config(0);
    sm_config_set_in_pins(&c, pin);
    sm_config_set_in_shift(&c, false, true, 32);    /* left, autopush @32 */
    sm_config_set_out_shift(&c, true, false, 32);
    sm_config_set_fifo_join(&c, PIO_FIFO_JOIN_NONE);
    sm_config_set_clkdiv(&c, 1.0f);                  /* full sysclk resolution */
    pio_sm_init(ENC_PIO, sm, 0, &c);

    /* STATUS := (rx_fifo level < 1) so "MOV PC, ~STATUS" pushes only with room */
    ENC_PIO->sm[sm].execctrl = (ENC_PIO->sm[sm].execctrl & 0xFFFFFF80u) | 0x12u;

    ints = save_and_disable_interrupts();
    pin_state = (gpio_get_all() >> pin) & 3u;
    pio_sm_exec(ENC_PIO, sm, pio_encode_set(pio_y, ~pin_state));
    pio_sm_exec(ENC_PIO, sm, pio_encode_mov(pio_osr, pio_y));
    switch (pin_state) {
        case 0: position = 0; break;
        case 1: position = 3; break;
        case 2: position = 1; break;
        default: position = 2; break;
    }
    pio_sm_exec(ENC_PIO, sm, pio_encode_set(pio_y, position));
    pio_sm_set_enabled(ENC_PIO, sm, true);
    restore_interrupts(ints);
}

static void substep_get_counts(uint sm, uint *step, int *cycles, uint *us) {
    int i, pairs;
    pairs = pio_sm_get_rx_fifo_level(ENC_PIO, sm) >> 1;
    for (i = 0; i < pairs + 1; i++) {
        *cycles = (int)pio_sm_get_blocking(ENC_PIO, sm);
        *step   = pio_sm_get_blocking(ENC_PIO, sm);
    }
    *us = time_us_32();
}

/* --- speed/position estimation (ported) --- */

static uint step_start_pos(substep_t *s, uint step) {
    return ((step << 6) & 0xFFFFFF00u) | s->calibration_data[step & 3u];
}

static int calc_speed(int delta_substep, int delta_us) {
    return (int)(((int64_t)delta_substep << 20) / delta_us);
}

static void read_pio(substep_t *s, uint *step, uint *step_us, uint *trans_us, int *fwd) {
    int cycles;
    substep_get_counts(s->sm, step, &cycles, step_us);
    if (cycles < 0) { cycles = -cycles; *fwd = 1; }
    else            { cycles = 0x80000000 - cycles; *fwd = 0; }
    *trans_us = *step_us - (uint)((cycles * 13) / (int)s->clocks_per_us);
}

static void substep_update(substep_t *s) {
    uint step, step_us, transition_us, transition_pos, low, high;
    int forward, speed_high, speed_low;

    read_pio(s, &step, &step_us, &transition_us, &forward);

    low  = step_start_pos(s, step);
    high = step_start_pos(s, step + 1);

    if (step == s->raw_step) s->idle_stop_sample_count++;
    else                     s->idle_stop_sample_count = 0;

    if (!s->stopped && s->idle_stop_sample_count >= s->idle_stop_samples) {
        s->speed = 0; s->speed_2_20 = 0; s->stopped = 1;
    }

    if (s->raw_step != step) {
        transition_pos = forward ? low : high;
        if (!s->stopped)
            s->speed_2_20 = calc_speed((int)(transition_pos - s->prev_trans_pos),
                                       (int)(transition_us - s->prev_trans_us));
        s->stopped = 0;
        s->prev_trans_pos = transition_pos;
        s->prev_trans_us  = transition_us;
    }

    if (!s->stopped) {
        if (s->prev_trans_us > s->prev_step_us &&
            (int)(s->prev_trans_us - s->prev_step_us) > (int)(step_us - s->prev_trans_us)) {
            speed_high = calc_speed((int)(s->prev_trans_pos - s->prev_low),
                                    (int)(s->prev_trans_us - s->prev_step_us));
            speed_low  = calc_speed((int)(s->prev_trans_pos - s->prev_high),
                                    (int)(s->prev_trans_us - s->prev_step_us));
        } else {
            speed_high = calc_speed((int)(high - s->prev_trans_pos),
                                    (int)(step_us - s->prev_trans_us));
            speed_low  = calc_speed((int)(low - s->prev_trans_pos),
                                    (int)(step_us - s->prev_trans_us));
        }
        if (s->speed_2_20 > speed_high) s->speed_2_20 = speed_high;
        if (s->speed_2_20 < speed_low)  s->speed_2_20 = speed_low;

        s->speed = (int)((s->speed_2_20 * 62500LL) >> 16);
        s->position = s->prev_trans_pos +
                      (uint)(((int64_t)s->speed_2_20 * (int)(step_us - transition_us)) >> 20);

        if ((int)(s->position - high) > 0)      s->position = high;
        else if ((int)(s->position - low) < 0)  s->position = low;
    }

    s->prev_low = low;
    s->prev_high = high;
    s->raw_step = step;
    s->prev_step_us = step_us;
}

/* --- public API --- */

bool hal_encoder_init_mask(uint8_t mask) {
    if (!s_loaded) {
        uint off = pio_add_program_at_offset(ENC_PIO, &evn_quad_substep_program, 0);
        if (off != 0) return false;   /* must load at origin 0 */
        s_loaded = true;
    }

    for (int i = 0; i < 4; i++) {
        if (!(mask & (1u << i))) continue;
        int sm = pio_claim_unused_sm(ENC_PIO, false);
        if (sm < 0) return false;

        substep_t *s = &s_enc[i];
        memset(s, 0, sizeof(*s));
        s->sm = (uint)sm;
        s->calibration_data[0] = 0;
        s->calibration_data[1] = 64;
        s->calibration_data[2] = 128;
        s->calibration_data[3] = 192;   /* balanced phases until calibrated */
        s->idle_stop_samples = 30;   /* 30 ms: span low-rate edges without stale endpoint speed */
        s->stopped = 1;
        s->clocks_per_us = (clock_get_hz(clk_sys) + 500000u) / 1000000u;

        substep_program_init((uint)sm, s_hw[i].base_pin);

        /* seed previous-state so the first update has a sane reference */
        int fwd;
        read_pio(s, &s->raw_step, &s->prev_step_us, &s->prev_trans_us, &fwd);
        s->position = step_start_pos(s, s->raw_step) + 32u;

        s_populated |= (uint8_t)(1u << i);
        s_idle_div[i] = 0;
    }
    return true;
}

bool hal_encoder_init(void) {
    return hal_encoder_init_mask(0xFu);
}

void hal_encoder_service(void) {
    for (int i = 0; i < 4; i++) {
        if (!(s_populated & (1u << i))) continue;
        substep_t *s = &s_enc[i];

        /* Idle decimation: when stopped, run the full estimator only every
         * ENC_IDLE_DECIMATIONth call; otherwise just detect motion cheaply. */
        if (s->stopped) {
            if (++s_idle_div[i] < ENC_IDLE_DECIMATION) {
                /* cheap motion check: did the raw step move? if so, un-idle. */
                uint step; int cyc; uint us;
                substep_get_counts(s->sm, &step, &cyc, &us);
                if (step == s->raw_step) continue;   /* still stopped, skip */
                /* motion detected: fall through to a full update now */
                s_idle_div[i] = 0;
            } else {
                s_idle_div[i] = 0;
            }
        }
        substep_update(s);
    }
}

int32_t hal_encoder_get_count(evn_encoder_id_t id) {
    return (int32_t)s_enc[id].raw_step * s_sign[id];
}

void hal_encoder_reset(evn_encoder_id_t id) {
    s_enc[id].raw_step = 0;
}

void hal_encoder_set_sign(evn_encoder_id_t id, int8_t sign) {
    s_sign[id] = (sign < 0) ? -1 : +1;
}

/* --- substep (fractional / velocity) accessors for the motion engine --- */

int32_t hal_encoder_get_position_substep(evn_encoder_id_t id) {
    return (int32_t)s_enc[id].position * s_sign[id];
}

int32_t hal_encoder_get_speed_substep(evn_encoder_id_t id) {
    return (int32_t)s_enc[id].speed * s_sign[id];
}

uint32_t hal_encoder_get_transition_age_us(evn_encoder_id_t id) {
    return time_us_32() - s_enc[id].prev_trans_us;
}

bool hal_encoder_is_stopped(evn_encoder_id_t id) {
    return s_enc[id].stopped != 0;
}
