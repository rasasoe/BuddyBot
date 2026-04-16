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

# PID gains (tune these for your motors)
PID_KP = 1.0
PID_KI = 0.1
PID_KD = 0.05

# Motor speed limits (-1.0 to 1.0)
MAX_MOTOR_SPEED = 1.0
MIN_MOTOR_SPEED = -1.0

# Per-wheel motor polarity correction for the real BuddyBot wiring.
# Keep these as +/-1 so field fixes can be made without rewiring or
# changing the higher-level kinematics. Current field symptom was that
# pure forward commands spun in place, which most strongly suggested the
# front-right motor direction was inverted relative to the software model.
MOTOR_DIRECTION_SIGNS = {
    'left': 1,
    'right': -1,
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

# Manual teleop and ROS cmd_vel values are already normalized to roughly [-1, 1]
# before they reach the Pico. Keep the rotational term in the same normalized
# space so pure rotation does not get scaled down into a barely moving command.
ROTATION_MIX_GAIN = 1.5

# Status reporting interval (control loops)
STATUS_REPORT_INTERVAL = 5  # Every 5 control loops (100ms at 50Hz)
