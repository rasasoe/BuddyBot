"""BuddyBot Pico firmware entrypoint (deploy this as /main.py on Pico)."""

import utime

from config import (
    BATTERY_VOLTAGE_DIVIDER_RATIO,
    COMMAND_ZERO_DEADBAND,
    CONTROL_LOOP_PERIOD_MS,
    MAX_RPM_EST,
    MOTOR_OUTPUT_SLEW_DOWN,
    MOTOR_OUTPUT_SLEW_REVERSAL,
    MOTOR_OUTPUT_SLEW_UP,
    OUTPUT_CPR,
    PID_CORR_MAX,
    STATUS_REPORT_INTERVAL,
)
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


def reset_all_pid(pid_controllers):
    for controller in pid_controllers.values():
        controller.reset()


def reset_applied_outputs(applied_outputs):
    for wheel_name in applied_outputs:
        applied_outputs[wheel_name] = 0.0


def targets_are_zero():
    return (
        abs(system_state.target_vx) <= COMMAND_ZERO_DEADBAND
        and abs(system_state.target_vy) <= COMMAND_ZERO_DEADBAND
        and abs(system_state.target_wz) <= COMMAND_ZERO_DEADBAND
    )


def ramp_output(current, target):
    if current * target < 0.0:
        step = MOTOR_OUTPUT_SLEW_REVERSAL
    elif abs(target) > abs(current):
        step = MOTOR_OUTPUT_SLEW_UP
    else:
        step = MOTOR_OUTPUT_SLEW_DOWN

    delta = target - current
    if delta > step:
        return current + step
    if delta < -step:
        return current - step
    return target


def control_loop(pid_controllers, applied_outputs):
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
        safety_system.clear_emergency_stop()
        uart_protocol.send_ack('CLEAR')
    elif command_type is None and params is None:
        pass

    safety_system.check_emergency_stop_pin()
    timeout = watchdog.is_timed_out()
    safety_system.check_watchdog_timeout(timeout)

    if safety_system.is_emergency_stop_active():
        reset_all_pid(pid_controllers)
        reset_applied_outputs(applied_outputs)
        stop_all()
    elif targets_are_zero():
        system_state.update_wheel_targets({'left': 0.0, 'right': 0.0, 'back': 0.0})
        reset_all_pid(pid_controllers)
        reset_applied_outputs(applied_outputs)
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
            rev_per_sec = (count / OUTPUT_CPR) / dt if dt > 0 else 0.0
            current_rpm = rev_per_sec * 60.0
            measured_drive = max(-2.0, min(2.0, current_rpm / MAX_RPM_EST))
            encoders[wheel_name].reset()
            base_drive = system_state.wheel_targets[wheel_name]
            if abs(base_drive) < COMMAND_ZERO_DEADBAND:
                pid_controllers[wheel_name].reset()
                applied_outputs[wheel_name] = 0.0
                motors[wheel_name].set_speed(0.0)
                continue
            error = base_drive - measured_drive
            correction = pid_controllers[wheel_name].update(error, dt)
            correction = max(-PID_CORR_MAX, min(PID_CORR_MAX, correction))
            target_output = max(-1.0, min(1.0, base_drive + correction))
            applied_output = ramp_output(applied_outputs[wheel_name], target_output)
            applied_outputs[wheel_name] = applied_output
            motors[wheel_name].set_speed(applied_output)

    system_state.update_battery(read_battery_voltage())
    system_state.loop_count += 1

    if system_state.loop_count % STATUS_REPORT_INTERVAL == 0:
        uart_protocol.send_status(
            safety_system.is_emergency_stop_active(),
            timeout,
            system_state.get_mode(),
        )
        uart_protocol.send_rpm(0.0, 0.0, 0.0)  # TODO: wire true wheel RPM telemetry


def main():
    pid_controllers = {
        'left': PIDController(),
        'right': PIDController(),
        'back': PIDController(),
    }
    applied_outputs = {'left': 0.0, 'right': 0.0, 'back': 0.0}
    watchdog.reset()

    while True:
        start = utime.ticks_ms()
        control_loop(pid_controllers, applied_outputs)
        elapsed = utime.ticks_diff(utime.ticks_ms(), start)
        sleep_ms = CONTROL_LOOP_PERIOD_MS - elapsed
        if sleep_ms > 0:
            utime.sleep_ms(sleep_ms)


if __name__ == '__main__':
    main()
