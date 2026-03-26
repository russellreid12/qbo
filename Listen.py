#!/usr/bin/env python3

import os
import errno
import time
from assistants.QboTalk import QBOtalk

FIFO_listen = '/opt/qbo/pipes/pipe_listen'
FIFO_cmd = '/opt/qbo/pipes/pipe_cmd'

talk = QBOtalk()
Listening = True
listen_thd = 0


def WaitForSpeech():

	global Listening, listen_thd, FIFO_listen, FIFO_cmd

	print("WaitForSpeech: Listening=" + str(Listening) + "getAudio=" + str(talk.GetAudio))

	if Listening == False:
		print("Listening = False")
		return

	elif talk.GetAudio == True:
		listen_thd(wait_for_stop=True)
		print("Something has arrived at WaitForSpeech: " + talk.strAudio)

		fifo = os.open(FIFO_listen, os.O_WRONLY)
		os.write(fifo, talk.strAudio.encode('utf-8'))
		os.close(fifo)

		talk.GetAudio = False
		Listening = False

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

while True:

	time.sleep(1)
	WaitForSpeech()

	if talk.GetAudio == True:

		fifo = os.open(FIFO_cmd, os.O_WRONLY)
		os.write(fifo, b"-c nose -co red")
		os.close(fifo)

		time.sleep(1)

		print("StartBackListen")

		try:
			listen_thd = talk.StartBackListen()
			talk.GetAudio = False

		except:
			print("StartBackListen EXCEPTION")

	if Listening == False:
		listen_thd = talk.StartBackListen()
		Listening = True
