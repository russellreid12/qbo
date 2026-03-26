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
		PYTHONHTTPSVERIFY=0
		python3 /opt/qbo/PiFaceFast.py &
        #/opt/qbo/PiFaceFast.py > /dev/null &
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
