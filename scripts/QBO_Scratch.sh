#!/bin/bash

START="start"
STOP="stop"

if [[ $1 = $START ]]; then
	# start all qbo process for scratch control
	echo "starting Websocket server..."
	/opt/qbo/scripts/QBO_Server.sh start
	echo "starting PiCmd.py ..."
	/opt/qbo/scripts/QBO_PiCmd.sh start
	echo "starting Say.py..."
	/opt/qbo/scripts/QBO_Say.sh start
	echo "starting Listen.py..."
	/opt/qbo/scripts/QBO_Listen.sh start
	echo "starting Feel.py..."
	/opt/qbo/scripts/QBO_Feel.sh start
	echo "starting FindFace.py..."
	/opt/qbo/scripts/QBO_FindFace.sh start
fi

if [[ $1 = $STOP ]];  then
	# stop all qbo process for scratch control
        echo "stoping Websocket server..."
        /opt/qbo/scripts/QBO_Server.sh stop
        echo "stoping PiCmd.py ..."
        /opt/qbo/scripts/QBO_PiCmd.sh stop
        echo "stoping Say.py..."
        /opt/qbo/scripts/QBO_Say.sh stop
        echo "stoping Listen.py..."
        /opt/qbo/scripts/QBO_Listen.sh stop
        echo "stoping Feel.py..."
        /opt/qbo/scripts/QBO_Feel.sh stop
        echo "stoping FindFace.py..."
        /opt/qbo/scripts/QBO_FindFace.sh stop
fi
