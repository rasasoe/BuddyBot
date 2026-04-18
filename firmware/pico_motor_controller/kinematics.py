"""Kinematics helpers for the real BuddyBot 3-wheel kiwi base."""

import math

from config import ROTATION_MIX_GAIN, WHEEL_ANGLES_DEG

class Kinematics:
    def __init__(self):
        self.wheel_angles_deg = WHEEL_ANGLES_DEG
        self.rotation_mix_gain = ROTATION_MIX_GAIN

    def robot_to_wheel_velocities(self, vx, vy, wz):
        """
        Convert robot velocities to wheel velocities
        vx: normalized forward velocity (ROS +x)
        vy: normalized lateral-left velocity (ROS +y)
        wz: normalized angular velocity
        Returns: dict of wheel velocities (left, right, back)
        """
        rotation = wz * self.rotation_mix_gain

        wheel_velocities = {}
        for wheel_name in ('left', 'right', 'back'):
            angle_rad = math.radians(self.wheel_angles_deg[wheel_name])
            wheel_velocities[wheel_name] = (
                math.cos(angle_rad) * vx
                + math.sin(angle_rad) * vy
                + rotation
            )

        max_mag = max(1.0, *(abs(value) for value in wheel_velocities.values()))
        for wheel_name in wheel_velocities:
            wheel_velocities[wheel_name] /= max_mag

        return wheel_velocities

    def wheel_to_robot_velocities(self, wheel_velocities):
        """
        Convert wheel velocities back to robot velocities (for odometry)
        wheel_velocities: dict of wheel velocities
        Returns: (vx, vy, wz)
        """
        # Forward solution is the field-critical path; keep inverse simple for now.
        left = wheel_velocities.get('left', 0.0)
        right = wheel_velocities.get('right', 0.0)
        back = wheel_velocities.get('back', 0.0)
        rotation = (left + right + back) / 3.0
        vx = (right - left) / 1.7320508075688772
        vy = (left + right - 2.0 * back) / 3.0
        wz = rotation / self.rotation_mix_gain if self.rotation_mix_gain else 0.0
        return vx, vy, wz

# Create kinematics instance
kinematics = Kinematics()
