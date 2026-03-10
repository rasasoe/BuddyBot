"""
BuddyBot Kinematics

This module handles conversion between robot velocities and wheel velocities
for a 3-wheel omnidirectional drive.
"""

import math
from config import WHEEL_BASE_WIDTH, WHEEL_BASE_LENGTH

class Kinematics:
    def __init__(self):
        # Wheel positions relative to robot center
        # Assuming: left wheel at (-width/2, 0), right at (width/2, 0), back at (0, -length)
        self.wheel_positions = {
            'left': (-WHEEL_BASE_WIDTH/2, 0),
            'right': (WHEEL_BASE_WIDTH/2, 0),
            'back': (0, -WHEEL_BASE_LENGTH)
        }

    def robot_to_wheel_velocities(self, vx, vy, wz):
        """
        Convert robot velocities to wheel velocities
        vx: forward velocity (m/s)
        vy: lateral velocity (m/s)
        wz: angular velocity (rad/s)
        Returns: dict of wheel velocities (left, right, back)
        """
        wheel_velocities = {}

        for wheel_name, (x, y) in self.wheel_positions.items():
            # For omnidirectional wheels, velocity = vx + vy + wz × r
            # where r is the perpendicular distance from wheel to ICR
            # For 3-wheel drive, simplified kinematics
            if wheel_name == 'left':
                # Left wheel: opposes lateral movement
                wheel_velocities[wheel_name] = vx - vy - wz * (WHEEL_BASE_WIDTH/2)
            elif wheel_name == 'right':
                # Right wheel: opposes lateral movement
                wheel_velocities[wheel_name] = vx + vy - wz * (WHEEL_BASE_WIDTH/2)
            elif wheel_name == 'back':
                # Back wheel: handles forward/backward and rotation
                wheel_velocities[wheel_name] = vy + wz * WHEEL_BASE_LENGTH

        return wheel_velocities

    def wheel_to_robot_velocities(self, wheel_velocities):
        """
        Convert wheel velocities back to robot velocities (for odometry)
        wheel_velocities: dict of wheel velocities
        Returns: (vx, vy, wz)
        """
        # This is the inverse kinematics - more complex for odometry
        # Simplified version for now
        vl = wheel_velocities.get('left', 0)
        vr = wheel_velocities.get('right', 0)
        vb = wheel_velocities.get('back', 0)

        # Approximate inverse (this needs proper matrix inversion for accuracy)
        vx = (vl + vr) / 2
        vy = (vr - vl) / 2 + vb
        wz = -(vr + vl) / WHEEL_BASE_WIDTH  # Approximate

        return vx, vy, wz

# Create kinematics instance
kinematics = Kinematics()