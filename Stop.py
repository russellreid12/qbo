#!/usr/bin/env python3
# -*- coding: latin-1 -*-

import time
import yaml
import subprocess

config = yaml.safe_load(open("/opt/qbo/config.yml"))

if config["language"] == "spanish":
	text = "Adíos"
	speak = "pico2wave -l \"es-ES\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + text + "\" && aplay -D convertQBO /opt/qbo/sounds/pico2wave.wav"
else:
	text = "Good bye"
	speak = "pico2wave -l \"en-US\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + text + "\" && aplay -D convertQBO /opt/qbo/sounds/pico2wave.wav"

subprocess.call(speak, shell = True)
time.sleep(0.5)

subprocess.call("/opt/qbo/scripts/QBO_Scratch.sh stop > /opt/qbo/logs/Qbo_ScratchModeStop.log 2>&1", shell = True)
