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
static int   s_cycle = 0;             // completed FWD..COAST cycles this motor
static bool  s_test_done = false;     // all motors cycled → test halted

#define TEST_CYCLES_PER_MOTOR 3       // 3 full cycles, then move on

/* Called once after the LAST motor finishes: coast everything, let the bus
 * settle, then log a clean (no-load) battery reading for the multimeter
 * comparison data point. */
static void motor_test_finish(void) {
    hal_motor_coast_all();
    // let brush bounce / bus recover before the no-load reading
    busy_wait_ms(500);
    hal_battery_service();
    busy_wait_ms(50);
    hal_battery_service();              // ensure a fresh published sample
    evn_battery_state_t b;
    if (hal_battery_get(&b)) {
        printf("\n=== TEST COMPLETE (no-load battery) ===\n");
        printf("Battery: %.3f V | Cell1: %.3f V | Cell2: %.3f V\n",
               b.vbatt_mv / 1000.0f, b.vcell1_mv / 1000.0f, b.vcell2_mv / 1000.0f);
        printf("(motors coasted — take multimeter reading now)\n");
    }
}

static void motor_test_step(void) {
    if (s_test_done) return;
    evn_motor_id_t m = (evn_motor_id_t)s_test_motor;
    static const char  *names[] = { "FWD",   "BRAKE", "REV",    "COAST" };
    static const float  duty [] = {  0.60f,   0.0f,    -0.60f,     0.0f    };

    // measure encoder delta over the phase that JUST ran, then advance
    evn_encoder_id_t e = (evn_encoder_id_t)s_test_motor;
    int32_t c = hal_encoder_get_count(e);
    int32_t delta = c - s_prev_count;
    s_prev_count = c;
    int ran = (s_phase + 3) & 3;   // phase that just finished
    int32_t spd = hal_encoder_get_speed_substep(e);
    int32_t pos = hal_encoder_get_position_substep(e);
    printf("Motor %d cyc%d %-5s duty=%+.2f  steps=%ld (delta=%+ld)  speed=%ld s/s %s\n",
           s_test_motor + 1, s_cycle, names[ran], (double)duty[ran], (long)c, (long)delta,
           (long)spd, hal_encoder_is_stopped(e) ? "[stopped]" : "");

    // now command the NEXT phase
    switch (s_phase) {
    case 0: hal_motor_set(m, TEST_DUTY);  break;   // forward
    case 1: hal_motor_brake(m);           break;   // brake
    case 2: hal_motor_set(m, -TEST_DUTY); break;   // reverse
    case 3: hal_motor_coast(m);           break;   // coast
    }

    // completed a full FWD..COAST cycle when we wrap from coast back to fwd
    if (s_phase == 3) {
        s_cycle++;
        if (s_cycle >= TEST_CYCLES_PER_MOTOR) {
            // this motor done — auto-advance to next populated motor
            s_cycle = 0;
            hal_motor_coast(m);
            s_test_motor++;
            s_phase = 0;
            if (s_test_motor >= 4) {
                s_test_motor = 3;      // stay parked
                s_test_done = true;
                motor_test_finish();
                return;
            }
            hal_encoder_reset((evn_encoder_id_t)s_test_motor);
            s_prev_count = 0;
            printf(">> Auto-advance to Motor %d\n", s_test_motor + 1);
        }
    }
    s_phase = (s_phase + 1) & 3;
}

/* --- scheduler tasks (file scope) --- */
static void task_button(void) {
    hal_button_update();
    if (hal_button_get_event()) {
        hal_led_toggle();
        // button = restart the finite test from Motor 1
        hal_motor_coast_all();
        s_test_motor = 0;
        s_phase = 0;
        s_cycle = 0;
        s_prev_count = 0;
        s_test_done = false;
        hal_encoder_reset(EVN_ENC_1);
        printf(">> Test restarted at Motor 1. Battery %.2f V\n", hal_battery_voltage_v());
    }
}
static void task_encoder(void) { hal_encoder_service(); }
static void task_battery(void) { hal_battery_service(); }
static void task_motor(void)   { motor_test_step(); }

typedef struct { uint64_t next; uint64_t period_us; void (*fn)(void); } task_t;

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
    printf("hal_motor_init: %s (4ch DRV8833 @ %u kHz)\n", mot ? "OK" : "FAIL", (unsigned)(EVN_MOTOR_PWM_FREQ_HZ/1000));

    bool enc = hal_encoder_init();
    printf("hal_encoder_init: %s (4ch PIO substep @ pio0)\n", enc ? "OK" : "FAIL");

    // Initial battery report
    hal_battery_service();
    print_battery();
    printf("Motor test: %d cycles/motor, auto-advance M1→M4, then coast + clean battery reading. Button = restart.\n",
           TEST_CYCLES_PER_MOTOR);

    /* --- Non-blocking task-table scheduler -------------------------------
     * One elapsed-time check per task; a single now timestamp per pass.
     * Tasks ordered by rate (fastest first) for deterministic service. */
    static task_t s_tasks[] = {
        { 0, BUTTON_POLL_INTERVAL_US,    task_button  },   // 1 kHz
        { 0, ENCODER_SERVICE_INTERVAL_US, task_encoder },  // 1 kHz
        { 0, BATTERY_SERVICE_INTERVAL_US, task_battery },  // 50 Hz
        { 0, MOTOR_TEST_INTERVAL_US,     task_motor   },   // 0.5 Hz
    };
    const unsigned n_tasks = sizeof(s_tasks) / sizeof(s_tasks[0]);
    for (unsigned i = 0; i < n_tasks; i++) s_tasks[i].next = time_us_64();

    while (true) {
        uint64_t now = time_us_64();
        for (unsigned i = 0; i < n_tasks; i++) {
            if ((int64_t)(now - s_tasks[i].next) >= 0) {
                s_tasks[i].next = now + s_tasks[i].period_us;
                s_tasks[i].fn();
            }
        }
        tight_loop_contents();
    }
}
