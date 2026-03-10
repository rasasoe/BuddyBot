"""Line-based USB serial protocol for Pi5 <-> Pico."""

import sys
import uselect
import utime


class UARTProtocol:
    def __init__(self):
        self.buffer = ""
        self.last_command_time = utime.ticks_ms()
        self.poller = uselect.poll()
        self.poller.register(sys.stdin, uselect.POLLIN)

    def _send_message(self, message):
        try:
            sys.stdout.write(message + "\n")
        except Exception:
            pass

    def send_ack(self, command_type):
        self._send_message("ACK,%s" % command_type)

    def send_status(self, estop, timeout, mode):
        self._send_message(
            "STAT,estop=%d,timeout=%d,mode=%s" % (1 if estop else 0, 1 if timeout else 0, mode)
        )

    def send_rpm(self, m0_rpm, m1_rpm, m2_rpm):
        self._send_message("RPM,m0=%.2f,m1=%.2f,m2=%.2f" % (m0_rpm, m1_rpm, m2_rpm))

    def send_safety_event(self, reason):
        self._send_message("SAFE,%s" % reason)

    def _parse_command(self, line):
        parts = line.strip().split(',')
        if not parts or not parts[0]:
            return None, None
        cmd = parts[0].upper()

        if cmd == 'HB' and len(parts) == 1:
            return 'HB', {}
        if cmd == 'CMD' and len(parts) == 4:
            try:
                vx = max(-1.0, min(1.0, float(parts[1])))
                vy = max(-1.0, min(1.0, float(parts[2])))
                wz = max(-1.0, min(1.0, float(parts[3])))
                return 'CMD', {'vx': vx, 'vy': vy, 'wz': wz}
            except ValueError:
                return None, None
        if cmd == 'BRAKE' and len(parts) == 1:
            return 'BRAKE', {}
        if cmd == 'CLEAR' and len(parts) == 1:
            return 'CLEAR', {}
        return None, None

    def parse_command(self):
        events = self.poller.poll(0)
        if not events:
            return None, None

        try:
            chunk = sys.stdin.read(1)
        except Exception:
            self.buffer = ""
            return None, None

        if not chunk:
            return None, None

        if chunk == '\n':
            cmd, params = self._parse_command(self.buffer)
            self.buffer = ""
            if cmd:
                self.last_command_time = utime.ticks_ms()
                return cmd, params
            return None, None

        if chunk != '\r':
            self.buffer += chunk
            if len(self.buffer) > 96:
                self.buffer = ""
        return None, None


uart_protocol = UARTProtocol()
