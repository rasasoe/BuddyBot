"""
BuddyBot Motor Driver

This module handles low-level motor control using PWM and direction pins.
"""

import machine
from config import MAX_MOTOR_SPEED, MIN_MOTOR_SPEED, MOTOR_DIRECTION_SIGNS
from pins import motor_pins

class MotorDriver:
    def __init__(self, motor_name):
        self.name = motor_name
        self.pwm = motor_pins[motor_name]['pwm']
        self.dir1 = motor_pins[motor_name]['dir1']
        self.dir2 = motor_pins[motor_name]['dir2']
        self.direction_sign = 1 if MOTOR_DIRECTION_SIGNS.get(motor_name, 1) >= 0 else -1
        self.pwm.freq(1000)  # 1kHz PWM frequency

    def set_speed(self, speed):
        """
        Set motor speed as a normalized value (-1.0 to 1.0)
        Positive = forward, Negative = reverse, 0 = stop
        """
        # Clamp speed to valid range
        speed = max(MIN_MOTOR_SPEED, min(MAX_MOTOR_SPEED, speed))
        speed *= self.direction_sign

        if speed > 0:
            # Preserve the legacy Pico single-file convention that was already
            # field-proven on BuddyBot before the firmware was modularized.
            # In that implementation, positive output meant IN1=0, IN2=1.
            self.dir1.value(0)
            self.dir2.value(1)
            duty = int(speed * 65535)  # Convert to 16-bit duty cycle
        elif speed < 0:
            self.dir1.value(1)
            self.dir2.value(0)
            duty = int(-speed * 65535)  # Use absolute value
        else:
            # Stop
            self.dir1.value(0)
            self.dir2.value(0)
            duty = 0

        self.pwm.duty_u16(duty)

    def stop(self):
        """Emergency stop this motor"""
        self.dir1.value(0)
        self.dir2.value(0)
        self.pwm.duty_u16(0)

# Create motor driver instances
motor_left = MotorDriver('left')
motor_right = MotorDriver('right')
motor_back = MotorDriver('back')

motors = {
    'left': motor_left,
    'right': motor_right,
    'back': motor_back
}
