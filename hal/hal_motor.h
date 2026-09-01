#ifndef HAL_MOTOR_H
#define HAL_MOTOR_H

#include <stdint.h>
#include <stdbool.h>

/* ==========================================================================
 * EVN ALPHA Motor HAL — 4× TI DRV8833 H-bridges, hardware PWM @ 25 kHz.
 *
 * Ground truth (Hardware Reference §5, §7.1):
 *   200 MHz / 25 kHz → WRAP = 7999 (8000 steps ≈ 13-bit).
 *   M1: IN1=GP29 (slice6 B), IN2=GP28 (slice6 A)
 *   M2: IN1=GP27 (slice5 B), IN2=GP26 (slice5 A)
 *   M3: IN1=GP23 (slice3 B), IN2=GP22 (slice3 A)
 *   M4: IN1=GP21 (slice2 B), IN2=GP20 (slice2 A)
 *
 *   DRV8833 truth table:
 *     Forward:  IN1=PWM, IN2=0      Reverse: IN1=0, IN2=PWM
 *     Brake:    IN1=1,   IN2=1      Coast:   IN1=0, IN2=0
 *
 * All PWM writes go straight to the hardware registers (no SDK wrapper in the
 * hot path). Duty is signed −1.0..+1.0 (sign = direction).
 * ========================================================================== */

#define EVN_MOTOR_COUNT 4

/* 25 kHz is ultrasonic and gives 8000 duty steps at 200 MHz. Raising the
 * carrier to 40 kHz does not raise the 1 kHz control bandwidth or average
 * motor voltage; it reduces resolution to 5000 steps and raises switching
 * loss. Revisit only with an isolated current-ripple/response A/B result. */
#define EVN_MOTOR_PWM_FREQ_HZ  25000UL

typedef enum {
    EVN_MOTOR_1 = 0,
    EVN_MOTOR_2 = 1,
    EVN_MOTOR_3 = 2,
    EVN_MOTOR_4 = 3
} evn_motor_id_t;

/* Initialise motor PWM pairs at EVN_MOTOR_PWM_FREQ_HZ (clkdiv=1, WRAP derived
 * from sysclk). Only the motors set in `mask` (bit0=M1..bit3=M4) are set up;
 * others are left untouched for partial-population builds. Pass 0xF for all. */
bool hal_motor_init_mask(uint8_t mask);

/* Init all 4 (convenience). */
bool hal_motor_init(void);

/* Runtime PWM frequency change (Hz). Recomputes WRAP; call before enabling
 * outputs. Rarely needed — the default is tuned. */
void hal_motor_set_pwm_freq(uint32_t freq_hz);

/* Current configured carrier frequency, for benchmark trace metadata. */
uint32_t hal_motor_get_pwm_freq(void);

/* Drive a motor. duty in [-1.0, +1.0]; magnitude → PWM duty, sign → direction
 * per the DRV8833 truth table. 0 = coast (both low). Clamped internally. */
void hal_motor_set(evn_motor_id_t id, float duty);

/* Active brake (both inputs high) and high-impedance coast (both low). */
void hal_motor_brake(evn_motor_id_t id);
void hal_motor_coast(evn_motor_id_t id);

/* Convenience: brake/coast all four. */
void hal_motor_brake_all(void);
void hal_motor_coast_all(void);

/* Diagnostics: current PWM level (0..WRAP) on the driven pin per motor. */
uint16_t hal_motor_get_level(evn_motor_id_t id);

/* Set drive-direction polarity. Motor/encoder convention depends on how the
 * motor is mounted and which encoder lead lands on A vs B, so make it a
 * runtime setting. dir=+1 normal, dir=-1 swaps the meaning of forward/reverse.
 * Default is +1. Applies to hal_motor_set() only (brake/coast unaffected). */
void hal_motor_set_direction(evn_motor_id_t id, int8_t dir);

#endif /* HAL_MOTOR_H */
