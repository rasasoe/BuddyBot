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
PID_KP = 0.3
PID_KI = 0.0
PID_KD = 0.0

# Legacy closed-loop tuning from the pre-ROS Pico controller.
MAX_RPM_EST = 60.0
PID_CORR_MAX = 0.30

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
    'left': 1,
    'right': 1,
    'back': 1,
}

# Battery ADC settings
BATTERY_ADC_PIN = 26
BATTERY_VOLTAGE_DIVIDER_RATIO = 2.0  # Assuming voltage divider

# Encoder constants from the field-proven standalone Pico controller.
ENCODER_CPR = 11
GEAR_RATIO = 270
OUTPUT_CPR = ENCODER_CPR * GEAR_RATIO

# Wheel radius (meters) - for velocity calculation
WHEEL_RADIUS = 0.05

# Robot geometry for kinematics (meters)
WHEEL_BASE_WIDTH = 0.2  # Distance between left/right wheels
WHEEL_BASE_LENGTH = 0.15  # Distance from back wheel to front axle

# Legacy direct-mix sign hooks. Keep the January motor channel order intact and
# flip individual wheel commands here if a specific wheel is physically
# "green-onion" / backwards on the real robot.
WHEEL_COMMAND_SIGNS = {
    'left': 1.0,
    'right': 1.0,
    'back': 1.0,
}

# Keep rotational commands in the same normalized space as vx/vy.
ROTATION_MIX_GAIN = 1.5

# Status reporting interval (control loops)
STATUS_REPORT_INTERVAL = 5  # Every 5 control loops (100ms at 50Hz)
