# Generated Cmake Pico project file

cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Initialise pico_sdk from installed location
# (note this can come from environment, CMake cache etc)

# == DO NOT EDIT THE FOLLOWING LINES for the Raspberry Pi Pico VS Code Extension to work ==
if(WIN32)
    set(USERHOME $ENV{USERPROFILE})
else()
    set(USERHOME $ENV{HOME})
endif()
set(sdkVersion 2.3.0)
set(toolchainVersion 15_2_Rel1)
set(picotoolVersion 2.3.0)
set(picoVscode ${USERHOME}/.pico-sdk/cmake/pico-vscode.cmake)
if (EXISTS ${picoVscode})
    include(${picoVscode})
endif()
# ====================================================================================
set(PICO_BOARD pico CACHE STRING "Board type")

# Pull in Raspberry Pi Pico SDK (must be before project)
include(pico_sdk_import.cmake)

project(EVN_ALPHA_Performance C CXX ASM)

# Initialise the Raspberry Pi Pico SDK
pico_sdk_init()

# Add executable. Default name is the project name, version 0.1

add_executable(EVN_ALPHA_Performance 
    EVN_ALPHA_Performance.c 
    hal/hal_led.c
    hal/hal_button.c
    hal/hal_i2c.c
    hal/hal_battery.c
    hal/hal_uart.c
    hal/hal_servo.c
    hal/hal_motor.c
    hal/hal_encoder.c
    hal/hal_tuning_log.c
    motion/core1.c
    motion/observer.c
    motion/motor_models.c
    motion/trajectory.c
    motion/pid.c
    motion/motion_engine.c
    bench/bench_cycles.c
)

# Generate PIO headers
pico_generate_pio_header(EVN_ALPHA_Performance ${CMAKE_CURRENT_LIST_DIR}/pio/servo.pio)
pico_generate_pio_header(EVN_ALPHA_Performance ${CMAKE_CURRENT_LIST_DIR}/pio/quadrature.pio)

pico_set_program_name(EVN_ALPHA_Performance "EVN_ALPHA_Performance")
pico_set_program_version(EVN_ALPHA_Performance "0.1")

# Modify the below lines to enable/disable output over UART/USB
pico_enable_stdio_uart(EVN_ALPHA_Performance 0)
pico_enable_stdio_usb(EVN_ALPHA_Performance 1)

# Add the standard library to the build
target_link_libraries(EVN_ALPHA_Performance
        pico_stdlib
        pico_multicore
        hardware_i2c
        hardware_uart
        hardware_pio
        hardware_pwm
        hardware_flash)

# Add the standard include files to the build
target_include_directories(EVN_ALPHA_Performance PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}
)

pico_add_extra_outputs(EVN_ALPHA_Performance)

# Spec §4: 200 MHz performance profile
# TinyUSB full-speed CDC uses 64-byte bulk endpoints. Keep class FIFOs at one
# packet; the application owns an 8 KiB record queue and retryable trace blocks.
target_compile_definitions(EVN_ALPHA_Performance PRIVATE
    PICO_USE_FASTEST_SUPPORTED_CLOCK=1
    PICO_STDIO_USB_STDOUT_TIMEOUT_US=500000
    CFG_TUD_CDC_TX_BUFSIZE=64
    CFG_TUD_CDC_RX_BUFSIZE=64
)

# EVN ALPHA flash: Winbond W25Q128JV 16 MB (override generic pico 2 MB).
# QSPI clkdiv /2 -> 100 MHz SCK at 200 MHz sys (W25Q128JV rated to 133 MHz).
target_compile_definitions(EVN_ALPHA_Performance PRIVATE
    PICO_FLASH_SIZE_BYTES=16777216
    PICO_FLASH_SPI_CLKDIV=2
)

