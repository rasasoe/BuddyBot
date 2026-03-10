"""
BuddyBot Safety System

This module handles emergency stop and safety interlocks.
"""

from pins import emergency_stop_pin
from motor_driver import motors

class SafetySystem:
    def __init__(self):
        self.emergency_stop_active = False
        self.emergency_stop_pin_state = False

    def check_emergency_stop_pin(self):
        """Check physical emergency stop pin"""
        # Active low (pressed = 0)
        pin_pressed = emergency_stop_pin.value() == 0
        if pin_pressed and not self.emergency_stop_pin_state:
            self.emergency_stop_pin_state = True
            self.trigger_emergency_stop()
        elif not pin_pressed:
            self.emergency_stop_pin_state = False

    def trigger_emergency_stop(self):
        """Trigger emergency stop - stops all motors"""
        self.emergency_stop_active = True
        for motor in motors.values():
            motor.stop()

    def clear_emergency_stop(self):
        """Clear emergency stop (requires explicit command)"""
        self.emergency_stop_active = False

    def is_emergency_stop_active(self):
        """Check if emergency stop is active"""
        return self.emergency_stop_active

    def check_watchdog_timeout(self, watchdog_timed_out):
        """Handle watchdog timeout"""
        if watchdog_timed_out and not self.emergency_stop_active:
            self.trigger_emergency_stop()

# Create safety system instance
safety_system = SafetySystem()