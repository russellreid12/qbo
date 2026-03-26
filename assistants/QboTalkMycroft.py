#!/usr/bin/env python3

import speech_recognition as sr
import yaml
import subprocess
import time

class QBOtalkMycroft(object):

	def __init__(self):

		self.config = yaml.safe_load(open("/opt/qbo/config.yml"))
		self.r = sr.Recognizer()
		self.GetAudio = False
		self.strAudio = ""
		self.Response = ""
		self.GetResponse = False

		for i, mic_name in enumerate(sr.Microphone.list_microphone_names()):
			if mic_name == "dmicQBO_sv":
				self.m = sr.Microphone(i)

		with self.m as source:
			self.r.adjust_for_ambient_noise(source)

	def callMycroft(self, str):

		print ("Listened... : " + str)
		str=str.replace("'", "")
		print ("Listened Converted...: " + str)
		subprocess.call('bash /opt/qbo/scripts/EnableSourceMyCroft.sh "' + str + '" &', shell=True)
		time.sleep(2)


	def Decode(self, audio):
		try:
			if self.config["language"] == "spanish":
				str = self.r.recognize_google(audio, language="es-ES")
			else:
				str = self.r.recognize_google(audio)

			self.strAudio = str
			self.GetAudio = True

			print("listen: " + self.strAudio)

			self.GetResponse = True
			self.callMycroft(str)

			str_resp = ""

		except sr.UnknownValueError:
			str_resp = ""

		except sr.RequestError as e:
			str_resp = "Could not request results from Speech Recognition service"

		return str_resp

	def callback(self, recognizer, audio):
		try:
			self.Decode(audio)
			print("Listening Mycroft")

		except:
			return

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

	def StartBack(self):
		with self.m as source:
			self.r.adjust_for_ambient_noise(source)

		print("start background listening")

		return self.r.listen_in_background(self.m, self.callback)

	def StartBackListen(self):
		with self.m as source:
			self.r.adjust_for_ambient_noise(source)

		print("start background only listening")

		return self.r.listen_in_background(self.m, self.callback_listen)
