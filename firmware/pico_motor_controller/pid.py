"""
BuddyBot PID Controller

This module implements a PID controller for motor speed control.
"""

from config import PID_KP, PID_KI, PID_KD

class PIDController:
    def __init__(self, kp=PID_KP, ki=PID_KI, kd=PID_KD):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.prev_error = 0.0
        self.integral = 0.0
        self.integral_limit = 1.0  # Prevent integral windup

    def update(self, error, dt):
        """
        Calculate PID output
        error: current error (target - measured)
        dt: time delta in seconds
        Returns: control output (-1.0 to 1.0)
        """
        # Proportional term
        p_term = self.kp * error

        # Integral term with windup protection
        self.integral += error * dt
        self.integral = max(-self.integral_limit, min(self.integral_limit, self.integral))
        i_term = self.ki * self.integral

        # Derivative term
        derivative = (error - self.prev_error) / dt if dt > 0 else 0
        d_term = self.kd * derivative

        # Calculate output
        output = p_term + i_term + d_term

        # Store for next iteration
        self.prev_error = error

        return output

    def reset(self):
        """Reset controller state"""
        self.prev_error = 0.0
        self.integral = 0.0