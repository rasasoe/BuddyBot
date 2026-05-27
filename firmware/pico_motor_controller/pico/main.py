"""BuddyBot Pico firmware entrypoint (deploy this as /main.py on Pico)."""

import utime

from config import CONTROL_LOOP_PERIOD_MS, STATUS_REPORT_INTERVAL, BATTERY_VOLTAGE_DIVIDER_RATIO
from pins import battery_adc
from motor_driver import motors
from encoder import encoders
from pid import PIDController
from kinematics import kinematics
from uart_protocol import uart_protocol
from watchdog import watchdog
from safety import safety_system
from state import system_state


def read_battery_voltage():
    adc_value = battery_adc.read_u16()
    return (adc_value / 65535.0) * 3.3 * BATTERY_VOLTAGE_DIVIDER_RATIO


def stop_all():
    for motor in motors.values():
        motor.stop()


def control_loop(pid_controllers):
    command_type, params = uart_protocol.parse_command()
    if command_type == 'HB':
        uart_protocol.send_ack('HB')
        watchdog.feed()
    elif command_type == 'CMD':
        system_state.update_targets(params['vx'], params['vy'], params['wz'])
        uart_protocol.send_ack('CMD')
        watchdog.feed()
    elif command_type == 'BRAKE':
        safety_system.activate_emergency_stop('brake_command')
        uart_protocol.send_ack('BRAKE')
        uart_protocol.send_safety_event('brake_command')
    elif command_type == 'CLEAR':
        watchdog.feed()
        safety_system.clear_emergency_stop()
        uart_protocol.send_ack('CLEAR')
    elif command_type is None and params is None:
        pass

    safety_system.check_emergency_stop_pin()
    timeout = watchdog.is_timed_out()
    safety_system.check_watchdog_timeout(timeout)

    if safety_system.is_emergency_stop_active():
        stop_all()
    else:
        wheel_targets = kinematics.robot_to_wheel_velocities(
            system_state.target_vx,
            system_state.target_vy,
            system_state.target_wz,
        )
        system_state.update_wheel_targets(wheel_targets)

        dt = CONTROL_LOOP_PERIOD_MS / 1000.0
        for wheel_name in ('left', 'right', 'back'):
            count = encoders[wheel_name].get_count()
            system_state.encoder_counts[wheel_name] += count
            current_vel = count / dt
            encoders[wheel_name].reset()
            error = system_state.wheel_targets[wheel_name] - current_vel
            output = pid_controllers[wheel_name].update(error, dt)
            motors[wheel_name].set_speed(max(-1.0, min(1.0, output)))

    system_state.update_battery(read_battery_voltage())
    system_state.loop_count += 1

    if system_state.loop_count % STATUS_REPORT_INTERVAL == 0:
        uart_protocol.send_status(
            safety_system.is_emergency_stop_active(),
            timeout,
            system_state.get_mode(),
            system_state.encoder_counts["left"],
            system_state.encoder_counts["right"],
            system_state.encoder_counts["back"],
        )
        uart_protocol.send_rpm(0.0, 0.0, 0.0)  # TODO: compute true RPM from encoder counts


def main():
    pid_controllers = {
        'left': PIDController(),
        'right': PIDController(),
        'back': PIDController(),
    }
    watchdog.reset()

    while True:
        start = utime.ticks_ms()
        control_loop(pid_controllers)
        elapsed = utime.ticks_diff(utime.ticks_ms(), start)
        sleep_ms = CONTROL_LOOP_PERIOD_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)


if __name__ == '__main__':
    main()
