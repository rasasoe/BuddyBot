#!/usr/bin/env python3
"""
USB Serial Protocol Test Script

This script tests the text-based USB serial protocol implementation.
Can be used to simulate Pi 5 communication with Pico or test real hardware.
"""

import serial
import time
import threading
import sys

class USBSerialTester:
    def __init__(self, port='/dev/ttyACM0', baud=115200):
        self.port = port
        self.baud = baud
        self.serial = None
        self.running = True

    def connect(self):
        """Connect to USB serial port"""
        try:
            self.serial = serial.Serial(self.port, self.baud, timeout=0.1)
            print(f"Connected to {self.port} at {self.baud} baud")
            return True
        except serial.SerialException as e:
            print(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Disconnect from USB serial port"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            print("Disconnected")

    def send_command(self, command):
        """Send a command to Pico"""
        if not self.serial or not self.serial.is_open:
            print("Not connected")
            return

        try:
            self.serial.write((command + '\n').encode('utf-8'))
            print(f"Sent: {command}")
        except Exception as e:
            print(f"Send error: {e}")

    def receive_loop(self):
        """Background thread to receive messages"""
        buffer = ""
        while self.running:
            try:
                if self.serial and self.serial.in_waiting:
                    data = self.serial.read(self.serial.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data

                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            print(f"Received: {line}")

                time.sleep(0.01)
            except Exception as e:
                print(f"Receive error: {e}")
                time.sleep(0.1)

    def interactive_mode(self):
        """Interactive command mode"""
        print("USB Serial Protocol Test - Interactive Mode")
        print("Available commands:")
        print("  hb           - Send heartbeat")
        print("  cmd vx vy wz - Send velocity command (e.g., cmd 0.5 0 0.2)")
        print("  brake        - Send emergency brake")
        print("  clear        - Clear emergency stop")
        print("  mode MODE    - Change mode (NORMAL, SAFE, MANUAL)")
        print("  quit         - Exit")
        print()

        # Start receive thread
        receive_thread = threading.Thread(target=self.receive_loop)
        receive_thread.daemon = True
        receive_thread.start()

        try:
            while self.running:
                cmd = input("Command> ").strip()
                if not cmd:
                    continue

                parts = cmd.split()
                cmd_type = parts[0].lower()

                if cmd_type == 'quit':
                    break
                elif cmd_type == 'hb':
                    self.send_command("HB")
                elif cmd_type == 'brake':
                    self.send_command("BRAKE")
                elif cmd_type == 'clear':
                    self.send_command("CLEAR")
                elif cmd_type == 'cmd' and len(parts) == 4:
                    try:
                        vx, vy, wz = map(float, parts[1:])
                        self.send_command(f"CMD,{vx:.3f},{vy:.3f},{wz:.3f}")
                    except ValueError:
                        print("Invalid velocity values")
                elif cmd_type == 'mode' and len(parts) == 2:
                    mode = parts[1].upper()
                    if mode in ['NORMAL', 'SAFE', 'MANUAL']:
                        self.send_command(f"MODE,{mode}")
                    else:
                        print("Invalid mode. Use NORMAL, SAFE, or MANUAL")
                else:
                    print("Unknown command")

        except KeyboardInterrupt:
            print("\nInterrupted")
        finally:
            self.running = False

    def demo_mode(self):
        """Automated demo sequence"""
        print("USB Serial Protocol Test - Demo Mode")
        print("Running automated test sequence...")

        # Start receive thread
        receive_thread = threading.Thread(target=self.receive_loop)
        receive_thread.daemon = True
        receive_thread.start()

        try:
            # Demo sequence
            time.sleep(1)
            print("1. Sending heartbeat...")
            self.send_command("HB")
            time.sleep(2)

            print("2. Sending velocity command...")
            self.send_command("CMD,0.500,0.000,0.200")
            time.sleep(2)

            print("3. Sending brake command...")
            self.send_command("BRAKE")
            time.sleep(2)

            print("4. Clearing emergency stop...")
            self.send_command("CLEAR")
            time.sleep(2)

            print("5. Changing to SAFE mode...")
            self.send_command("MODE,SAFE")
            time.sleep(2)

            print("6. Changing back to NORMAL mode...")
            self.send_command("MODE,NORMAL")
            time.sleep(2)

            print("Demo complete!")

        except KeyboardInterrupt:
            print("\nDemo interrupted")
        finally:
            self.running = False

def main():
    import argparse

    parser = argparse.ArgumentParser(description='USB Serial Protocol Tester')
    parser.add_argument('--port', default='/dev/ttyACM0', help='USB serial port (default: /dev/ttyACM0)')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate (default: 115200)')
    parser.add_argument('--demo', action='store_true', help='Run automated demo instead of interactive mode')

    args = parser.parse_args()

    tester = USBSerialTester(args.port, args.baud)

    if not tester.connect():
        sys.exit(1)

    try:
        if args.demo:
            tester.demo_mode()
        else:
            tester.interactive_mode()
    finally:
        tester.disconnect()

if __name__ == '__main__':
    main()