#!/usr/bin/env python3

from assistants.QboTalk import QBOtalk
import errno
import subprocess
import os
import time
import yaml

# FIFO init.
FIFO_listen = '/opt/qbo/pipes/pipe_listen'
FIFO_say = '/opt/qbo/pipes/pipe_say'
FIFO_cmd = '/opt/qbo/pipes/pipe_cmd'

Listening = True
listen_thd = 0
talk = QBOtalk()


def SayFromFifo():

	print("Opening FIFO...")
	fifo = os.open(FIFO_say, os.O_RDONLY | os.O_NONBLOCK)

	try:
		data = os.read(fifo, 100)
	except OSError as oe:
		if oe.errno != 11:  # errno.EEXIST:
			raise

	os.close(fifo)

	if data:
		config = yaml.safe_load(open("/opt/qbo/config.yml"))

		print('Read: "{0}"'.format(data))

		if config["languaje"] == "english":
			speak = "espeak -ven+f3 \"" + data + "\" --stdout  | aplay -D convertQBO"
		elif config["languaje"] == "spanish":
			speak = "espeak -v mb-es2 -s 120 \"" + data + "\" --stdout  | aplay -D convertQBO"

		subprocess.call(speak, shell=True)


def WaitForSpeech():

	global Listening, listen_thd, FIFO_listen, FIFO_cmd

	if Listening == False:
		return

	elif talk.GetAudio == True:

		fifo = os.open(FIFO_cmd, os.O_WRONLY)
		os.write(fifo, b"-c nose -co red")
		os.close(fifo)
		listen_thd(wait_for_stop=True)

		print("Ha llegado algo al WaitForSpeech: " + talk.strAudio)
		fifo = os.open(FIFO_listen, os.O_WRONLY)
		os.write(fifo, talk.strAudio.encode('utf-8'))
		os.close(fifo)

	return


try:
	os.mkfifo(FIFO_listen)
except OSError as oe:
	if oe.errno != errno.EEXIST:
		raise

try:
	os.mkfifo(FIFO_cmd)
except OSError as oe:
	if oe.errno != errno.EEXIST:
		raise

listen_thd = talk.StartBackListen()
fifo = os.open(FIFO_cmd, os.O_WRONLY)
os.write(fifo, b"-c nose -co green")
os.close(fifo)

while True:

	SayFromFifo()
	WaitForSpeech()

	if talk.GetAudio == True:
		fifo = os.open(FIFO_cmd, os.O_WRONLY)
		os.write(fifo, b"-c nose -co red")
		os.close(fifo)
		time.sleep(1)

		print("StartBackListen")

		try:
			listen_thd = talk.StartBackListen()
			fifo = os.open(FIFO_cmd, os.O_WRONLY)
			os.write(fifo, b"-c nose -co green")
			os.close(fifo)
			talk.GetAudio = False
		except:
			print("StartBackListe EXCEPTION")
