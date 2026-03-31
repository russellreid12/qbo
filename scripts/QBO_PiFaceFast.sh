#!/bin/bash

#busca un proceso especifico
DATO=`ps -aux | grep -v grep | grep PiFaceFast.py`
if [ -z "$DATO" ]; then
    	EXISTE=false
else
	EXISTE=true
fi

START="start"
STOP="stop"

# echo "EXISTE: " $EXISTE
# start PiFaceFast
if [[ $1 = $START ]]; then
	if $EXISTE = true;
	then
		echo "PiFaceFast.py is already running"
	else
		echo "launching PiFaceFast"
		export XDG_RUNTIME_DIR=/run/user/$(id -u)
		PYTHONHTTPSVERIFY=0
		# Cron runs as user qbo with bare python3 — use a venv if present (same deps as dev).
		if [ -x /opt/qbo/qbo_venv/bin/python3 ]; then
			/opt/qbo/qbo_venv/bin/python3 /opt/qbo/PiFaceFast.py &
		elif [ -x "${HOME}/qbo_venv/bin/python3" ]; then
			"${HOME}/qbo_venv/bin/python3" /opt/qbo/PiFaceFast.py &
		elif [ -x /home/pi/qbo_venv/bin/python3 ]; then
			/home/pi/qbo_venv/bin/python3 /opt/qbo/PiFaceFast.py &
		else
			python3 /opt/qbo/PiFaceFast.py &
		fi
	fi
fi

# stop PiFaceFast
if [[ $1 = $STOP ]];
then
	if $EXISTE = true;
	then
		kill -9 `ps -ef |grep -v grep |grep PiFaceFast.py| awk '{print $2}'`
		echo "PiFaceFast stoped"
	else
		echo "PiFaceFast was not running"
	fi
fi
