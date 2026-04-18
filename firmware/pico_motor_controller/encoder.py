"""Quadrature encoder reader for BuddyBot Pico."""

import machine
from pins import encoder_pins


class Encoder:
    def __init__(self, encoder_name):
        self.name = encoder_name
        self.pin_a = encoder_pins[encoder_name]['a']
        self.pin_b = encoder_pins[encoder_name]['b']
        self.count = 0
        self.pin_a.irq(trigger=machine.Pin.IRQ_RISING, handler=self._callback)

    def _callback(self, _pin):
        # Match the legacy standalone Pico controller's quadrature sign
        # convention:
        #   enc_b == 0 -> positive count
        #   enc_b == 1 -> negative count
        # This must stay aligned with the motor polarity and direct wheel-mix
        # baseline, otherwise the RPM correction term will push the robot into a
        # consistent arc even when forward/backward commands are nominally
        # symmetric.
        self.count += 1 if not self.pin_b.value() else -1

    def get_count(self):
        return self.count

    def reset(self):
        self.count = 0


encoders = {name: Encoder(name) for name in ('m0', 'm1', 'm2')}
encoders['left'] = encoders['m0']
encoders['right'] = encoders['m1']
encoders['back'] = encoders['m2']
