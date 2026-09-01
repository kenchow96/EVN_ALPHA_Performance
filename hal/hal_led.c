#include "hal_led.h"
#include "hardware/structs/sio.h"

// Direct SIO register access (repo rule: prefer registers over SDK wrappers).
// GPIO 25 < 30 so GPIO_OUT / GPIO_OUT_XOR / GPIO_OUT_SET / GPIO_OUT_CLR all apply.

void hal_led_init(void) {
    gpio_set_function(LED_PIN, GPIO_FUNC_SIO);
    sio_hw->gpio_oe_set = 1u << LED_PIN;   // output-enable only; gpio_init() not needed
}

void hal_led_set(bool state) {
    if (state) {
        sio_hw->gpio_set = 1u << LED_PIN;
    } else {
        sio_hw->gpio_clr = 1u << LED_PIN;
    }
}

void hal_led_toggle(void) {
    sio_hw->gpio_togl = 1u << LED_PIN;
}
