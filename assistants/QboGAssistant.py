#!/usr/bin/env python3

from google.assistant.library import Assistant
from google.assistant.library.event import EventType
import google.oauth2.credentials
import io
import json
import subprocess
import threading


class GAssistant(object):

	onConversation = False
	doBlip = True

	# Initializer
	def __init__(self, deviceModelId, debug=False, credentialsFile='/opt/qbo/.config/google-oauthlib-tool/credentials.json'):

		# Read credentials file
		with io.open(credentialsFile, 'r') as f:
			self.credentials = google.oauth2.credentials.Credentials(token=None,
																	 **json.load(f))
		self.deviceModelId = deviceModelId
		self.debug = debug

		# Create thread
		self.thread = threading.Thread(target=self.run, args=())
		self.thread.daemon = False

	def run(self):
		with Assistant(self.credentials, self.deviceModelId) as assistant:
			self.assistant = assistant
			for event in assistant.start():
				self.process_event(event)
				if self.debug == True:
					print(event)

	def start(self):
		self.thread.start()

	def stop(self):
		if self.thread.is_alive():
			self.thread.join()

	def start_conversation_from_face(self):
		self.doBlip = False
		self.start_conversation()

	def start_conversation(self):
		if self.onConversation == False:
			self.assistant.start_conversation()

	def send_question(self, question):
		self.assistant.send_text_query(question)

	def stop_conversation(self):
		if self.onConversation == True:
			self.assistant.stop_conversation()

	def process_event(self, event):
		if event.type == EventType.ON_CONVERSATION_TURN_STARTED:
			if self.doBlip:
				subprocess.call("aplay /opt/qbo/sounds/blip_0.wav", shell=True)
				self.doBlip = True
			self.onConversation = True

		if event.type == EventType.ON_CONVERSATION_TURN_FINISHED:
			self.onConversation = False

		if event.type == EventType.ON_CONVERSATION_TURN_TIMEOUT:
			self.onConversation = False
