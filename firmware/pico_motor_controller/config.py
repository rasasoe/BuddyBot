"""
BuddyBot Pico Configuration

This module contains all configuration constants for the motor controller.
"""

# Control loop frequency (Hz)
CONTROL_LOOP_HZ = 50
CONTROL_LOOP_PERIOD_MS = 1000 // CONTROL_LOOP_HZ  # 20ms for 50Hz

# UART settings - Using USB serial, not GPIO UART
# Communication with Pi 5 is via USB serial (/dev/ttyACM0 on Pi 5)
# No GPIO UART pins needed - Pico appears as USB CDC device
UART_BAUDRATE = 115200

# Note: UART_ID and UART_TX/RX pins are not used for USB serial communication
# The Pico firmware communicates via USB serial interface

# Watchdog timeout (ms)
WATCHDOG_TIMEOUT_MS = 1000

# Demo-first motor control gains.
# Keep BuddyBot on P-only control for now because the current field setup
# still has noisy/limited encoder feedback, and I/D terms caused stop lag
# and oscillation risks during live testing. This matches the simpler AMR
# reference controller that only tunes kp in the field.
PID_KP = 0.6
PID_KI = 0.0
PID_KD = 0.0

# Motor speed limits (-1.0 to 1.0)
MAX_MOTOR_SPEED = 1.0
MIN_MOTOR_SPEED = -1.0

# Treat very small command magnitudes as an explicit stop so the firmware
# can bypass PID holdover and drop motor output immediately.
COMMAND_ZERO_DEADBAND = 0.02

# Per-wheel motor polarity correction for the real BuddyBot wiring.
# Keep these as +/-1 so field fixes can be made without rewiring or
# changing the higher-level kinematics. After comparing against the
# working AMR reference (same GP2/8/12 motor order), the safer starting
# point is to keep all wheels aligned and solve motion mix issues in the
# kinematics layer rather than by flipping one wheel ad hoc.
MOTOR_DIRECTION_SIGNS = {
    'left': -1,
    'right': 1,
    'back': 1,
}

# Battery ADC settings
BATTERY_ADC_PIN = 26
BATTERY_VOLTAGE_DIVIDER_RATIO = 2.0  # Assuming voltage divider

# Encoder counts per revolution (adjust for your encoders)
ENCODER_CPR = 360  # Example value

# Wheel radius (meters) - for velocity calculation
WHEEL_RADIUS = 0.05

# Robot geometry for kinematics (meters)
WHEEL_BASE_WIDTH = 0.2  # Distance between left/right wheels
WHEEL_BASE_LENGTH = 0.15  # Distance from back wheel to front axle

# Wheel drive-direction angles for BuddyBot's kiwi base in the ROS body frame
# (x=forward, y=left). The robot's forward axis is defined as the direction
# pointing outward from the midpoint between the physical left/right wheels.
# With that definition, pure forward should be produced mainly by the front
# left/right pair while the back wheel contribution stays near zero.
WHEEL_ANGLES_DEG = {
    'left': 150.0,
    'right': 30.0,
    'back': 270.0,
}

# Manual teleop and ROS cmd_vel values are already normalized to roughly [-1, 1]
# before they reach the Pico. Keep the rotational term in the same normalized
# space so pure rotation does not get scaled down into a barely moving command.
ROTATION_MIX_GAIN = 1.5

# Status reporting interval (control loops)
STATUS_REPORT_INTERVAL = 5  # Every 5 control loops (100ms at 50Hz)
