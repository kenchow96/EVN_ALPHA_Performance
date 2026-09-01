/*
 * EVN ALPHA board definition
 *
 * RP2040 + Winbond W25Q128JVSIQ (16 MB QSPI flash), 200 MHz capable.
 * Standalone board header (does not inherit pico.h to avoid redefinition).
 */

#ifndef _BOARDS_EVN_ALPHA_H
#define _BOARDS_EVN_ALPHA_H

/* For board detection by SDK build */
#define EVN_ALPHA

/* --- Flash: Winbond W25Q128JVSIQ, 16 MB --- */
#define PICO_FLASH_SIZE_BYTES        (16 * 1024 * 1024)
/* W25Q128JV max SCK 133 MHz; QSPI /2 at 200 MHz sys = 100 MHz, safe margin. */
#define PICO_FLASH_SPI_CLKDIV        2

/* --- Onboard UI (ground truth: Hardware Reference §5) --- */
#define PICO_DEFAULT_LED_PIN         25
#define PICO_DEFAULT_BUTTON_PIN      24

/* --- UART defaults (Serial 1 = UART0 on GP0/GP1) --- */
#define PICO_DEFAULT_UART            0
#define PICO_DEFAULT_UART_TX_PIN     0
#define PICO_DEFAULT_UART_RX_PIN     1

/* No onboard WS2812 RGB LED */
#undef PICO_DEFAULT_WS2812_PIN

/* --- Standard RP2040 voltage/clock expectations --- */
/* EVN ALPHA regulates 3V3 onboard; default flash voltage is fine. */

#endif /* _BOARDS_EVN_ALPHA_H */
