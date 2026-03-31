#!/usr/bin/env python3

import uuid
import os
import yaml
import subprocess
import pyaudio
import wave
import tempfile
import threading
import time
import random
import speech_recognition as sr

from qbo_audio import aplay_wav_shell_play_wav


class QboDialogFlowV2(object):
	def __init__(self, credentialFile="/opt/qbo/.config/dialogflowv2.json"):
		self.config = yaml.safe_load(open("/opt/qbo/config.yml"))
		self.project_id = self.config["dialogflowv2_projectid"]
		self.credentialFile = credentialFile
		os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentialFile
		self.FORMAT = pyaudio.paInt16
		self.CHANNELS = 1
		self.RATE = 16000
		self.CHUNK = 1024
		self.RECORD_SECONDS = self.config['SpeechToTextListeningTime']
		self.strAudio = ""
		self.GetAudio = False
		self.r = sr.Recognizer()
		self.controller = None
		self.is_animating = False

	def set_controller(self, controller):
		"""Bind the hardware controller for mouth sync animations."""
		self.controller = controller

	def record_wav(self):
		audio = pyaudio.PyAudio()
		stream = audio.open(format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE, input=True, frames_per_buffer=self.CHUNK)

		print("recording...")
		frames = []
		for i in range(0, int(self.RATE / self.CHUNK * self.RECORD_SECONDS)):
			data = stream.read(self.CHUNK)
			frames.append(data)
		print("finished recording")

		# stop Recording
		stream.stop_stream()
		stream.close()
		audio.terminate()

		# Create wav file
		tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
		waveFile = wave.open(tmp, 'wb')
		waveFile.setnchannels(self.CHANNELS)
		waveFile.setsampwidth(audio.get_sample_size(self.FORMAT))
		waveFile.setframerate(self.RATE)
		waveFile.writeframes(b''.join(frames))
		waveFile.close()

		audio_file_path = open(tmp.name)
		self.audio_file_path = tmp.name

	def callback_listen(self, recognizer, audio):

		print("callback listen")

		try:
			if self.config["language"] == "spanish":
				self.strAudio = self.r.recognize_google(audio, language="es-ES")
			else:
				self.strAudio = self.r.recognize_google(audio)

			self.strAudio = self.r.recognize_google(audio)
			self.GetAudio = True

			print("listen: " + self.strAudio)

		except:
			print("callback listen exception")
			self.strAudio = ""
			return

	def detect_intent_stream(self):

		import dialogflow_v2 as dialogflow
		session_client = dialogflow.SessionsClient()

		session_id = uuid.uuid4()

		language_code = 'en-US'
		if self.config["language"] == "Spanish":
			language_code = 'es-ES'

		audio_encoding = dialogflow.enums.AudioEncoding.AUDIO_ENCODING_LINEAR_16
		sample_rate_hertz = 16000

		session_path = session_client.session_path(self.project_id, session_id)

		def request_generator(audio_config, audio_file_path):
			query_input = dialogflow.types.QueryInput(audio_config=audio_config)

			# The first request contains the configuration.
			yield dialogflow.types.StreamingDetectIntentRequest(
				session=session_path, query_input=query_input)

			# Here we are reading small chunks of audio data from a local
			# audio file.  In practice these chunks should come from
			# an audio input device.
			with open(audio_file_path, 'rb') as audio_file:
				while True:
					chunk = audio_file.read(4096)
					if not chunk:
						break
					# The later requests contains audio data.
					yield dialogflow.types.StreamingDetectIntentRequest(
						input_audio=chunk)

		audio_config = dialogflow.types.InputAudioConfig(
			audio_encoding=audio_encoding, language_code=language_code,
			sample_rate_hertz=sample_rate_hertz)

		requests = request_generator(audio_config, self.audio_file_path)
		responses = session_client.streaming_detect_intent(requests)

		for response in responses:
			print('Intermediate transcript: "{}".'.format(
				response.recognition_result.transcript))

		# Note: The result from the last response is the final transcript along
		# with the detected content.
		query_result = response.query_result

		print('=' * 20)
		print('Query text: {}'.format(query_result.query_text))
		print('Detected intent: {} (confidence: {})\n'.format(
			query_result.intent.display_name,
			query_result.intent_detection_confidence))
		print('Response: {}\n'.format(
			query_result.fulfillment_text))

		# QBO talks here
		dialogflowResponse = format(query_result.fulfillment_text)
		self.SpeechText(dialogflowResponse)
		os.remove(self.audio_file_path)

	def _animate_mouth_loop(self):
		"""Flickers the mouth LEDs while is_animating is True."""
		mouth_patterns = [0x110E00, 0x0E1100, 0x1F1F00, 0x1B1F0E04]
		while self.is_animating:
			if self.controller:
				pattern = random.choice(mouth_patterns)
				self.controller.SetMouth(pattern)
			time.sleep(0.15)
		if self.controller:
			self.controller.SetMouth(0)

	def SpeechText(self, text_to_speech):

		_wav = "/opt/qbo/sounds/pico2wave.wav"
		_play = aplay_wav_shell_play_wav(self.config, _wav)
		if self.config["language"] == "spanish":
			speak = "pico2wave -l \"es-ES\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(self.config["volume"]) + "'>" + text_to_speech + "\" && " + _play
		else:
			speak = "pico2wave -l \"en-US\" -w /opt/qbo/sounds/pico2wave.wav \"<volume level='" + str(self.config["volume"]) + "'>" + text_to_speech + "\" && " + _play

		# Start mouth animation
		self.is_animating = True
		anim_thread = threading.Thread(target=self._animate_mouth_loop)
		anim_thread.daemon = True
		anim_thread.start()

		try:
			subprocess.call(speak, shell=True)
		finally:
			self.is_animating = False
			anim_thread.join(timeout=1.0)


if __name__ == '__main__':
	talk = QboDialogFlowV2()
	talk.record_wav()
	talk.detect_intent_stream()
