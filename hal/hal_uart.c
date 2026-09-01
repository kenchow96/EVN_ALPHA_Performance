#include "hal_uart.h"

#include "pico/stdlib.h"
#include "hardware/uart.h"
#include "hardware/gpio.h"
#include "hardware/irq.h"

/* --------------------------------------------------------------------------
 * Pin map (ground truth — Hardware Reference §5)
 * -------------------------------------------------------------------------- */
#define UART1_TX_PIN 0   /* Serial 1 = uart0 */
#define UART1_RX_PIN 1
#define UART2_TX_PIN 8   /* Serial 2 = uart1 */
#define UART2_RX_PIN 9

#define RX_BUF_SIZE 256  /* power of two */

typedef struct {
    uart_inst_t *hw;
    uint8_t      tx_pin, rx_pin;
    uint8_t      irq;         /* UART0_IRQ or UART1_IRQ */
    volatile uint16_t rx_head, rx_tail;
    uint8_t      rx_buf[RX_BUF_SIZE];
    bool         initialised;
} uart_state_t;

static uart_state_t s_uart[2] = {
    { uart0, UART1_TX_PIN, UART1_RX_PIN, UART0_IRQ, 0, 0, {0}, false },
    { uart1, UART2_TX_PIN, UART2_RX_PIN, UART1_IRQ, 0, 0, {0}, false },
};

static inline uint16_t buf_next(uint16_t i) { return (i + 1u) & (RX_BUF_SIZE - 1u); }

/* IRQ: drain HW FIFO into the ring buffer. Runs in interrupt context. */
static void uart_on_irq(uart_state_t *u) {
    while (uart_is_readable(u->hw)) {
        uint8_t c = (uint8_t)uart_get_hw(u->hw)->dr;
        uint16_t next = buf_next(u->rx_head);
        if (next != u->rx_tail) {          /* drop on overflow */
            u->rx_buf[u->rx_head] = c;
            u->rx_head = next;
        }
    }
}

static void uart0_irq_handler(void) { uart_on_irq(&s_uart[0]); }
static void uart1_irq_handler(void) { uart_on_irq(&s_uart[1]); }

bool hal_uart_init(evn_uart_id_t id, uint32_t baud) {
    uart_state_t *u = &s_uart[id];
    uart_init(u->hw, baud);

    gpio_set_function(u->tx_pin, GPIO_FUNC_UART);
    gpio_set_function(u->rx_pin, GPIO_FUNC_UART);
    uart_set_format(u->hw, 8, 1, UART_PARITY_NONE);
    uart_set_fifo_enabled(u->hw, true);

    /* RX IRQ → ring buffer */
    irq_handler_t handler = (id == EVN_UART_1) ? uart0_irq_handler : uart1_irq_handler;
    irq_set_exclusive_handler(u->irq, handler);
    irq_set_enabled(u->irq, true);
    uart_set_irq_enables(u->hw, true, false);  /* RX irq on, TX irq off */

    u->initialised = true;
    return true;
}

bool hal_uart_putc(evn_uart_id_t id, uint8_t c) {
    uart_state_t *u = &s_uart[id];
    if (!uart_is_writable(u->hw)) return false;
    uart_get_hw(u->hw)->dr = c;
    return true;
}

size_t hal_uart_write(evn_uart_id_t id, const uint8_t *data, size_t len) {
    size_t n = 0;
    while (n < len && hal_uart_putc(id, data[n])) n++;
    return n;
}

bool hal_uart_available(evn_uart_id_t id) {
    return s_uart[id].rx_head != s_uart[id].rx_tail;
}

size_t hal_uart_rx_count(evn_uart_id_t id) {
    uart_state_t *u = &s_uart[id];
    return (u->rx_head - u->rx_tail) & (RX_BUF_SIZE - 1u);
}

int hal_uart_getc(evn_uart_id_t id) {
    uart_state_t *u = &s_uart[id];
    if (u->rx_head == u->rx_tail) return -1;
    uint8_t c = u->rx_buf[u->rx_tail];
    u->rx_tail = buf_next(u->rx_tail);
    return c;
}

size_t hal_uart_read(evn_uart_id_t id, uint8_t *buf, size_t len) {
    size_t n = 0;
    int c;
    while (n < len && (c = hal_uart_getc(id)) >= 0) {
        buf[n++] = (uint8_t)c;
    }
    return n;
}

void hal_uart_flush_rx(evn_uart_id_t id) {
    s_uart[id].rx_tail = s_uart[id].rx_head;
}
