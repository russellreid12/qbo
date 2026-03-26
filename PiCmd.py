#!/usr/bin/env python3

import serial
import subprocess
import sys
import os
import errno
import yaml
from assistants.QboTalk import QBOtalk
from controller.QboController import Controller


port = '/dev/serial0'
config = yaml.safe_load(open("/opt/qbo/config.yml"))

FIFO_cmd = '/opt/qbo/pipes/pipe_cmd'
FIFO_say = '/opt/qbo/pipes/pipe_say'

cmd = ""
angle = 0
axis = 0
speed = 0
color = ""
text = ""
idx = 0
line = ""
lang = ""
ser = ""
matrix = 0
expression = ""
youtube_url = ""
pid = [0, 0, 0]



# returns the argument in the 'idx' position
def scan_argument(index):
	if len(sys.argv) > 1:
		return sys.argv[index]
	else:
		return line.split()[index]


# returns the number of arguments of the executable or of 'line'
def n_args(line):
	if len(sys.argv) > 1:
		return len(sys.argv)
	else:
		return len(line.split())


def get_command():
	global cmd, idx

	try:
		arg = scan_argument(idx)
		if arg in commands:
			cmd = str(arg)
		else:
			print("wrong command")

	except:
		print("command param error")


def get_angle():
	global angle, idx

	try:
		arg = scan_argument(idx)

		if int(arg) <= 800 and int(arg) >= -800:
			angle = int(arg)

		else:
			print("wrong angle value")

	except:
		print("wrong angle value")


def get_text():
	global text, idx

	text = ""
	try:
		while idx < n_args(line):

			arg = scan_argument(idx)

			# next command is finded
			if arg[0] == '-':
				break

			idx = idx + 1
			text += " " + arg

	except:
		print("wrong text value")


def get_pid():
	global pid, idx

	pid = [0, 0, 0]
	i = 0

	try:
		while idx < n_args(line):

			arg = scan_argument(idx)

			# next command is finded
			if arg[0] == '-':
				break

			idx = idx + 1
			pid[i] = int(arg)
			i += 1

	except:
		print("wrong pid value")

	print("PID: " + str(pid))


def get_axis():
	global axis, idx

	arg = scan_argument(idx)

	if arg in axises:
		axis = int(arg)

	else:
		print("wrong axis value")


def get_speed():
	global speed

	try:
		arg = scan_argument(idx)

		if int(arg) >= 0 and int(arg) < 2000:
			speed = int(arg)

		else:
			print("wrong speed value")

	except:
		print("wrong speed value")


def get_color():
	global color, idx

	try:
		arg = scan_argument(idx)

		if arg in colors:
			color = arg

		else:
			print("wrong color value")

	except:
		print("color param error")


def get_language():
	global lang, idx

	try:
		arg = scan_argument(idx)

		if arg in languages:
			lang = arg

		else:
			print("wrong language value")

	except:
		print("laguage param error")


def get_youtube_code():
	global youtube_url
	youtube_url = scan_argument(idx)


def get_mouth_expression():
	global expression, idx

	try:
		arg = scan_argument(idx)

		if arg in expressions:
			expression = arg

		else:
			print("wrong expression value")

	except:
		print("expression param error")


def get_mouth_matrix():
	global matrix, idx

	print("GET_MOUTH_MATRIX")
	print("idx: " + str(idx))

	try:

		i = 0

		while i < 4:

			arg = scan_argument(idx)
			print("arg: " + arg)

			matrix |= int(arg) << (8 * (3 - i))
			print("arg matrix: " + str(matrix))

			i = i + 1
			idx = idx + 1

	except:
		print("mouth matrix param error")


def say():
	print("")


def help():
	global cmd

	cmd = "help"
	print(" ")
	print("Options:")
	print("-c [command] servo, nose, say, mouth, listen or voice")
	print("-a [angle] from -180 to 180")
	print("-x [axis] 1 or 2")
	print("-s [speed] from 1 to 2000")
	print("-co [color] none, red, green or blue")
	print("-l [language] english or spanish")
	print("-m [matrix] mouth leds matrix")
	print("-e [expression] smile, sad or serious")
	print("-y [Youtube URL] Play sound of Youtube Video")
	print(" ")
	print("EXAMPLES: ")
	print("-c servo -a 30 -x 1 -s 200")
	print("-c nose -co red")
	print(" ")


def CommandOK_Action():
	global config, ser, HeadServo, color

	if cmd == "servo" and angle != 0 and axis != 0 and speed >= 0:
		print("Sending: " + cmd + "(" + str(axis) + "," + str(angle) + "," + str(speed) + ")")
		HeadServo.SetServo(axis, angle, speed)

	elif cmd == "move" and angle != 0 and axis != 0:
		HeadServo.SetAngle(axis, angle)

	elif cmd == "move_rel" and angle != 0 and axis != 0:
		HeadServo.SetAngleRelative(axis, angle)

	elif cmd == "nose" and color != "":

		print("Sending: " + cmd + "(" + str(color) + ")")

		# the led of the nose goes off
		# call to the command "nose"
		if color == "none":
			HeadServo.SetNoseColor(0)
		if color == "red":
			HeadServo.SetNoseColor(2)
		if color == "blue":
			HeadServo.SetNoseColor(1)
		if color == "green":
			HeadServo.SetNoseColor(4)

	elif cmd == "say" and text != "":

		print("Opening FIFO..." + FIFO_say)
		fifo_say = os.open(FIFO_say, os.O_WRONLY)
		os.write(fifo_say, text.encode('utf-8'))
		os.close(fifo_say)

		print("Saying: " + text)

	elif cmd == "voice":

		# actualizacion del fichero config
		config["language"] = lang
		with open('/opt/qbo/config.yml', 'w') as f:
			yaml.dump(config, f)

		print("Setting: " + cmd + " = " + str(lang))
		f.close()

	elif cmd == "mouth":

		if matrix != 0:
			print("Sending " + cmd + "(" + str(matrix) + ")")
			HeadServo.SetMouth(matrix)

		elif expression != "":

			print("Sending " + cmd + "(" + expression + ")")

			if expression == "smile":
				HeadServo.SetMouth(0x110E00)

			elif expression == "sad":
				HeadServo.SetMouth(0x0E1100)

			elif expression == "serious":
				HeadServo.SetMouth(0x1F1F00)

			elif expression == "love":
				HeadServo.SetMouth(0x1B1F0E04)

	elif cmd == "pid":
		if axis != 0:
			HeadServo.SetPid(axis, pid[0], pid[1], pid[2])

	elif cmd == "listen":
		talk = QBOtalk()
		talk.StartBack()

	elif cmd == "youtube" and youtube_url != "":
		subprocess.call("youtube-dl --extract-audio --audio-format wav -o \"/tmp/song_youtube.%(ext)s\" " + youtube_url + " ; aplay /tmp/song_youtube.wav -D convertQBO", shell=True)

	else:
		print("Command error. Type ? to help")


options = {"-c": get_command,
		   "-a": get_angle,
		   "-x": get_axis,
		   "-s": get_speed,
		   "-t": get_text,
		   "-co": get_color,
		   "-l": get_language,
		   "-m": get_mouth_matrix,
		   "-e": get_mouth_expression,
		   "-y": get_youtube_code,
		   "-p": get_pid,
		   "?": help,
		   "help": help,
		   "-h": help,
		   }

commands = {"servo",
			"nose",
			"say",
			"voice",
			"mouth",
			"listen",
			"youtube",
			"pid",
			"move",
			"move_rel",
			}

axises = {"1", "2"}

colors = {"none", "red", "green", "blue"}

languages = {"english", "spanish"}

expressions = {"smile", "sad", "serious", "love"}

# scans executable arguments
for arg in sys.argv:
	idx = idx + 1
	if arg in options:
		options[arg]()

try:

	# Open serial port
	ser = serial.Serial(port, baudrate=115200, bytesize=serial.EIGHTBITS, stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE, rtscts=False, dsrdtr=False, timeout=0)
	print("Open serial port sucessfully.")
	print(ser.name)

	HeadServo = Controller(ser)

except:
	print("Error opening serial port.")
	sys.exit()

# if parameters in command then execute action
if len(sys.argv) > 1:
	CommandOK_Action()

try:
	os.mkfifo(FIFO_cmd)
except OSError as oe:
	if oe.errno != errno.EEXIST:
		raise

# scan stdin
if len(sys.argv) == 1:

	line = ""

	while 1:

		idx = 0
		print("Opening FIFO..." + FIFO_cmd)

		with open(FIFO_cmd) as fifo_cmd:

			print("FIFO opened" + FIFO_cmd)

			line = fifo_cmd.read()
			fifo_cmd.close()

			if len(line) == 0:
				print("Writer closed")
				continue

			print('line_cmd: ' + line)

			if line == "exit" or line == "quit":
				sys.exit()

			cmd = ""
			angle = 0
			axis = 0
			speed = 0
			color = ""
			matrix = 0
			expression = ""
			youtube_url = ""

			# Scans command line arguments
			for word in line.split():
				idx = idx + 1
				if word in options:
					options[word]()

			# Manage the correct commands
			# Different operations are carried out:
			#    - Sending to the motherboard by serial port.
			#    - Call the raspi system to execute the program 'espeak'.
			CommandOK_Action()

sys.exit()
