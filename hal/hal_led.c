#include "hal_led.h"

void hal_led_init(void) {
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);
}

void hal_led_set(bool state) {
    gpio_put(LED_PIN, state);
}

void hal_led_toggle(void) {
    static bool state = false;
    state = !state;
    gpio_put(LED_PIN, state);
}
