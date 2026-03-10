"""
BuddyBot Pico Main Script - Modular Motor Controller

This is the main entry point for the BuddyBot motor controller.
It orchestrates all modules to provide safe, responsive motor control.

Execution Flow:
1. Initialize all modules
2. Main control loop at fixed frequency (50Hz)
   a. Parse incoming UART commands
   b. Check safety systems (watchdog, estop)
   c. Update kinematics and PID control
   d. Send status reports periodically
3. Handle emergency stops and timeouts

Assumptions:
- Hardware is properly connected as per pins.py
- PID gains in config.py are tuned for the specific motors
- UART protocol matches Pi 5 implementation
- Control loop runs fast enough for real-time response

TODO:
- Add proper timing measurement for loop frequency
- Implement odometry calculation
- Add motor current sensing for overload protection
- Tune PID gains for specific robot
- Add LED status indicators
"""

import machine
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
    """Read battery voltage from ADC"""
    adc_value = battery_adc.read_u16()
    voltage = (adc_value / 65535) * 3.3 * BATTERY_VOLTAGE_DIVIDER_RATIO
    return voltage

def update_encoders():
    """Update encoder counts in system state"""
    counts = {}
    for name, encoder in encoders.items():
        counts[name] = encoder.get_count()
    system_state.update_encoders(counts)

def control_loop():
    """Main control loop - runs at fixed frequency"""
    global loop_count

    current_time = utime.ticks_ms()

    # 1. Parse incoming commands
    command_type, params = uart_protocol.parse_command()
    if command_type:
        if command_type == 'HB':
            # Heartbeat - just acknowledge
            uart_protocol.send_ack('HB')
            watchdog.feed()  # Valid command received
        elif command_type == 'CMD':
            # Velocity command
            vx = params['vx']
            vy = params['vy']
            wz = params['wz']
            system_state.update_targets(vx, vy, wz)
            uart_protocol.send_ack('CMD')
            watchdog.feed()  # Valid command received
        elif command_type == 'BRAKE':
            # Emergency brake
            safety_system.activate_emergency_stop()
            uart_protocol.send_ack('BRAKE')
            uart_protocol.send_safety_event('brake_command')
        elif command_type == 'CLEAR':
            # Clear emergency stop
            safety_system.clear_emergency_stop()
            uart_protocol.send_ack('CLEAR')
        elif command_type == 'MODE':
            # Mode change
            mode = params['mode']
            system_state.set_mode(mode)
            uart_protocol.send_ack('MODE')

    # 2. Check safety systems
    safety_system.check_emergency_stop_pin()
    safety_system.check_watchdog_timeout(watchdog.is_timed_out())

    # 3. If emergency stop active, skip motor control
    if safety_system.is_emergency_stop_active():
        # Motors already stopped by safety system
        pass
    else:
        # 4. Update kinematics (robot velocities -> wheel velocities)
        wheel_targets = kinematics.robot_to_wheel_velocities(
            system_state.target_vx,
            system_state.target_vy,
            system_state.target_wz
        )
        system_state.update_wheel_targets(wheel_targets)

        # 5. Run PID control for each wheel
        dt = CONTROL_LOOP_PERIOD_MS / 1000.0  # Convert to seconds
        for wheel_name in ['left', 'right', 'back']:
            target_vel = system_state.wheel_targets[wheel_name]
            # TODO: Calculate actual velocity from encoders
            # For now, assume encoders give velocity directly
            current_vel = encoders[wheel_name].get_count() / dt  # Placeholder
            encoders[wheel_name].reset()  # Reset for next measurement

            error = target_vel - current_vel
            pid_output = pid_controllers[wheel_name].update(error, dt)

            # Clamp PID output
            motor_speed = max(-1.0, min(1.0, pid_output))
            motors[wheel_name].set_speed(motor_speed)

    # 6. Update system state
    update_encoders()
    battery_voltage = read_battery_voltage()
    system_state.update_battery(battery_voltage)

    # 7. Send status report periodically
    system_state.loop_count += 1
    if system_state.loop_count % STATUS_REPORT_INTERVAL == 0:
        # Send status report
        estop = safety_system.is_emergency_stop_active()
        timeout = watchdog.is_timed_out()
        mode = system_state.get_mode()
        uart_protocol.send_status(estop, timeout, mode)

        # Send RPM summary (placeholder values for now)
        # TODO: Calculate actual RPM from encoders
        uart_protocol.send_rpm(0, 0, 0)

def main():
    """Main function - initialize and run control loop"""
    print("BuddyBot Pico Motor Controller Starting...")

    # Initialize PID controllers for each wheel
    global pid_controllers
    pid_controllers = {
        'left': PIDController(),
        'right': PIDController(),
        'back': PIDController()
    }

    # Initialize timing
    global loop_count
    loop_count = 0

    print("Initialization complete. Starting control loop...")

    # Main control loop
    while True:
        loop_start = utime.ticks_ms()
        control_loop()
        loop_end = utime.ticks_ms()

        # Calculate sleep time to maintain loop frequency
        loop_duration = utime.ticks_diff(loop_end, loop_start)
        sleep_time = max(0, CONTROL_LOOP_PERIOD_MS - loop_duration)
        utime.sleep_ms(sleep_time)

if __name__ == '__main__':
    main()