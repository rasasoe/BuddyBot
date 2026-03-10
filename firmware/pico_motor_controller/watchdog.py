"""
BuddyBot Watchdog

This module implements a watchdog timer for safety.
If no valid commands received within timeout, triggers emergency stop.
"""

import machine
from config import WATCHDOG_TIMEOUT_MS

class Watchdog:
    def __init__(self):
        self.timeout_ms = WATCHDOG_TIMEOUT_MS
        self.last_feed_time = machine.time_pulse_us(machine.Pin(0), 1) // 1000  # Current time in ms

    def feed(self):
        """Feed the watchdog (reset timeout)"""
        self.last_feed_time = machine.time_pulse_us(machine.Pin(0), 1) // 1000

    def is_timed_out(self):
        """Check if watchdog has timed out"""
        current_time = machine.time_pulse_us(machine.Pin(0), 1) // 1000
        return (current_time - self.last_feed_time) > self.timeout_ms

    def reset(self):
        """Reset watchdog state"""
        self.feed()

# Create watchdog instance
watchdog = Watchdog()