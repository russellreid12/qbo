#!/bin/bash

# To list the Qbo processes that are running: (lsqbo.sh)
ps -aux | grep -v grep | grep -e PiCmdLine.py -e Listen.py -e WebsocketServer -e PiCmd.py -e Feel.py -e say
