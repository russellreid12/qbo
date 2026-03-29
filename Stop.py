#!/usr/bin/env python3
# -*- coding: latin-1 -*-

import time
import yaml
import subprocess

from qbo_audio import aplay_wav_shell_play_wav

config = yaml.safe_load(open("/opt/qbo/config.yml"))
_PICO_WAV = "/opt/qbo/sounds/pico2wave.wav"
_aplay_play = aplay_wav_shell_play_wav(config, _PICO_WAV)

if config["language"] == "spanish":
	text = "Adíos"
	speak = "pico2wave -l \"es-ES\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + text + "\" && " + _aplay_play
else:
	text = "Good bye"
	speak = "pico2wave -l \"en-US\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + text + "\" && " + _aplay_play

subprocess.call(speak, shell = True)
time.sleep(0.5)

subprocess.call("/opt/qbo/scripts/QBO_Scratch.sh stop > /opt/qbo/logs/Qbo_ScratchModeStop.log 2>&1", shell = True)
