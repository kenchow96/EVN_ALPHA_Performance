#ifndef HAL_LED_H
#define HAL_LED_H

#include "pico/stdlib.h"

// Hardware mapping
#define LED_PIN 25

// Initialize the LED GPIO
void hal_led_init(void);

// Set LED state
void hal_led_set(bool state);

// Toggle LED state
void hal_led_toggle(void);

#endif // HAL_LED_H
