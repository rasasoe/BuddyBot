"""
BuddyBot State Management

This module manages the current state of the motor controller.
"""

class SystemState:
    def __init__(self):
        # Current velocity commands from Pi 5
        self.target_vx = 0.0
        self.target_vy = 0.0
        self.target_wz = 0.0

        # Wheel target velocities (calculated from kinematics)
        self.wheel_targets = {
            'left': 0.0,
            'right': 0.0,
            'back': 0.0
        }

        # Current encoder counts
        self.encoder_counts = {
            'left': 0,
            'right': 0,
            'back': 0
        }

        # Battery voltage
        self.battery_voltage = 0.0

        # Control loop timing
        self.last_loop_time = 0
        self.loop_count = 0

        # Operating mode
        self.mode = 'NORMAL'  # NORMAL, SAFE, MANUAL

    def update_targets(self, vx, vy, wz):
        """Update velocity targets"""
        self.target_vx = vx
        self.target_vy = vy
        self.target_wz = wz

    def update_wheel_targets(self, wheel_targets):
        """Update wheel velocity targets"""
        self.wheel_targets = wheel_targets

    def update_encoders(self, encoder_counts):
        """Update encoder counts"""
        self.encoder_counts = encoder_counts

    def update_battery(self, voltage):
        """Update battery voltage"""
        self.battery_voltage = voltage

    def set_mode(self, mode):
        """Set operating mode"""
        valid_modes = ['NORMAL', 'SAFE', 'MANUAL']
        if mode in valid_modes:
            self.mode = mode

    def get_mode(self):
        """Get current operating mode"""
        return self.mode

    def get_status_dict(self):
        """Get status as dictionary for reporting"""
        return {
            'battery_voltage': self.battery_voltage,
            'encoder_counts': self.encoder_counts.copy(),
            'emergency_stop': False,  # This will be set by safety system
            'mode': self.mode
        }

# Create system state instance
system_state = SystemState()