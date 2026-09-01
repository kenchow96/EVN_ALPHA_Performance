#include "hal_button.h"

static void (*button_callback)(void) = NULL;
static volatile bool event_triggered = false;

void hal_button_init(void) {
    gpio_init(BUTTON_PIN);
    gpio_set_dir(BUTTON_PIN, GPIO_IN);
    gpio_pull_up(BUTTON_PIN);
}

void hal_button_set_callback(void (*callback)(void)) {
    button_callback = callback;
}

bool hal_button_is_pressed(void) {
    return !gpio_get(BUTTON_PIN);
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
    static bool current_sample = true;
    static uint32_t stable_count = 0;
    const uint32_t STABLE_THRESHOLD = 20;

    current_sample = gpio_get(BUTTON_PIN);

    if (current_sample == last_stable_state) {
        stable_count = 0;
    } else {
        stable_count++;
        if (stable_count >= STABLE_THRESHOLD) {
            last_stable_state = current_sample;
            stable_count = 0;

            if (last_stable_state == false) { // Button Pressed (Low)
                if (button_callback) {
                    button_callback();
                }
                event_triggered = true;
            }
        }
    }
}


