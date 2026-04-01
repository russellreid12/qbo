#!/usr/bin/env python3

import time
import yaml
import subprocess

from qbo_audio import aplay_wav_shell_play_wav

time.sleep(5)

# read config file
config = yaml.safe_load(open("/opt/qbo/config.yml"))
_PICO_WAV = "/opt/qbo/sounds/pico2wave.wav"
_aplay_play = aplay_wav_shell_play_wav(config, _PICO_WAV)


def _enable_qbo_speaker_before_tts(cfg):
	"""Head MCU keeps the amp muted until this runs; try multiple times during boot-up scramble."""
	for attempt in range(3):
		try:
			import serial
			from controller.QboController import Controller
			port = cfg.get("serialPort", "/dev/serial0")
			ser = serial.Serial(
				port,
				baudrate=115200,
				bytesize=serial.EIGHTBITS,
				stopbits=serial.STOPBITS_ONE,
				parity=serial.PARITY_NONE,
				rtscts=False,
				dsrdtr=False,
				timeout=0.1,
			)
			ctrl = Controller(ser)
			ctrl.SetEnableSpeaker(True)
			ser.close()
			print(f"Start.py: Speaker enabled on attempt {attempt + 1}")
			return True
		except Exception as e:
			print(f"Start.py: Speaker enable attempt {attempt + 1} failed: {e}")
			time.sleep(2)
	return False


_enable_qbo_speaker_before_tts(config)

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
