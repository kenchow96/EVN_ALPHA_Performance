#ifndef HAL_BUTTON_H
#define HAL_BUTTON_H

#include "pico/stdlib.h"

// Hardware mapping
#define BUTTON_PIN 24

// Initialize the button GPIO
void hal_button_init(void);

// Set the button callback for Toggle mode (triggered on press/release)
void hal_button_set_callback(void (*callback)(void));

// Update button state (call this in main loop)
void hal_button_update(void);

// Pushbutton mode: Read the instantaneous state (returns true if pressed)
bool hal_button_is_pressed(void);

// Returns true if the button was pressed and released since last check
bool hal_button_get_event(void);

#endif // HAL_BUTTON_H
