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
        self.count += 1 if self.pin_b.value() else -1

    def get_count(self):
        return self.count

    def reset(self):
        self.count = 0


encoders = {name: Encoder(name) for name in ('m0', 'm1', 'm2')}
encoders['left'] = encoders['m0']
encoders['right'] = encoders['m1']
encoders['back'] = encoders['m2']
