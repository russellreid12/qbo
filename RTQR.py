#!/usr/bin/env python3

import subprocess
import zbar
from PIL import Image
import cv2
import yaml

from qbo_audio import subprocess_aplay_wav

def main():

	config = yaml.safe_load(open("/opt/qbo/config.yml"))

	# Set 0 to default camera
	capture = cv2.VideoCapture(int(config['camera']), cv2.CAP_V4L2)

	while True:

		# Breaks down the video into frames
		ret, frame = capture.read()

		# Displays the current frame
		# cv2.imshow('Current', frame)

		# Converts image to grayscale.
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

		# Uses PIL to convert the grayscale image into a ndary array that ZBar can understand.
		image = Image.fromarray(gray)
		width, height = image.size
		zbar_image = zbar.Image(width, height, 'Y800', image.tobytes())

		# Scans the zbar image.
		scanner = zbar.ImageScanner()
		scanner.scan(zbar_image)

		# Prints data from image.
		for decoded in zbar_image:

			# O btain string info qr
			info = decoded.data

			# Check if QR contain WiFi string
			if info[0:7] == "WIFI:S:":

				# Get indexs
				indexEndName = info.find(";T:")
				indexEndType = info.find(";P:")
				indexEndPass = len(info) - 2
				indexStartHidden = info.find(";H:true;")
				hidden = False

				# Check if wifi hidden
				if indexStartHidden != -1:
					hidden = True
					indexEndPass = indexStartHidden

				# Obtain values
				ssid = info[7:indexEndName]
				type = info[indexEndName + 3:indexEndType]
				password = info[indexEndType + 3:indexEndPass]

				subprocess_aplay_wav(config, "/opt/qbo/sounds/blip_1.wav")

				wificonfig = "sudo bash /opt/qbo/scripts/WiFiAdd.sh '\"%s\"' '\"%s\"' \"%s\"" % (ssid, password, type)
				subprocess.call(wificonfig, shell=True)

				return


if __name__ == "__main__":
	main()
