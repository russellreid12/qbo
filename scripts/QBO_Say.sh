#!/bin/bash

#busca un proceso especifico
DATO=`ps -aux | grep -v grep | grep Say.py`
if [ -z "$DATO" ]; then
    	EXISTE=false
else
	EXISTE=true
fi

START="start"
STOP="stop"

# echo "EXISTE: " $EXISTE
# start Say.py
if [[ $1 = $START ]]; then
	if $EXISTE = true;
	then
		echo "Say.py is already running"
	else
		echo "launching Say.py"
		/opt/qbo/Say.py > /dev/null &
	fi
fi

# stop Say
if [[ $1 = $STOP ]];
then
	if $EXISTE = true;
	then
		kill -9 `ps -ef |grep -v grep |grep Say.py| awk '{print $2}'`
		echo "Say.py stoped"
	else
		echo "Say.py was not running"
	fi
fi
