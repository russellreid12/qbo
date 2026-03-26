#!/bin/bash

## QBO Wifi Add Script
## Version 1.0.0

if [ `whoami` == "root" ]
then
	if [ $# -eq 3 ]
	then
		if [ "$3" == "nopass" ]
		then
			echo "Setting Wifi: $1"
			echo "" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo "network={" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo "		ssid=$1" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo "		key_mgmt=NONE" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo "}" >> /etc/wpa_supplicant/wpa_supplicant.conf
		elif [ "$3" == "WEP" ]
		then
			echo "Setting Wifi: $1"
			echo "" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo "network={" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo " 		  ssid=$1" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo "		  psk=$2" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo "}" >> /etc/wpa_supplicant/wpa_supplicant.conf
		elif [ "$3" == "WPA" ]
		then
			echo "Setting Wifi: $1"
			echo "" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo "network={" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo "		ssid=$1" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo "		psk=$2" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo "		key_mgmt=WPA-PSK" >> /etc/wpa_supplicant/wpa_supplicant.conf
			echo "}" >> /etc/wpa_supplicant/wpa_supplicant.conf
		else
			echo "WiFi type unsupported"
		fi

		echo "Stopping WPA_SUPPLICANT..."
		kill `pidof wpa_supplicant`
		sleep 1

		echo "Starting WPA_SUPPLICANT..."
		wpa_supplicant -B -c/etc/wpa_supplicant/wpa_supplicant.conf -iwlan0

		reboot

	else
		echo "This script requires 3 parameters. Example: sudo addWiFi.sh SSID PASS TYPE"
	fi
else
	echo "Only superuser ROOT can execute this script."
fi
