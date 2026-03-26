#!/bin/bash

#busca un proceso especifico
DATO=`ps -aux | grep -v grep | grep Listen.py`
if [ -z "$DATO" ]; then
    	EXISTE=false
else
	EXISTE=true
fi

START="start"
STOP="stop"

# echo "EXISTE: " $EXISTE
# start Listen.py
if [[ $1 = $START ]]; then
	if $EXISTE = true;
	then
		echo "Listen.py is already running"
	else
		echo "launching Listen.py"
		/opt/qbo/Listen.py > /dev/null &
	fi
fi

# stop Listen.py
if [[ $1 = $STOP ]];
then
	if $EXISTE = true;
	then
		kill -9 `ps -ef |grep -v grep |grep Listen.py| awk '{print $2}'`
		echo "Listen.py stoped"
	else
		echo "Listen.py was not running"
	fi
fi
