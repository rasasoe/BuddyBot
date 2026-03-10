"""
BuddyBot Pico Pin Definitions

This module defines all GPIO pin assignments for the motor controller.
"""

import machine

# Motor 1 (Left)
MOTOR_LEFT_PWM_PIN = 0
MOTOR_LEFT_DIR1_PIN = 1
MOTOR_LEFT_DIR2_PIN = 2

# Motor 2 (Right)
MOTOR_RIGHT_PWM_PIN = 3
MOTOR_RIGHT_DIR1_PIN = 4
MOTOR_RIGHT_DIR2_PIN = 5

# Motor 3 (Back)
MOTOR_BACK_PWM_PIN = 6
MOTOR_BACK_DIR1_PIN = 7
MOTOR_BACK_DIR2_PIN = 8

# Encoders
ENC_LEFT_A_PIN = 9
ENC_LEFT_B_PIN = 10
ENC_RIGHT_A_PIN = 11
ENC_RIGHT_B_PIN = 12
ENC_BACK_A_PIN = 13
ENC_BACK_B_PIN = 14

# Emergency Stop
EMERGENCY_STOP_PIN = 15

# Battery ADC
BATTERY_ADC_PIN = 26

# UART (defined in config.py, but pins here for reference)
UART_TX_PIN = 16
UART_RX_PIN = 17

# Pin objects (initialized in motor_driver.py and encoder.py)
motor_pins = {
    'left': {
        'pwm': machine.PWM(machine.Pin(MOTOR_LEFT_PWM_PIN)),
        'dir1': machine.Pin(MOTOR_LEFT_DIR1_PIN, machine.Pin.OUT),
        'dir2': machine.Pin(MOTOR_LEFT_DIR2_PIN, machine.Pin.OUT)
    },
    'right': {
        'pwm': machine.PWM(machine.Pin(MOTOR_RIGHT_PWM_PIN)),
        'dir1': machine.Pin(MOTOR_RIGHT_DIR1_PIN, machine.Pin.OUT),
        'dir2': machine.Pin(MOTOR_RIGHT_DIR2_PIN, machine.Pin.OUT)
    },
    'back': {
        'pwm': machine.PWM(machine.Pin(MOTOR_BACK_PWM_PIN)),
        'dir1': machine.Pin(MOTOR_BACK_DIR1_PIN, machine.Pin.OUT),
        'dir2': machine.Pin(MOTOR_BACK_DIR2_PIN, machine.Pin.OUT)
    }
}

encoder_pins = {
    'left': {
        'a': machine.Pin(ENC_LEFT_A_PIN, machine.Pin.IN),
        'b': machine.Pin(ENC_LEFT_B_PIN, machine.Pin.IN)
    },
    'right': {
        'a': machine.Pin(ENC_RIGHT_A_PIN, machine.Pin.IN),
        'b': machine.Pin(ENC_RIGHT_B_PIN, machine.Pin.IN)
    },
    'back': {
        'a': machine.Pin(ENC_BACK_A_PIN, machine.Pin.IN),
        'b': machine.Pin(ENC_BACK_B_PIN, machine.Pin.IN)
    }
}

emergency_stop_pin = machine.Pin(EMERGENCY_STOP_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
battery_adc = machine.ADC(machine.Pin(BATTERY_ADC_PIN))