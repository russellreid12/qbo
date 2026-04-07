#!/usr/bin/env python3
import sys
import os
import time
import serial
import yaml

# Ensure we can import the controller
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from controller.QboController import Controller

def test_servo():
    config_path = "/opt/qbo/config.yml"
    if not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yml")
        
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    port = config.get("serialPort", "/dev/serial0")
    ser = serial.Serial(port, baudrate=115200, timeout=0.5)
    controller = Controller(ser)

    print("Reading current positions...")
    pos1 = controller.GetServoPosition(1)
    pos2 = controller.GetServoPosition(2)
    
    val1 = pos1[0] | (pos1[1] << 8) if pos1 else 511
    val2 = pos2[0] | (pos2[1] << 8) if pos2 else 511
    
    print(f"Current Servo 1: {val1}")
    print(f"Current Servo 2: {val2}")

    speed = 60

    print("\n--- Moving SERVO 1 ---")
    print("Does the head TILT (up/down) or PAN (left/right)?")
    controller.SetServo(1, val1 + 30, speed)
    time.sleep(1)
    controller.SetServo(1, val1 - 30, speed)
    time.sleep(1)
    controller.SetServo(1, val1, speed)
    time.sleep(1)

    print("\n--- Moving SERVO 2 ---")
    print("Does the head TILT (up/down) or PAN (left/right)?")
    controller.SetServo(2, val2 + 30, speed)
    time.sleep(1)
    controller.SetServo(2, val2 - 30, speed)
    time.sleep(1)
    controller.SetServo(2, val2, speed)
    time.sleep(1)

    ser.close()
    print("\nDone. Please confirm which Servo ID controls which joint.")

if __name__ == "__main__":
    test_servo()
