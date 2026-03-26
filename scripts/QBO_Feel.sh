#!/bin/bash

#busca un proceso especifico
DATO=`ps -aux | grep -v grep | grep Feel.py`
if [ -z "$DATO" ]; then
    	EXISTE=false
else
	EXISTE=true
fi

START="start"
STOP="stop"

# echo "EXISTE: " $EXISTE
# start Feel.py
if [[ $1 = $START ]]; then
	if $EXISTE = true;
	then
		echo "Feel.py is already running"
	else
		echo "launching Feel.py"
		/opt/qbo/Feel.py > /dev/null &
	fi
fi

# stop Feel.py
if [[ $1 = $STOP ]];
then
	if $EXISTE = true;
	then
		kill -9 `ps -ef |grep -v grep |grep Feel.py| awk '{print $2}'`
		echo "Feel.py stoped"
	else
		echo "Feel.py was not running"
	fi
fi
