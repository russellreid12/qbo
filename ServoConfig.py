#!/usr/bin/env python3

import argparse
import serial
import time
from controller.QboController import Controller

parser = argparse.ArgumentParser()
parser.add_argument("-d", "--device", help="Servo number ID = 1:Left-Right servo 2:Up-Down Servo", type=int)
parser.add_argument("-c", "--command", help="Command: SET_SERVO_ID, SET_SERVO_CW_LIM, SET_SERVO_CCW_LIM, SET_USB2SERVO_FWD, SET_SERVO_ENABLE")
parser.add_argument("param", help="Command parameter", type=int)
args = parser.parse_args()

comPort = serial.Serial('/dev/serial0', 115200, timeout=0)
HeadCtrl = Controller(comPort)


def ChangeDeviceID(device, cmd, value):
	HeadCtrl.GetHeadCmd("SET_SERVO_LED", [device, 1])
	time.sleep(0.1)
	Id = HeadCtrl.GetHeadCmd("GET_SERVO_BYTE_REG", [device, 3])
	print("Present ID", Id)
	time.sleep(0.1)
	HeadCtrl.GetHeadCmd(cmd, [device, value])
	print(cmd, [device, value])
	time.sleep(0.1)
	newId = HeadCtrl.GetHeadCmd("GET_SERVO_BYTE_REG", [value, 3])
	print("New ID", newId)
	time.sleep(.5)
	HeadCtrl.GetHeadCmd("SET_SERVO_LED", [value, 0])
	time.sleep(.1)

	return


def ChangePortFwd(cmd, value):
	fwd_en = value & 1

	if fwd_en != 0:
		print("USB to Servo port forwarding enabled", fwd_en)
	else:
		print("USB to Servo port forwarding disabled", fwd_en)

	HeadCtrl.GetHeadCmd(cmd, [device, fwd_en])
	time.sleep(.1)
	return


def ChangeServoEnable(device, cmd, value):
	servo_en = value & 1

	if servo_en != 0:
		print("Servo", device, "enabled")

	else:
		print("Servo", device, "disabled")

	HeadCtrl.GetHeadCmd(cmd, [device, servo_en])
	time.sleep(.1)

	return


def GetServoLimits(cmd, device):

	if cmd == "SET_SERVO_CW_LIM":
		cw_limits = HeadCtrl.GetHeadCmd("GET_SERVO_CW_LIM", device)
		if cw_limits:
			result = (cw_limits[1] << 8 | cw_limits[0])
		else:
			result = 0

	elif cmd == "SET_SERVO_CCW_LIM":
		ccw_limits = HeadCtrl.GetHeadCmd("GET_SERVO_CCW_LIM", device)
		if ccw_limits:
			result = (ccw_limits[1] << 8 | ccw_limits[0])
		else:
			result = 0

	return result


def ChangeLimit(device, cmd, value):

	limit = GetServoLimits(cmd, device)
	print("Present Limit ", limit)

	time.sleep(0.1)
	HeadCtrl.GetHeadCmd("SET_SERVO_LED", [device, 1])
	time.sleep(0.1)
	HeadCtrl.GetHeadCmd(cmd, [device, value])
	time.sleep(0.1)
	newLimit = GetServoLimits(cmd, device)

	if newLimit == value:
		print("Limit changed!")

	print("New Limit", newLimit)
	time.sleep(.5)
	HeadCtrl.GetHeadCmd("SET_SERVO_LED", [device, 0])

	return


if args.command == "SET_USB2SERVO_FWD":
	ChangePortFwd(args.command, args.param)

elif args.device == 1 or args.device == 2:
	if args.command == "SET_SERVO_ID":
		if args.param == 1 or args.param == 2:
			ChangeDeviceID(args.device, args.command, args.param)
		else:
			print("Bad setting new device number", args.param)

	elif args.command == "SET_SERVO_CW_LIM" or args.command == "SET_SERVO_CCW_LIM":
		if args.param > 1023:
			print("Bad setting angle limit")
		else:
			ChangeLimit(args.device, args.command, args.param)

	elif args.command == "SET_SERVO_ENABLE":
		ChangeServoEnable(args.device, args.command, args.param)

else:
	print("Bad device number", args.device)
