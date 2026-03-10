"""
BuddyBot Pico Main Script

This is the spinal cord of BuddyBot: motor control, encoders, PID control, watchdog, safety stop.
Runs on Raspberry Pi Pico with MicroPython.
Safety: Implements watchdog timeout and emergency stop latch independent of Pi 5.
"""

import machine
import utime
import struct

# Pins
MOTOR_LEFT_PWM = machine.PWM(machine.Pin(0))
MOTOR_LEFT_DIR1 = machine.Pin(1, machine.Pin.OUT)
MOTOR_LEFT_DIR2 = machine.Pin(2, machine.Pin.OUT)

MOTOR_RIGHT_PWM = machine.PWM(machine.Pin(3))
MOTOR_RIGHT_DIR1 = machine.Pin(4, machine.Pin.OUT)
MOTOR_RIGHT_DIR2 = machine.Pin(5, machine.Pin.OUT)

MOTOR_BACK_PWM = machine.PWM(machine.Pin(6))
MOTOR_BACK_DIR1 = machine.Pin(7, machine.Pin.OUT)
MOTOR_BACK_DIR2 = machine.Pin(8, machine.Pin.OUT)

ENC_LEFT_A = machine.Pin(9, machine.Pin.IN)
ENC_LEFT_B = machine.Pin(10, machine.Pin.IN)

ENC_RIGHT_A = machine.Pin(11, machine.Pin.IN)
ENC_RIGHT_B = machine.Pin(12, machine.Pin.IN)

ENC_BACK_A = machine.Pin(13, machine.Pin.IN)
ENC_BACK_B = machine.Pin(14, machine.Pin.IN)

EMERGENCY_STOP_PIN = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)

# UART for communication with Pi 5
uart = machine.UART(0, baudrate=115200, tx=machine.Pin(16), rx=machine.Pin(17))

# ADC for battery
adc_battery = machine.ADC(machine.Pin(26))

# PID controllers
class PID:
    def __init__(self, kp, ki, kd):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.prev_error = 0
        self.integral = 0
    
    def update(self, error, dt):
        self.integral += error * dt
        derivative = (error - self.prev_error) / dt
        output = self.kp * error + self.ki * self.integral + self.kd * derivative
        self.prev_error = error
        return output

# Motor control
def set_motor_speed(pwm, dir1, dir2, speed):
    pwm.freq(1000)
    if speed > 0:
        dir1.value(1)
        dir2.value(0)
    elif speed < 0:
        dir1.value(0)
        dir2.value(1)
        speed = -speed
    else:
        dir1.value(0)
        dir2.value(0)
    pwm.duty_u16(int(speed * 65535))

# Encoders
enc_left_count = 0
enc_right_count = 0
enc_back_count = 0

def enc_left_callback(pin):
    global enc_left_count
    if ENC_LEFT_B.value():
        enc_left_count += 1
    else:
        enc_left_count -= 1

def enc_right_callback(pin):
    global enc_right_count
    if ENC_RIGHT_B.value():
        enc_right_count += 1
    else:
        enc_right_count -= 1

def enc_back_callback(pin):
    global enc_back_count
    if ENC_BACK_B.value():
        enc_back_count += 1
    else:
        enc_back_count -= 1

ENC_LEFT_A.irq(trigger=machine.Pin.IRQ_RISING, handler=enc_left_callback)
ENC_RIGHT_A.irq(trigger=machine.Pin.IRQ_RISING, handler=enc_right_callback)
ENC_BACK_A.irq(trigger=machine.Pin.IRQ_RISING, handler=enc_back_callback)

# Main loop
last_time = utime.ticks_ms()
last_heartbeat = utime.ticks_ms()
watchdog_timeout = 1000  # ms

pid_left = PID(1.0, 0.1, 0.05)
pid_right = PID(1.0, 0.1, 0.05)
pid_back = PID(1.0, 0.1, 0.05)

target_linear_x = 0.0
target_linear_y = 0.0
target_angular_z = 0.0

emergency_stop = False

while True:
    current_time = utime.ticks_ms()
    dt = utime.ticks_diff(current_time, last_time) / 1000.0
    last_time = current_time
    
    # Check emergency stop
    if EMERGENCY_STOP_PIN.value() == 0 or emergency_stop:
        set_motor_speed(MOTOR_LEFT_PWM, MOTOR_LEFT_DIR1, MOTOR_LEFT_DIR2, 0)
        set_motor_speed(MOTOR_RIGHT_PWM, MOTOR_RIGHT_DIR1, MOTOR_RIGHT_DIR2, 0)
        set_motor_speed(MOTOR_BACK_PWM, MOTOR_BACK_DIR1, MOTOR_BACK_DIR2, 0)
        emergency_stop = True
        continue
    
    # Check watchdog
    if utime.ticks_diff(current_time, last_heartbeat) > watchdog_timeout:
        self.get_logger().warn('Watchdog timeout - emergency stop')
        emergency_stop = True
        continue
    
    # Read commands from UART
    if uart.any():
        data = uart.read(12)  # 3 floats
        if len(data) == 12:
            target_linear_x, target_linear_y, target_angular_z = struct.unpack('fff', data)
            last_heartbeat = current_time
    
    # Omni-wheel kinematics (simplified)
    # For 3-wheel omni: front-left, front-right, back
    v_left = target_linear_x - target_linear_y - target_angular_z * 0.5
    v_right = target_linear_x + target_linear_y - target_angular_z * 0.5
    v_back = target_linear_y + target_angular_z * 0.5
    
    # PID control (simplified, assuming encoder gives velocity)
    # In reality, need to calculate velocity from encoder counts
    error_left = v_left - (enc_left_count / dt)  # Placeholder
    error_right = v_right - (enc_right_count / dt)
    error_back = v_back - (enc_back_count / dt)
    
    pwm_left = pid_left.update(error_left, dt)
    pwm_right = pid_right.update(error_right, dt)
    pwm_back = pid_back.update(error_back, dt)
    
    # Clamp to [-1, 1]
    pwm_left = max(-1, min(1, pwm_left))
    pwm_right = max(-1, min(1, pwm_right))
    pwm_back = max(-1, min(1, pwm_back))
    
    set_motor_speed(MOTOR_LEFT_PWM, MOTOR_LEFT_DIR1, MOTOR_LEFT_DIR2, pwm_left)
    set_motor_speed(MOTOR_RIGHT_PWM, MOTOR_RIGHT_DIR1, MOTOR_RIGHT_DIR2, pwm_right)
    set_motor_speed(MOTOR_BACK_PWM, MOTOR_BACK_DIR1, MOTOR_BACK_DIR2, pwm_back)
    
    # Send status
    battery = adc_battery.read_u16() / 65535 * 3.3 * 2  # Assuming voltage divider
    status_data = struct.pack('fiii?', battery, enc_left_count, enc_right_count, enc_back_count, emergency_stop)
    uart.write(status_data)
    
    # Reset encoder counts for next cycle
    enc_left_count = 0
    enc_right_count = 0
    enc_back_count = 0
    
    utime.sleep_ms(100)