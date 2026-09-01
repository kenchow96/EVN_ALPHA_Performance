#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hal/hal_led.h"
#include "hal/hal_button.h"
#include "hal/hal_i2c.h"

// 1 kHz debouncer poll interval (non-blocking; project rule: never sleep)
#define BUTTON_POLL_INTERVAL_US 1000ULL

static void print_scan(void) {
    uint8_t counts[EVN_I2C_PORT_COUNT];
    uint8_t found[EVN_I2C_PORT_COUNT][16];

    printf("\n=== EVN ALPHA I2C 16-Port Scan ===\n");
    uint64_t t0 = time_us_64();
    hal_i2c_scan_all(counts, found);
    uint32_t scan_us = (uint32_t)(time_us_64() - t0);

    int total = 0;
    for (uint8_t p = 1; p <= EVN_I2C_PORT_COUNT; p++) {
        if (counts[p - 1] == 0) continue;
        printf("Port %2d: %d device(s):", p, counts[p - 1]);
        for (uint8_t addr = 0x08; addr < 0x78; addr++) {
            if (found[p - 1][addr >> 3] & (1u << (addr & 7u))) {
                printf(" 0x%02X", addr);
                total++;
            }
        }
        printf("\n");
    }
    printf("Scan complete: %d device(s) across %d ports in %u us\n",
           total, EVN_I2C_PORT_COUNT, scan_us);

    // Cache state diagnostic (spec §3.2)
    printf("Mux cache: bus0=0x%02X bus1=0x%02X\n",
           hal_i2c_cached_channel(0), hal_i2c_cached_channel(1));
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

    // One scan at boot
    print_scan();

    uint64_t next_poll = time_us_64();

    while (true) {
        uint64_t now = time_us_64();

        // Non-blocking 1 kHz scheduler tick
        if ((int64_t)(now - next_poll) >= 0) {
            next_poll = now + BUTTON_POLL_INTERVAL_US;

            hal_button_update();

            // Button press = re-scan (and toggle LED as liveness proof)
            if (hal_button_get_event()) {
                hal_led_toggle();
                print_scan();
            }
        }

        tight_loop_contents();
    }
}
