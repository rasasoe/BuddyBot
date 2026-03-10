"""
BuddyBot Pico Configuration

This module contains all configuration constants for the motor controller.
"""

# Control loop frequency (Hz)
CONTROL_LOOP_HZ = 50
CONTROL_LOOP_PERIOD_MS = 1000 // CONTROL_LOOP_HZ  # 20ms for 50Hz

# UART settings
UART_ID = 0
UART_BAUDRATE = 115200
UART_TX_PIN = 16
UART_RX_PIN = 17

# Watchdog timeout (ms)
WATCHDOG_TIMEOUT_MS = 1000

# PID gains (tune these for your motors)
PID_KP = 1.0
PID_KI = 0.1
PID_KD = 0.05

# Motor speed limits (-1.0 to 1.0)
MAX_MOTOR_SPEED = 1.0
MIN_MOTOR_SPEED = -1.0

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

# Status reporting interval (control loops)
STATUS_REPORT_INTERVAL = 5  # Every 5 control loops (100ms at 50Hz)