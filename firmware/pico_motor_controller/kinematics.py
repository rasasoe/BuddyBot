"""
BuddyBot Kinematics

This module handles conversion between robot velocities and wheel velocities
for a 3-wheel omnidirectional drive.
"""

from config import ROTATION_MIX_GAIN, WHEEL_BASE_LENGTH, WHEEL_BASE_WIDTH

class Kinematics:
    def __init__(self):
        # Wheel positions relative to robot center
        # Assuming: left wheel at (-width/2, 0), right at (width/2, 0), back at (0, -length)
        self.wheel_positions = {
            'left': (-WHEEL_BASE_WIDTH/2, 0),
            'right': (WHEEL_BASE_WIDTH/2, 0),
            'back': (0, -WHEEL_BASE_LENGTH)
        }
        self.rotation_mix_gain = ROTATION_MIX_GAIN

    def robot_to_wheel_velocities(self, vx, vy, wz):
        """
        Convert robot velocities to wheel velocities
        vx: normalized forward velocity
        vy: normalized lateral velocity
        wz: normalized angular velocity
        Returns: dict of wheel velocities (left, right, back)
        """
        # Keep the existing translation feel, but mix rotation in normalized
        # command space. The previous implementation multiplied angular.z by the
        # physical base dimensions, which reduced pure rotation to about 10% of
        # the translational command magnitude and made rotate-in-place appear dead.
        left = vx - vy - (wz * self.rotation_mix_gain)
        right = vx + vy - (wz * self.rotation_mix_gain)
        back = vy + (wz * self.rotation_mix_gain)

        max_mag = max(1.0, abs(left), abs(right), abs(back))
        wheel_velocities = {
            'left': left / max_mag,
            'right': right / max_mag,
            'back': back / max_mag,
        }

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

        vy = (vr - vl) / 2
        if self.rotation_mix_gain != 0:
            wz = (vb - vy) / self.rotation_mix_gain
        else:
            wz = 0.0
        vx = ((vl + vr) / 2) + (wz * self.rotation_mix_gain)

        return vx, vy, wz

# Create kinematics instance
kinematics = Kinematics()
