#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hal/hal_led.h"
#include "hal/hal_button.h"
#include "hal/hal_i2c.h"
#include "hal/hal_battery.h"
#include "hal/hal_uart.h"
#include "hal/hal_servo.h"

// Non-blocking scheduler intervals (project rule: never sleep in main loop)
#define BUTTON_POLL_INTERVAL_US   1000ULL    // 1 kHz debounce
#define BATTERY_SERVICE_INTERVAL_US 20000ULL // 50 Hz telemetry
#define UART_LOOPBACK_INTERVAL_US 500000ULL  // 2 Hz loopback self-test
#define SERVO_SWEEP_INTERVAL_US   20000ULL   // 50 Hz sweep update

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

/* Loopback: send a counter on Serial 1 (uart0 TX=GP0), read it back on
 * Serial 2 (uart1 RX=GP9) via the TX1->RX2 crossover wire, and vice versa. */
static void uart_loopback_test(void) {
    static uint32_t counter = 0;
    char msg[32];
    int len = snprintf(msg, sizeof msg, "PING%lu", (unsigned long)counter++);

    // Send on both ports
    hal_uart_flush_rx(EVN_UART_2);
    hal_uart_write(EVN_UART_1, (const uint8_t *)msg, len);

    // Give the wire a moment (bytes arrive via RX IRQ into ring buffer)
    uint64_t deadline = time_us_64() + 50000ULL; // 50 ms
    int got = 0;
    uint8_t rx[32];
    while (time_us_64() < deadline && got < len) {
        int c = hal_uart_getc(EVN_UART_2);
        if (c >= 0) rx[got++] = (uint8_t)c;
    }
    rx[got] = '\0';

    bool pass = (got == len) && (memcmp(rx, msg, len) == 0);
    static uint32_t pass_count = 0, fail_count = 0;
    if (pass) pass_count++; else fail_count++;
    // Print every test while failing, else a summary every 10 tests
    if (!pass || (pass_count % 10u) == 1u) {
        printf("UART loopback: '%s'->'%s' %s (pass=%lu fail=%lu)\n",
               msg, rx, pass ? "PASS" : "FAIL",
               (unsigned long)pass_count, (unsigned long)fail_count);
    }
}

/* Servo sweep self-test: triangle-wave all 4 channels 0↔180°, 50 Hz update.
 * Prints a status line each time the sweep reverses. */
static void servo_sweep_test(void) {
    static float angle = 0.0f;
    static float step = 1.0f;      // degrees per 20 ms tick → 90°/s sweep
    angle += step;
    if (angle >= 180.0f) { angle = 180.0f; step = -1.0f; printf("Servo sweep: at 180°\n"); }
    if (angle <= 0.0f)   { angle = 0.0f;   step =  1.0f; printf("Servo sweep: at 0°\n"); }
    for (int i = 0; i < EVN_SERVO_COUNT; i++) {
        hal_servo_write_angle((evn_servo_id_t)i, angle, false);
    }
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

    hal_uart_init(EVN_UART_1, 115200);
    hal_uart_init(EVN_UART_2, 115200);
    printf("hal_uart_init: Serial1 (uart0 GP0/GP1) + Serial2 (uart1 GP8/GP9) @115200\n");

    bool srv = hal_servo_init();
    printf("hal_servo_init: %s (4ch PIO @ 50 Hz, centred 1500us)\n", srv ? "OK" : "SM CLAIM FAIL");

    // Initial sample + report
    hal_battery_service();
    print_battery();

    uint64_t next_poll = time_us_64();
    uint64_t next_battery = time_us_64();
    uint64_t next_loopback = time_us_64();
    uint64_t next_servo = time_us_64();

    while (true) {
        uint64_t now = time_us_64();

        // 1 kHz: button debounce
        if ((int64_t)(now - next_poll) >= 0) {
            next_poll = now + BUTTON_POLL_INTERVAL_US;
            hal_button_update();
            if (hal_button_get_event()) {
                hal_led_toggle();
                print_battery();
            }
        }

        // 50 Hz: battery telemetry dispatcher (Core 0 background task)
        if ((int64_t)(now - next_battery) >= 0) {
            next_battery = now + BATTERY_SERVICE_INTERVAL_US;
            hal_battery_service();
        }

        // 2 Hz: UART loopback self-test
        if ((int64_t)(now - next_loopback) >= 0) {
            next_loopback = now + UART_LOOPBACK_INTERVAL_US;
            uart_loopback_test();
        }

        // 50 Hz: servo sweep self-test
        if ((int64_t)(now - next_servo) >= 0) {
            next_servo = now + SERVO_SWEEP_INTERVAL_US;
            servo_sweep_test();
        }

        tight_loop_contents();
    }
}
