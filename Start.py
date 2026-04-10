#!/usr/bin/env python3

import time
import yaml
import subprocess
import sys
import os

from qbo_audio import aplay_wav_shell_play_wav, wait_for_audio_hardware_visible

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


def _enable_qbo_speaker_before_tts(cfg):
	"""Head MCU keeps the amp muted until this runs. Start.py uses a private serial connection before PiFaceFast starts."""
	port = cfg.get("serialPort", "/dev/serial0")
	max_retries = 10
	retry_delay = 2
	print(f"Start.py: attempting to enable speaker on {port} (retries={max_retries})...")
	for i in range(max_retries):
		try:
			import serial
			from controller.QboController import Controller
			if not os.path.exists(port):
				time.sleep(retry_delay)
				continue
			ser = serial.Serial(port, baudrate=115200, timeout=0.2)
			ctrl = Controller(ser)
			ctrl.SetEnableSpeaker(True)
			ser.close()
			print("Start.py: QBO speaker enabled successfully.")
			return True
		except Exception as e:
			print(f"Start.py: attempt {i+1} failed: {e}")
			time.sleep(retry_delay)
	return False


def wait_for_bluetooth_sink(timeout=60, poll_interval=2):
	"""Wait until a Bluetooth audio sink appears in pactl."""
	print("Start.py: waiting for Bluetooth audio sink...")
	deadline = time.time() + timeout
	while time.time() < deadline:
		result = subprocess.run(
			["pactl", "list", "short", "sinks"],
			capture_output=True, text=True
		)
		if "bluez" in result.stdout:
			print("Start.py: Bluetooth sink found.")
			return True
		time.sleep(poll_interval)
	print("Start.py: WARNING — Bluetooth sink not found within timeout, proceeding anyway.")
	return False


_enable_qbo_speaker_before_tts(config)
wait_for_audio_hardware_visible()

# Only wait for BT if pulse/default/pipewire is used (where BT usually sits)
_audio_target = str(config.get("audioPlaybackDevice") or config.get("audioPlaybackMode", "convertQBO")).lower()
if "pulse" in _audio_target or "default" in _audio_target or "pipewire" in _audio_target:
	wait_for_bluetooth_sink(timeout=30)

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
