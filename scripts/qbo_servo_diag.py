#!/usr/bin/env python3
import sys
import os
import time
import serial
import yaml

# Ensure we can import the controller from the qbo directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from controller.QboController import Controller

def read_servo_diagnostics(controller, axis):
    """
    Read actual position and CW/CCW limits from the servo via Arduino.
    axis: 1 = Pan (X), 2 = Tilt (Y)
    """
    label = "Pan (X)" if axis == 1 else "Tilt (Y)"
    print(f"\n--- Diagnostics for Axis {axis} [{label}] ---")
    
    pos = controller.GetServoPosition(axis)
    cw  = controller.GetServoCwLimit(axis)
    ccw = controller.GetServoCcwLimit(axis)

    if pos and cw and ccw:
        actual_pos = pos[0] | (pos[1] << 8)
        cw_limit   = cw[0]  | (cw[1]  << 8)
        ccw_limit  = ccw[0] | (ccw[1] << 8)
        
        print(f"  Actual Position: {actual_pos}")
        print(f"  CW (Min) Limit:  {cw_limit}")
        print(f"  CCW (Max) Limit: {ccw_limit}")
        
        if actual_pos <= cw_limit + 2 or actual_pos >= ccw_limit - 2:
            print("  [!] WARNING: Servo is at or very near a hardware register limit.")
        else:
            print("  [OK] Servo is within register limits.")
    else:
        print(f"  [!] ERROR: No response from controller for Axis {axis}.")

def main():
    config_path = "/opt/qbo/config.yml"
    if not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yml")
        
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Could not load config: {e}")
        sys.exit(1)

    port = config.get("serialPort", "/dev/serial0")
    try:
        ser = serial.Serial(port, baudrate=115200, timeout=0.5)
        print(f"Opened serial port: {port}")
    except Exception as e:
        print(f"Could not open serial port {port}: {e}")
        sys.exit(1)

    controller = Controller(ser)
    
    read_servo_diagnostics(controller, 1)  # Pan
    read_servo_diagnostics(controller, 2)  # Tilt
    
    print("\n------------------------------------------------")
    print("To widen limits, use the following template in a script:")
    print("  controller.SetServoCwLimit(axis, new_cw_value)")
    print("  controller.SetServoCcwLimit(axis, new_ccw_value)")
    print("Increase in small steps (~20 units) and watch for mechanical stops.")
    print("------------------------------------------------\n")
    
    ser.close()

if __name__ == "__main__":
    main()
