#ifndef HAL_ENCODER_H
#define HAL_ENCODER_H

#include <stdint.h>
#include <stdbool.h>

/* ==========================================================================
 * EVN ALPHA Encoder HAL — 4× quadrature encoders, 100% PIO-offloaded (pio0).
 *
 * Ground truth (Hardware Reference §5, §7.2):
 *   M1: A=GP18 B=GP19      M3: A=GP14 B=GP15
 *   M2: A=GP17 B=GP16  (B lower → base=B pin, sign-flip)
 *   M4: A=GP13 B=GP12  (B lower → base=B pin, sign-flip)
 *
 * The PIO (pio/quadrature.pio, official pico-examples design) counts edges in
 * hardware and pushes the step count to each SM's RX FIFO. This HAL drains the
 * FIFOs at 1 kHz into per-motor 32-bit accumulators. No CPU pin polling.
 * ========================================================================== */

typedef enum {
    EVN_ENC_1 = 0,
    EVN_ENC_2 = 1,
    EVN_ENC_3 = 2,
    EVN_ENC_4 = 3
} evn_encoder_id_t;

/* Initialise encoders on pio0 (one SM each). `mask` selects which motors are
 * populated (bit0=M1..bit3=M4); unpopulated encoders are not claimed and are
 * skipped by hal_encoder_service(). Pass 0xF for all four. */
bool hal_encoder_init_mask(uint8_t mask);
bool hal_encoder_init(void);   /* convenience: all four */

/* Drain/refresh encoders. Runs the full substep estimator for moving motors;
 * a motor that has been stopped (no transitions) is serviced at a decimated
 * rate to save CPU — it returns to full rate automatically on motion. */
void hal_encoder_service(void);

/* Total accumulated counts since init (signed; sign = direction). */
int32_t hal_encoder_get_count(evn_encoder_id_t id);

/* Zero an accumulator. */
void hal_encoder_reset(evn_encoder_id_t id);

/* Set count-sign polarity. Encoder count direction depends on which lead is
 * wired to A vs B (and motor mounting), so expose it. sign=+1 normal,
 * sign=-1 inverts. The default per Hardware Reference is +1 for M1/M3 and
 * -1 for M2/M4 (B on the lower pin); override here if your wiring differs. */
void hal_encoder_set_sign(evn_encoder_id_t id, int8_t sign);

/* --- Substep (high-resolution) accessors for the motion engine ---
 * The substep PIO timestamps each edge, giving a fractional position and a
 * low-noise speed estimate that stays smooth at single-tick low speeds
 * (feeds the Luenberger observer in Phase 7). */
int32_t hal_encoder_get_position_substep(evn_encoder_id_t id); /* substeps (256/step-cycle) */
int32_t hal_encoder_get_speed_substep(evn_encoder_id_t id);    /* substeps / second */
uint32_t hal_encoder_get_transition_age_us(evn_encoder_id_t id);
bool    hal_encoder_is_stopped(evn_encoder_id_t id);

#endif /* HAL_ENCODER_H */
