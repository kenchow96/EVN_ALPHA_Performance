#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hal/hal_led.h"
#include "hal/hal_button.h"
#include "hal/hal_i2c.h"
#include "hal/hal_battery.h"

// Non-blocking scheduler intervals (project rule: never sleep in main loop)
#define BUTTON_POLL_INTERVAL_US   1000ULL    // 1 kHz debounce
#define BATTERY_SERVICE_INTERVAL_US 20000ULL // 50 Hz telemetry

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

    // Initial sample + report
    hal_battery_service();
    print_battery();

    uint64_t next_poll = time_us_64();
    uint64_t next_battery = time_us_64();

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

        tight_loop_contents();
    }
}
