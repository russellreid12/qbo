#!/usr/bin/env python3

import subprocess
import os
import yaml

from qbo_audio import aplay_wav_device_quoted

config = yaml.safe_load(open("/opt/qbo/config.yml"))
_aplay_d = aplay_wav_device_quoted(config)
FIFO_say = '/opt/qbo/pipes/pipe_say'


def SayFromFile():
	global config, FIFO_say

	print("Opening FIFO...")

	while True:

		fifo = os.open(FIFO_say, os.O_RDONLY)
		data = os.read(fifo, 100)
		os.close(fifo)

		if data:

			print('Read: "{0}"'.format(data))

			if (config["language"] == "spanish"):
				speak = "pico2wave -l \"es-ES\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + data + "\" && aplay -D " + _aplay_d + " /opt/qbo/sounds/pico2wave.wav"
			else:
				speak = "pico2wave -l \"en-US\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + data + "\" && aplay -D " + _aplay_d + " /opt/qbo/sounds/pico2wave.wav"

			print("say.py: " + speak)

			subprocess.call("/opt/qbo/scripts/QBO_listen.sh stop", shell=True)
			subprocess.call(speak, shell=True)
			subprocess.call("/opt/qbo/scripts/QBO_listen.sh start", shell=True)


while True:
	SayFromFile()
