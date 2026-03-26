#!/bin/bash

arecord --format=S16_LE --duration=5 --rate=16000 --file-type=wav /tmp/testAudio.wav
aplay -D convertQBO /tmp/testAudio.wav
