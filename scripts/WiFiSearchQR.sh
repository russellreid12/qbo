#!/bin/bash

## QBO Search WiFi QR
## Version 1.0.0

sleep 25 # Wait twenty five seconds

internetStatus=$(curl -s -I https://www.google.com/ | grep "HTTP/2 200")

if [ -z "$internetStatus" ]
then
	/opt/qbo/scripts/QBO_scratch.sh stop
	/opt/qbo/scripts/QBO_PiFaceFast.sh stop

	RTQRExec=$(ps -aux | grep RTQR.py | wc -l)

	if [ $RTQRExec -eq 2 ]
	then
		echo "QR recognition is already running"
	else
	    pico2wave -l "en-US" -w /opt/qbo/sounds/pico2wave.wav "I'm not connected to the internet. Start scanning QR code." && aplay -D convertQBO /opt/qbo/sounds/pico2wave.wav
		python3 /opt/qbo/RTQR.py
		pico2wave -l "en-US" -w /opt/qbo/sounds/pico2wave.wav "Got it, I'm connecting to the internet" && aplay -D convertQBO /opt/qbo/sounds/pico2wave.wav
		sleep 20
		internetStatus2=$(curl -s -I https://www.google.com/ | grep "HTTP/2 200")
		if [ -z "$internetStatus2" ]
		then
			pico2wave -l "en-US" -w /opt/qbo/sounds/pico2wave.wav "Sorry, your SSID or password is wrong, try again." && aplay -D convertQBO /opt/qbo/sounds/pico2wave.wav
		else
			pico2wave -l "en-US" -w /opt/qbo/sounds/pico2wave.wav "I am connected" && aplay -D convertQBO /opt/qbo/sounds/pico2wave.wav
			python3 /opt/qbo/Start.py
		fi
	fi
fi
