#!/usr/bin/env python3

import os
import errno
import serial
import sys
import time
from controller.QboController import Controller


FIFO_feel = '/opt/qbo/pipes/pipe_feel'

if len(sys.argv) > 1:
	port = sys.argv[1]
else:
	port = '/dev/serial0'

try:

	print(port)

	# Open serial port
	ser = serial.Serial(port, baudrate=115200, bytesize=serial.EIGHTBITS, stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE, rtscts=False, dsrdtr=False, timeout=0)

	print("Open serial port sucessfully.")
	print(ser.name)

	HeadServo = Controller(ser)

except:
	print("Error opening serial port.")
	sys.exit()


def WaitForTouch():

	touch_str = ""
	touch = HeadServo.GetHeadCmd("GET_TOUCH", 0)

	if touch:

		if touch == [1]:
			touch_str = "Touch: right"
		elif touch == [2]:
			touch_str = "Touch: up"
		elif touch == [3]:
			touch_str = "Touch: left"

		if touch == [1] or touch == [2] or touch == [3]:
			print(touch_str + "TO FIFO FEEL")
			fifo = os.open(FIFO_feel, os.O_WRONLY)
			os.write(fifo, touch_str.encode('utf-8'))

	time.sleep(.250)
	return touch_str


try:
	os.mkfifo(FIFO_feel)
except OSError as oe:
	if oe.errno != errno.EEXIST:
		raise

while True:
	time.sleep(1)
	WaitForTouch()
