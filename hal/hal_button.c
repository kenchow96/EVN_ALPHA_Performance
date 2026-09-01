#include "hal_button.h"
#include "hardware/structs/sio.h"

static void (*button_callback)(void) = NULL;
static volatile bool event_triggered = false;

void hal_button_init(void) {
    gpio_set_function(BUTTON_PIN, GPIO_FUNC_SIO);
    // Input is default after function-select; just enable pull-up.
    gpio_pull_up(BUTTON_PIN);
}

void hal_button_set_callback(void (*callback)(void)) {
    button_callback = callback;
}

bool hal_button_is_pressed(void) {
    return !(sio_hw->gpio_in & (1u << BUTTON_PIN));
}

bool hal_button_get_event(void) {
    if (event_triggered) {
        event_triggered = false;
        return true;
    }
    return false;
}

void hal_button_update(void) {
    static bool last_stable_state = true;
    static uint32_t stable_count = 0;
    const uint32_t STABLE_THRESHOLD = 20;

    bool current_sample = (sio_hw->gpio_in & (1u << BUTTON_PIN)) != 0;

    if (current_sample == last_stable_state) {
        stable_count = 0;
    } else {
        if (++stable_count >= STABLE_THRESHOLD) {
            last_stable_state = current_sample;
            stable_count = 0;

            if (last_stable_state == false) { // Button Pressed (active-low)
                event_triggered = true;
                if (button_callback) {
                    button_callback();
                }
            }
        }
    }
}


