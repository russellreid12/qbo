#!/usr/bin/env python3

import cv2
import sys
import time
import os
import errno
import yaml


config = yaml.safe_load(open("/opt/qbo/config.yml"))

## Initial Head position

Xcoor = 511
Ycoor = 600
Facedet = 0

no_face_tm = time.time()
face_det_tm = time.time()
face_not_found_idx = 0

webcam = cv2.VideoCapture(int(config['camera']), cv2.CAP_V4L2)  # Pi 5: use V4L2; set camera index in config (often 2, not 0)
webcam.set(cv2.CAP_PROP_FRAME_WIDTH, 320)  # I have found this to be about the highest-
webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)  # resolution you'll want to attempt on the pi
webcam.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not webcam:
	print("Error opening WebCAM")
	sys.exit(1)

frontalface = cv2.CascadeClassifier("/opt/qbo/haarcascades/haarcascade_frontalface_alt2.xml")  # frontal face pattern detection
profileface = cv2.CascadeClassifier("/opt/qbo/haarcascades/haarcascade_profileface.xml")  # side face pattern detection

face = [0, 0, 0, 0]  # This will hold the array that OpenCV returns when it finds a face: (makes a rectangle)
Cface = [0, 0]  # Center of the face: a point calculated from the above variable
lastface = 0  # int 1-3 used to speed up detection. The script is looking for a right profile face,-
# a left profile face, or a frontal face; rather than searching for all three every time,-
# it uses this variable to remember which is last saw: and looks for that again. If it-
# doesn't find it, it's set back to zero and on the next loop it will search for all three.-
# This basically tripples the detect time so long as the face hasn't moved much.

time.sleep(1)  # Wait for them to start

_camera_flip_h = bool(config.get("cameraFlipHorizontal", False))

for _ in range(5):
	webcam.grab()


def read_webcam_detection_frame(cap):
	for _ in range(2):
		cap.grab()
	ret, frame = cap.read()
	if not ret or frame is None:
		return None
	if _camera_flip_h:
		frame = cv2.flip(frame, 1)
	h, w = frame.shape[:2]
	if w != 320 or h != 240:
		frame = cv2.resize(frame, (320, 240))
	return frame


print("FindFace: use the same cameraFlipHorizontal as PiFaceFast; stop other apps using /dev/video* (select() timeouts if shared).")


FIFO_findFace = '/opt/qbo/pipes/pipe_findFace'

try:
	os.mkfifo(FIFO_findFace)
except OSError as oe:
	if oe.errno != errno.EEXIST:
		raise

fr_time = 0
while True:
	#print "frame time: " + str(time.time() - fr_time)
	time.sleep(0.5)  # capture image every 500ms
	fr_time = time.time()

	faceFound = False  # This variable is set to true if, on THIS loop a face has already been found
	# We search for a face three diffrent ways, and if we have found one already-
	# there is no reason to keep looking.
	if not faceFound:
		if lastface == 0 or lastface == 1:
			aframe = read_webcam_detection_frame(webcam)
			#print "t: " + str(time.time()-t_ini)
			if aframe is not None:
				fface = frontalface.detectMultiScale(aframe, 1.3, 4, (cv2.CASCADE_DO_CANNY_PRUNING + cv2.CASCADE_FIND_BIGGEST_OBJECT + cv2.CASCADE_DO_ROUGH_SEARCH), (60, 60))
				if len(fface) > 0:
					#print "FAAACEEEE"
					lastface = 1  # set lastface 1 (so next loop we will only look for a frontface)
					for f in fface:  # f in fface is an array with a rectangle representing a face
						faceFound = True
						face = f

	if not faceFound:  # if we didnt find a face yet...
		if lastface == 0 or lastface == 2:  # only attempt it if we didn't find a face last loop or if-
			aframe = read_webcam_detection_frame(webcam)
			#print "tp: " + str(time.time()-t_ini)
			if aframe is not None:
				pfacer = profileface.detectMultiScale(aframe, 1.3, 4, (cv2.CASCADE_DO_CANNY_PRUNING + cv2.CASCADE_FIND_BIGGEST_OBJECT + cv2.CASCADE_DO_ROUGH_SEARCH), (80, 80))

				if len(pfacer) > 0:
					#print "PROFILE FAAACEEEE"
					lastface = 2
					for f in pfacer:
						faceFound = True
						face = f

	if not faceFound:  # if no face was found...-
		face_not_found_idx += 1
		if (face_not_found_idx > 3):
			face_not_found_idx = 0
			lastface = 0  # the next loop needs to know
			face = [0, 0, 0, 0]  # so that it doesn't think the face is still where it was last loop
			if Facedet != 0:
				Facedet = 0
				no_face_tm = time.time()
			#print "No face.!"
			elif (time.time() - no_face_tm > 10):
				Cface[0] = [0, 0]
				no_face_tm = time.time()
	else:
		x, y, w, h = face
		Cface = [(w / 2 + x), (h / 2 + y)]  # we are given an x,y corner point and a width and height, we need the center
		#print "face ccord: " + str(Cface[0]) + "," + str(Cface[1])
		fifo = os.open(FIFO_findFace, os.O_WRONLY)
		os.write(fifo, (str(Cface[0]) + "," + str(Cface[1]) + "\n").encode('utf-8'))
		if Facedet == 0:
			Facedet = 1
			face_det_tm = time.time()
		#print "Face detected.!"
