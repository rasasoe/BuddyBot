"""Hardware pin mapping for the real BuddyBot Pico wiring.

Source of truth: existing lab wiring (do not remap without rewiring).
Pi 5 <-> Pico communication is USB CDC serial (/dev/ttyACM0 on Pi 5),
so GPIO UART pins are intentionally unused.
"""

import machine

# Motor 0
MOTOR0_PWM_PIN = 2
MOTOR0_IN1_PIN = 0
MOTOR0_IN2_PIN = 1
MOTOR0_ENCA_PIN = 3
MOTOR0_ENCB_PIN = 14

# Motor 1
MOTOR1_PWM_PIN = 8
MOTOR1_IN1_PIN = 6
MOTOR1_IN2_PIN = 7
MOTOR1_ENCA_PIN = 9
MOTOR1_ENCB_PIN = 15

# Motor 2
MOTOR2_PWM_PIN = 12
MOTOR2_IN1_PIN = 10
MOTOR2_IN2_PIN = 11
MOTOR2_ENCA_PIN = 13
MOTOR2_ENCB_PIN = 16

# I2C (reserved for expansion sensors)
I2C_SDA_PIN = 20
I2C_SCL_PIN = 21

# Optional hardware E-STOP is not wired on current platform.
# Keep None and enforce software safety layers (watchdog + BRAKE).
EMERGENCY_STOP_PIN = None

# Optional battery ADC input (not mandatory for bring-up)
BATTERY_ADC_PIN = 26


def _make_motor(pwm_pin: int, in1_pin: int, in2_pin: int):
    return {
        'pwm': machine.PWM(machine.Pin(pwm_pin)),
        'dir1': machine.Pin(in1_pin, machine.Pin.OUT),
        'dir2': machine.Pin(in2_pin, machine.Pin.OUT),
    }


def _make_encoder(a_pin: int, b_pin: int):
    return {
        'a': machine.Pin(a_pin, machine.Pin.IN, machine.Pin.PULL_UP),
        'b': machine.Pin(b_pin, machine.Pin.IN, machine.Pin.PULL_UP),
    }


motor_pins = {
    'm0': _make_motor(MOTOR0_PWM_PIN, MOTOR0_IN1_PIN, MOTOR0_IN2_PIN),
    'm1': _make_motor(MOTOR1_PWM_PIN, MOTOR1_IN1_PIN, MOTOR1_IN2_PIN),
    'm2': _make_motor(MOTOR2_PWM_PIN, MOTOR2_IN1_PIN, MOTOR2_IN2_PIN),
}

# Compatibility aliases for existing code paths.
# Field verification on 2026-04-19 showed the current chassis orientation
# presents the physical left/right wheels opposite to the original alias map.
# Keep the low-level GP2/8/12 pin wiring intact and swap only the semantic
# wheel labels so higher-level kiwi kinematics target the correct side.
motor_pins['left'] = motor_pins['m1']
motor_pins['right'] = motor_pins['m0']
motor_pins['back'] = motor_pins['m2']

encoder_pins = {
    'm0': _make_encoder(MOTOR0_ENCA_PIN, MOTOR0_ENCB_PIN),
    'm1': _make_encoder(MOTOR1_ENCA_PIN, MOTOR1_ENCB_PIN),
    'm2': _make_encoder(MOTOR2_ENCA_PIN, MOTOR2_ENCB_PIN),
}
encoder_pins['left'] = encoder_pins['m1']
encoder_pins['right'] = encoder_pins['m0']
encoder_pins['back'] = encoder_pins['m2']

emergency_stop_pin = None
if EMERGENCY_STOP_PIN is not None:
    emergency_stop_pin = machine.Pin(EMERGENCY_STOP_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

battery_adc = machine.ADC(machine.Pin(BATTERY_ADC_PIN))
