"""Safety supervisor for Pico motor controller."""

from pins import emergency_stop_pin
from motor_driver import motors


class SafetySystem:
    def __init__(self):
        self.emergency_stop_active = False
        self.emergency_stop_pin_state = False
        self.last_reason = ""

    def check_emergency_stop_pin(self):
        """Check physical E-STOP input when wired; no-op otherwise."""
        if emergency_stop_pin is None:
            return

        pin_pressed = emergency_stop_pin.value() == 0
        if pin_pressed and not self.emergency_stop_pin_state:
            self.emergency_stop_pin_state = True
            self.activate_emergency_stop('hw_estop')
        elif not pin_pressed:
            self.emergency_stop_pin_state = False

    def activate_emergency_stop(self, reason='software'):
        self.emergency_stop_active = True
        self.last_reason = reason
        for motor in motors.values():
            motor.stop()

    def clear_emergency_stop(self):
        self.emergency_stop_active = False
        self.last_reason = ''

    def is_emergency_stop_active(self):
        return self.emergency_stop_active

    def check_watchdog_timeout(self, watchdog_timed_out):
        if watchdog_timed_out and not self.emergency_stop_active:
            self.activate_emergency_stop('watchdog_timeout')


safety_system = SafetySystem()
