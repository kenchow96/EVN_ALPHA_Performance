#include <stdio.h>
#include "pico/stdlib.h"
#include "hal_led.h"
#include "hal_button.h"

// 1 kHz debouncer poll interval (non-blocking; project rule: never sleep)
#define BUTTON_POLL_INTERVAL_US 1000ULL

int main()
{
    stdio_init_all();

    hal_led_init();
    hal_button_init();

    uint64_t next_poll = time_us_64();

    while (true) {
        uint64_t now = time_us_64();

        // Non-blocking 1 kHz scheduler tick
        if ((int64_t)(now - next_poll) >= 0) {
            next_poll = now + BUTTON_POLL_INTERVAL_US;

            // Update the debouncer state machine
            hal_button_update();

            // Toggle Mode (event-based): one reliable event per debounced press
            if (hal_button_get_event()) {
                hal_led_toggle();
                printf("Toggle Mode: Event detected! Toggling LED\n");
            }

            // Pushbutton Mode alternative (instantaneous state):
            // hal_led_set(hal_button_is_pressed());
        }

        tight_loop_contents();
    }
}
