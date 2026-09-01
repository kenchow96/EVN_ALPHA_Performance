#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hal/hal_led.h"
#include "hal/hal_button.h"
#include "hal/hal_i2c.h"
#include "hal/hal_battery.h"
#include "hal/hal_motor.h"
#include "hal/hal_encoder.h"

// Non-blocking scheduler intervals (project rule: never sleep in main loop)
#define BUTTON_POLL_INTERVAL_US   1000ULL    // 1 kHz debounce
#define BATTERY_SERVICE_INTERVAL_US 20000ULL // 50 Hz telemetry
#define ENCODER_SERVICE_INTERVAL_US 1000ULL  // 1 kHz encoder drain
#define MOTOR_TEST_INTERVAL_US    2000000ULL // motor test step every 2 s

static void print_battery(void) {
    evn_battery_state_t b;
    if (!hal_battery_get(&b)) {
        printf("Battery: BQ25887 not present\n");
        return;
    }
    printf("Battery: %.3f V | Cell1: %.3f V | Cell2: %.3f V  (seq=%u)\n",
           b.vbatt_mv / 1000.0f, b.vcell1_mv / 1000.0f, b.vcell2_mv / 1000.0f,
           (unsigned)b.seq);
}

/* Motor + encoder self-test. Cycles a test motor through:
 *   forward 60% (2 s) -> brake (0.5 s) -> reverse 60% (2 s) -> coast (rest)
 * while draining the PIO encoders at 1 kHz and reporting counts each step.
 * The button advances to the next motor. */
static int   s_test_motor = 0;        // which motor is under test
static int   s_phase = 0;             // 0=fwd 1=brake 2=rev 3=coast
static const float TEST_DUTY = 0.60f; // ~60% overcomes stiction
static int32_t s_prev_count = 0;

static void motor_test_step(void) {
    evn_motor_id_t m = (evn_motor_id_t)s_test_motor;
    static const char  *names[] = { "FWD",   "BRAKE", "REV",    "COAST" };
    static const float  duty [] = {  0.60f,   0.0f,    -0.60f,     0.0f    };

    // measure encoder delta over the phase that JUST ran, then advance
    int32_t c = hal_encoder_get_count((evn_encoder_id_t)s_test_motor);
    int32_t delta = c - s_prev_count;
    s_prev_count = c;
    int ran = (s_phase + 3) & 3;   // phase that just finished
    printf("Motor %d ran %-5s duty=%+.2f  enc=%ld  (delta=%+ld)\n",
           s_test_motor + 1, names[ran], (double)duty[ran], (long)c, (long)delta);

    // now command the NEXT phase
    switch (s_phase) {
    case 0: hal_motor_set(m, TEST_DUTY);  break;   // forward
    case 1: hal_motor_brake(m);           break;   // brake
    case 2: hal_motor_set(m, -TEST_DUTY); break;   // reverse
    case 3: hal_motor_coast(m);           break;   // coast
    }
    s_phase = (s_phase + 1) & 3;
}

int main()
{
    stdio_init_all();

    hal_led_init();
    hal_button_init();

    // Boot heartbeat: 3 quick LED blinks so liveness is visible without console
    for (int i = 0; i < 3; i++) {
        hal_led_set(true);
        busy_wait_ms(80);
        hal_led_set(false);
        busy_wait_ms(80);
    }

    evn_i2c_status_t st = hal_i2c_init();
    printf("hal_i2c_init: %s\n", st == EVN_I2C_OK ? "OK (both muxes ACK)" : "MUX ERROR");

    bool bat = hal_battery_init();
    printf("hal_battery_init: %s\n", bat ? "OK (BQ25887 found)" : "NOT FOUND");

    bool mot = hal_motor_init();
    printf("hal_motor_init: %s (4ch DRV8833 @ 25 kHz)\n", mot ? "OK" : "FAIL");

    bool enc = hal_encoder_init();
    printf("hal_encoder_init: %s (4ch PIO quadrature @ pio0)\n", enc ? "OK" : "FAIL");

    // Initial battery report
    hal_battery_service();
    print_battery();
    printf("Motor test: M%d selected. Button = next motor. Cycling FWD/BRAKE/REV/COAST.\n",
           s_test_motor + 1);

    uint64_t next_poll = time_us_64();
    uint64_t next_battery = time_us_64();
    uint64_t next_encoder = time_us_64();
    uint64_t next_motor = time_us_64();

    while (true) {
        uint64_t now = time_us_64();

        // 1 kHz: button debounce
        if ((int64_t)(now - next_poll) >= 0) {
            next_poll = now + BUTTON_POLL_INTERVAL_US;
            hal_button_update();
            if (hal_button_get_event()) {
                hal_led_toggle();
                // advance to next motor, coast the current one first
                hal_motor_coast_all();
                s_test_motor = (s_test_motor + 1) & 3;
                s_phase = 0;
                hal_encoder_reset((evn_encoder_id_t)s_test_motor);
                printf(">> Motor %d selected (prev coasted). Battery %.2f V\n",
                       s_test_motor + 1, hal_battery_voltage_v());
            }
        }

        // 1 kHz: encoder drain
        if ((int64_t)(now - next_encoder) >= 0) {
            next_encoder = now + ENCODER_SERVICE_INTERVAL_US;
            hal_encoder_service();
        }

        // 50 Hz: battery telemetry dispatcher (Core 0 background task)
        if ((int64_t)(now - next_battery) >= 0) {
            next_battery = now + BATTERY_SERVICE_INTERVAL_US;
            hal_battery_service();
        }

        // every 2 s: advance the motor test phase and report encoder count
        if ((int64_t)(now - next_motor) >= 0) {
            next_motor = now + MOTOR_TEST_INTERVAL_US;
            motor_test_step();
        }

        tight_loop_contents();
    }
}
