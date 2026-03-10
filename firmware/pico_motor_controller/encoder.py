"""
BuddyBot Encoder Reader

This module handles quadrature encoder reading using interrupts.
"""

from pins import encoder_pins

class Encoder:
    def __init__(self, encoder_name):
        self.name = encoder_name
        self.pin_a = encoder_pins[encoder_name]['a']
        self.pin_b = encoder_pins[encoder_name]['b']
        self.count = 0

        # Set up interrupt on rising edge of A pin
        self.pin_a.irq(trigger=machine.Pin.IRQ_RISING, handler=self._callback)

    def _callback(self, pin):
        """Interrupt callback for encoder pulses"""
        if self.pin_b.value():
            self.count += 1  # Clockwise
        else:
            self.count -= 1  # Counter-clockwise

    def get_count(self):
        """Get current encoder count"""
        return self.count

    def reset(self):
        """Reset encoder count"""
        self.count = 0

    def get_velocity(self, dt):
        """
        Calculate velocity in counts per second
        dt: time delta in seconds
        """
        if dt > 0:
            return self.count / dt
        return 0

# Create encoder instances
encoder_left = Encoder('left')
encoder_right = Encoder('right')
encoder_back = Encoder('back')

encoders = {
    'left': encoder_left,
    'right': encoder_right,
    'back': encoder_back
}