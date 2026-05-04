"""Text protocol helpers for Pi5 <-> Pico USB serial link."""

from typing import Optional, Tuple, Dict, Any


class UARTProtocol:
    MSG_HEARTBEAT = "HB"
    MSG_COMMAND = "CMD"
    MSG_BRAKE = "BRAKE"
    MSG_CLEAR = "CLEAR"
    MSG_ACK = "ACK"
    MSG_STATUS = "STAT"
    MSG_RPM = "RPM"
    MSG_SAFETY = "SAFE"

    @staticmethod
    def format_command(vx: float, vy: float, wz: float) -> str:
        vx = max(-1.0, min(1.0, vx))
        vy = max(-1.0, min(1.0, vy))
        wz = max(-1.0, min(1.0, wz))
        return f"CMD,{vx:.3f},{vy:.3f},{wz:.3f}"

    @staticmethod
    def format_heartbeat() -> str:
        return UARTProtocol.MSG_HEARTBEAT

    @staticmethod
    def parse_response(line: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        if not line:
            return None
        parts = line.strip().split(',')
        if not parts:
            return None

        msg_type = parts[0].upper()
        if msg_type == UARTProtocol.MSG_ACK and len(parts) >= 2:
            return UARTProtocol.MSG_ACK, {'command': parts[1]}

        if msg_type == UARTProtocol.MSG_STATUS:
            params = UARTProtocol._parse_kv(parts[1:])
            try:
                return UARTProtocol.MSG_STATUS, {
                    'estop': params.get('estop', '0') == '1',
                    'timeout': params.get('timeout', '0') == '1',
                    'mode': params.get('mode', 'UNKNOWN'),
                    'left_encoder': int(params.get('left', params.get('left_encoder', 0))),
                    'right_encoder': int(params.get('right', params.get('right_encoder', 0))),
                    'back_encoder': int(params.get('back', params.get('back_encoder', 0))),
                }
            except ValueError:
                return None

        if msg_type == UARTProtocol.MSG_RPM:
            params = UARTProtocol._parse_kv(parts[1:])
            try:
                return UARTProtocol.MSG_RPM, {
                    'm0': float(params.get('m0', 0.0)),
                    'm1': float(params.get('m1', 0.0)),
                    'm2': float(params.get('m2', 0.0)),
                }
            except ValueError:
                return None

        if msg_type == UARTProtocol.MSG_SAFETY and len(parts) >= 2:
            return UARTProtocol.MSG_SAFETY, {'reason': ','.join(parts[1:])}

        return None

    @staticmethod
    def _parse_kv(items):
        out = {}
        for item in items:
            if '=' in item:
                k, v = item.split('=', 1)
                out[k.strip().lower()] = v.strip()
        return out
