"""Kinematics helpers for the real BuddyBot 3-wheel base."""

# Wheel layout (viewed from above):
#   left  : front-left side of the tuned field layout
#   right : front-right side of the tuned field layout
#   back  : rear wheel
# Positive wz = counter-clockwise (ROS convention)
# Adjust ROTATION_MIX_GAIN in config.py if rotation is still weak on hardware.

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
        # Keep the translation feel the team already tuned in the field, but
        # correct the rotation contribution so positive angular.z means a real
        # left turn and can spin in place.
        #
        # The previous mixer applied the same rotation sign to the left and
        # right wheels, which caused arc-like motion and "rotate only while
        # moving forward" behavior on the real base. Field behavior matched a
        # front pair that must oppose each other for yaw, while the rear wheel
        # should share the left wheel's sign for a clean in-place spin.
        rotation = wz * self.rotation_mix_gain
        left = vx - vy - rotation
        right = vx + vy + rotation
        back = vy - rotation

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
