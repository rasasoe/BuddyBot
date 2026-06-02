"""Kinematics helpers for the real BuddyBot 3-wheel kiwi base."""

from config import ROTATION_MIX_GAIN, STRAFE_BACK_WHEEL_GAIN, WHEEL_COMMAND_SIGNS

class Kinematics:
    def __init__(self):
        self.rotation_mix_gain = ROTATION_MIX_GAIN
        self.strafe_back_wheel_gain = STRAFE_BACK_WHEEL_GAIN
        self.wheel_command_signs = WHEEL_COMMAND_SIGNS

    def robot_to_wheel_velocities(self, vx, vy, wz):
        """
        Convert robot velocities to wheel velocities
        vx: normalized forward velocity (ROS +x)
        vy: normalized lateral-left velocity (ROS +y)
        wz: normalized angular velocity
        Returns: dict of wheel velocities (left, right, back)
        """
        # Restore the legacy direct mix that was previously field-proven on the
        # same BuddyBot chassis before the ROS-integrated refactor. This keeps
        # the original January channel order:
        #   left  -> v0
        #   right -> v1
        #   back  -> v2
        # and exposes per-wheel sign hooks for field polarity tweaks.
        rotation = wz * self.rotation_mix_gain

        wheel_velocities = {
            "left": (vx + 0.5 * vy + rotation) * self.wheel_command_signs["left"],
            "right": (-vx + 0.5 * vy + rotation) * self.wheel_command_signs["right"],
            "back": (-vy * self.strafe_back_wheel_gain + rotation) * self.wheel_command_signs["back"],
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
        left = wheel_velocities.get('left', 0.0) / self.wheel_command_signs['left']
        right = wheel_velocities.get('right', 0.0) / self.wheel_command_signs['right']
        back = wheel_velocities.get('back', 0.0) / self.wheel_command_signs['back']
        front_average = (left + right) / 2.0
        vx = (left - right) / 2.0
        vy = (front_average - back) / (self.strafe_back_wheel_gain + 0.5)
        rotation = front_average - 0.5 * vy
        wz = rotation / self.rotation_mix_gain if self.rotation_mix_gain else 0.0
        return vx, vy, wz

# Create kinematics instance
kinematics = Kinematics()
