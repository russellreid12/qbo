#!/bin/bash

# Search specific process
DATO=`ps -aux | grep -v grep | grep WebsocketServer`
if [ -z "$DATO" ]; then
    	EXISTE=false
else
	EXISTE=true
fi

START="start"
STOP="stop"

# echo "EXISTE: " $EXISTE
# start websocket server
if [[ $1 = $START ]]; then
	if $EXISTE = true;
	then
		echo "WebsocketServer is already running"
	else
		echo "launching WebsocketServer"
		/opt/qbo/websocket/WebsocketServer&
	fi
fi

# stop websocket server
if [[ $1 = $STOP ]];
then
	if $EXISTE = true;
	then
		kill -9 `ps -ef |grep -v grep |grep WebsocketServer| awk '{print $2}'`
		echo "WebsocketServer stopped"
	else
		echo "WebsocketServer was not running"
	fi
fi
