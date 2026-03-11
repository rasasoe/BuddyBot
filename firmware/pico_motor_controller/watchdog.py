"""Software watchdog based on monotonic ticks."""

import utime
from config import WATCHDOG_TIMEOUT_MS


class Watchdog:
    def __init__(self):
        self.timeout_ms = WATCHDOG_TIMEOUT_MS
        self.last_feed_time = utime.ticks_ms()

    def feed(self):
        self.last_feed_time = utime.ticks_ms()

    def is_timed_out(self):
        now = utime.ticks_ms()
        return utime.ticks_diff(now, self.last_feed_time) > self.timeout_ms

    def reset(self):
        self.feed()


watchdog = Watchdog()
