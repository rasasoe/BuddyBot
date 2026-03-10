"""
BuddyBot Pico Pin Definitions

This module defines all GPIO pin assignments for the motor controller.
Based on actual hardware wiring for L298N motor drivers and encoders.
"""

import machine

# Motor 1 (Left Front) - Connected to L298N Motor Driver 1
MOTOR_LEFT_PWM_PIN = 0    # GP0 - PWM capable
MOTOR_LEFT_DIR1_PIN = 1   # GP1 - Direction control
MOTOR_LEFT_DIR2_PIN = 2   # GP2 - Direction control

# Motor 2 (Right Front) - Connected to L298N Motor Driver 2
MOTOR_RIGHT_PWM_PIN = 4   # GP4 - PWM capable
MOTOR_RIGHT_DIR1_PIN = 5  # GP5 - Direction control
MOTOR_RIGHT_DIR2_PIN = 6  # GP6 - Direction control

# Motor 3 (Back) - Connected to L298N Motor Driver 3
MOTOR_BACK_PWM_PIN = 8    # GP8 - PWM capable
MOTOR_BACK_DIR1_PIN = 9   # GP9 - Direction control
MOTOR_BACK_DIR2_PIN = 10  # GP10 - Direction control

# Encoders - Connected to rotary encoders with pull-up resistors
ENC_LEFT_A_PIN = 11   # GP11 - Left encoder A channel
ENC_LEFT_B_PIN = 12   # GP12 - Left encoder B channel
ENC_RIGHT_A_PIN = 13  # GP13 - Right encoder A channel
ENC_RIGHT_B_PIN = 14  # GP14 - Right encoder B channel
ENC_BACK_A_PIN = 15   # GP15 - Back encoder A channel
ENC_BACK_B_PIN = 16   # GP16 - Back encoder B channel

# Emergency Stop - Connected to normally-open emergency stop button with pull-up
EMERGENCY_STOP_PIN = 17  # GP17 - Emergency stop input (active low)

# Battery ADC - Connected to voltage divider for battery monitoring
BATTERY_ADC_PIN = 26      # GP26/ADC0 - Battery voltage monitoring

# Note: UART pins (GP16/GP17) are reserved for USB serial communication
# Do not use GPIO UART for Pi 5 communication - use USB serial (/dev/ttyACM0)

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