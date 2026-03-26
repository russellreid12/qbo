#!/usr/bin/env python3
import websocket
import _thread
import time
import json
import sys

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("### closed ###")

def on_open(ws):
    def run(*args):
        time.sleep(1)
        mycroft_question = phraseToSay
        mycroft_type = 'recognizer_loop:utterance'
        mycroft_data = '{"utterances": ["%s"]}' % mycroft_question
        message = '{"type": "' + mycroft_type + '", "data": ' + mycroft_data + '}'
        ws.send(message)
        time.sleep(0.1)
        ws.close()
        print("thread terminating...")
    _thread.start_new_thread(run, ())



if __name__ == "__main__":
    #websocket.enableTrace(True)
    phraseToSay = sys.argv[1]
    ws = websocket.WebSocketApp("ws://localhost:8181/core",
                                on_error = on_error,
                                on_close = on_close)
    ws.on_open = on_open

    ws.run_forever()