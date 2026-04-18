"""Kinematics helpers for the real BuddyBot 3-wheel kiwi base."""

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
        # Restore the legacy direct mix that was previously field-proven on the
        # same BuddyBot chassis before the ROS-integrated refactor. With the
        # current semantic aliases:
        #   right -> motor0
        #   left  -> motor1
        #   back  -> motor2
        # this preserves the original:
        #   v0 =  vx + 0.5 * vy + w
        #   v1 = -vx + 0.5 * vy + w
        #   v2 = -vy + w
        rotation = wz * self.rotation_mix_gain

        wheel_velocities = {
            "right": vx + 0.5 * vy + rotation,
            "left": -vx + 0.5 * vy + rotation,
            "back": -vy + rotation,
        }

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
        vx = (right - left) / 2.0
        vy = (left + right - 2.0 * back) / 3.0
        wz = rotation / self.rotation_mix_gain if self.rotation_mix_gain else 0.0
        return vx, vy, wz

# Create kinematics instance
kinematics = Kinematics()
