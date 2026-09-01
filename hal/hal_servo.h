#ifndef HAL_SERVO_H
#define HAL_SERVO_H

#include <stdint.h>
#include <stdbool.h>

/* ==========================================================================
 * EVN ALPHA Servo HAL — 4 channels, PIO-driven PWM (pio1), 50 Hz, µs pulses.
 *
 * Ground truth (Hardware Reference §5, §9.1):
 *   Servo 1 → GP2, Servo 2 → GP3, Servo 3 → GP10, Servo 4 → GP11
 *   CRITICAL: Servos 3/4 (GP10/11) share hardware PWM Slice 5 with Motor 2
 *   (GP26/27). Therefore ALL servos are PIO-driven (pio1), never hardware PWM,
 *   so Motor 2 keeps Slice 5 at 25 kHz.
 *
 * Each channel runs on its own PIO state machine; the CPU pushes
 * (high_us, low_us) per 20 ms frame. Pulse range clamped to safe servo bounds.
 *
 * Defaults match common hobby servos; Arduino EVNServo uses 200–2800 µs.
 * ========================================================================== */

#define EVN_SERVO_COUNT        4
#define EVN_SERVO_FRAME_US     20000UL   /* 50 Hz */
#define EVN_SERVO_MIN_US       200U      /* safe electrical floor (matches Arduino) */
#define EVN_SERVO_MAX_US       2800U
#define EVN_SERVO_DEFAULT_MIN  500U      /* typical 0°   */
#define EVN_SERVO_DEFAULT_MAX  2500U     /* typical 180° */
#define EVN_SERVO_CENTER_US    1500U

typedef enum {
    EVN_SERVO_1 = 0,  /* GP2  */
    EVN_SERVO_2 = 1,  /* GP3  */
    EVN_SERVO_3 = 2,  /* GP10 */
    EVN_SERVO_4 = 3   /* GP11 */
} evn_servo_id_t;

/* Initialise all 4 servo channels on pio1 (one SM each), outputs disabled-low.
 * Returns true if all 4 SMs claimed and started. Call from Core 0. */
bool hal_servo_init(void);

/* Set a channel's pulse width directly in microseconds (clamped to
 * [EVN_SERVO_MIN_US, EVN_SERVO_MAX_US]). Takes effect next frame. */
void hal_servo_write_us(evn_servo_id_t id, uint16_t pulse_us);

/* Set by angle: 0–180 degrees mapped onto [min_us, max_us] (defaults
 * 500–2500 µs). dir=false → normal, dir=true → reversed. */
void hal_servo_write_angle(evn_servo_id_t id, float degrees, bool dir);

/* Per-channel calibration of the angle→µs endpoints. */
void hal_servo_set_range(evn_servo_id_t id, uint16_t min_us, uint16_t max_us);

/* Disable (drive low / stop pulses) or re-enable a channel. */
void hal_servo_disable(evn_servo_id_t id);
void hal_servo_enable(evn_servo_id_t id);

/* Diagnostics: current commanded µs per channel. */
uint16_t hal_servo_get_us(evn_servo_id_t id);

#endif /* HAL_SERVO_H */
