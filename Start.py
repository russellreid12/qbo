#!/usr/bin/env python3

import time
import yaml
import subprocess
import sys
import os

from qbo_audio import aplay_wav_shell_play_wav, enable_qbo_speaker_robust, wait_for_audio_hardware_visible

# Ensure logs directory exists (though installer should have created it)
LOG_FILE = "/opt/qbo/logs/Start.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Redirect stdout and stderr to Start.log
log_f = open(LOG_FILE, "a")
sys.stdout = log_f
sys.stderr = log_f

print(f"\n--- QBO Startup: {time.ctime()} ---")

time.sleep(5)

# read config file
config = yaml.safe_load(open("/opt/qbo/config.yml"))
_PICO_WAV = "/opt/qbo/sounds/pico2wave.wav"
_aplay_play = aplay_wav_shell_play_wav(config, _PICO_WAV)


enable_qbo_speaker_robust(config)
wait_for_audio_hardware_visible()

if config["language"] == "spanish":
	text = "Hola. Soy Cubo."
	speak = "pico2wave -l \"es-ES\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + text + "\" && " + _aplay_play
else:
	text = "Hello. I'm Q-B-O."
	speak = "pico2wave -l \"en-US\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + text + "\" && " + _aplay_play

subprocess.call(speak, shell=True)
time.sleep(0.5)

if config["startWith"] == "scratch":

	if config["language"] == "spanish":
		text = "Estoy en modo Scratch."
		speak = "pico2wave -l \"es-ES\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + text + "\" && " + _aplay_play
	else:
		text = "I'm in Scratch mode."
		speak = "pico2wave -l \"en-US\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + text + "\" && " + _aplay_play

	subprocess.call(speak, shell=True)

	subprocess.call("/opt/qbo/scripts/QBO_Scratch.sh start > /opt/qbo/logs/Qbo_ScratchMode.log 2>&1", shell=True)

elif config["startWith"] == "develop":

	if config["language"] == "spanish":
		text = "Estoy en modo desarrollo. Conectate por SSH o VNC para interacturar con Cubo."
		speak = "pico2wave -l \"es-ES\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + text + "\" && " + _aplay_play
	else:
		text = "I'm in development mode. Connect by SSH or VNC to interact with CUBO."
		speak = "pico2wave -l \"en-US\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + text + "\" && " + _aplay_play

	subprocess.call(speak, shell=True)

else:

	if (config["language"] == "spanish"):
		text = "Estoy en modo interactivo. Por favor, espere unos segundos."
		speak = "pico2wave -l \"es-ES\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + text + "\" && " + _aplay_play
	else:
		text = "I'm in interactive mode. Please, wait a few seconds."
		speak = "pico2wave -l \"en-US\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(config["volume"]) + "'>" + text + "\" && " + _aplay_play

	subprocess.call(speak, shell=True)

	time.sleep(10)

	subprocess.call("/opt/qbo/scripts/QBO_PiFaceFast.sh start > /opt/qbo/logs/Qbo_InteractiveMode.log 2>&1", shell=True)
