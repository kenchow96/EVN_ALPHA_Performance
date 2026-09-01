#ifndef HAL_UART_H
#define HAL_UART_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* ==========================================================================
 * EVN ALPHA UART HAL — Serial 1 (UART0) & Serial 2 (UART1)
 *
 * Ground truth (Hardware Reference §5):
 *   Serial 1: UART0  TX=GP0  RX=GP1
 *   Serial 2: UART1  TX=GP8  RX=GP9
 *
 * Non-blocking, ring-buffered UART with RX IRQ drain. No sleeps anywhere.
 * Both ports default to 115200 8N1 (configurable per port).
 * ========================================================================== */

typedef enum {
    EVN_UART_1 = 0,   /* Serial 1 header → uart0, GP0/GP1 */
    EVN_UART_2 = 1    /* Serial 2 header → uart1, GP8/GP9 */
} evn_uart_id_t;

/* Initialise a UART port: pins, baud, 8N1, RX ring buffer + IRQ drain.
 * Returns true on success. Call from Core 0. */
bool hal_uart_init(evn_uart_id_t id, uint32_t baud);

/* --- Transmit (non-blocking; drops byte if HW FIFO full) --- */
bool hal_uart_putc(evn_uart_id_t id, uint8_t c);
size_t hal_uart_write(evn_uart_id_t id, const uint8_t *data, size_t len);

/* --- Receive (from IRQ-drained ring buffer) --- */
bool   hal_uart_available(evn_uart_id_t id);          /* any byte waiting? */
size_t hal_uart_rx_count(evn_uart_id_t id);           /* bytes buffered */
int    hal_uart_getc(evn_uart_id_t id);               /* -1 if empty */
size_t hal_uart_read(evn_uart_id_t id, uint8_t *buf, size_t len);

/* Flush RX ring buffer. */
void hal_uart_flush_rx(evn_uart_id_t id);

#endif /* HAL_UART_H */
