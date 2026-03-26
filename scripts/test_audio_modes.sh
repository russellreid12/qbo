#!/bin/bash
# Audio playback tests for Pi 5 + Voice HAT.
# Run:  bash scripts/test_audio_modes.sh
#
# Prereqs (Pi): sudo apt install sox espeak libttspico-utils
# Optional: flite (sudo apt install flite), espeak-ng
#
# Start with step 0 only (MINIMAL=1). If that sounds best, use plughw in config — no sox.
# Optional: GAIN_DB=-12 only if you hear clipping (distortion), not for "general" noise.
#
# TTS backends: pico2wave (Pi), espeak, flite, say (macOS). Use TTS=pico2wave|espeak|flite|say
# to run only that backend's tests. DEVICE=plughw:0,0 or plughw (default) sets aplay device.


set -e
WAV16="/tmp/t.wav"
WAV48="/tmp/t_48k.wav"
TEXT="testing clarity one two three"
GAIN_DB="${GAIN_DB:-0}"
DEVICE="${DEVICE:-plughw:0,0}"
TTS_FILTER="${TTS:-}"


gain_args() {
 if [ "$GAIN_DB" != "0" ] && [ -n "$GAIN_DB" ]; then
   echo "gain $GAIN_DB"
 fi
}


_run() {
 local name="$1"
 shift
 if [ -n "$TTS_FILTER" ]; then
   case "$name" in *"$TTS_FILTER"*) ;; *) echo "=== $name (skipped, TTS=$TTS_FILTER) ==="; return 0 ;; esac
 fi
 echo "=== $name ==="
 "$@"
}


# --- pico2wave (Pi only; sudo apt install libttspico-utils) ---
if command -v pico2wave >/dev/null 2>&1; then
 _run "0. pico2wave + plughw (recommended baseline)" bash -c "
   pico2wave -l en-US -w $WAV16 \"$TEXT\" && aplay -D $DEVICE $WAV16
 "
 echo "If this is clearest: config audioPlaybackMode plughw (or omit)."
else
 echo "=== 0. pico2wave (skipped — not installed) ==="
 echo "Pi: sudo apt install libttspico-utils"
fi


if [ "${MINIMAL:-0}" = "1" ]; then
 echo "MINIMAL=1 — stopping after baseline."
 exit 0
fi


# --- espeak ---
if command -v espeak >/dev/null 2>&1; then
 _run "1a. espeak → plughw" bash -c "
   espeak -v en-us \"$TEXT\" --stdout | sox -t wav - $WAV16 && aplay -D $DEVICE $WAV16
 "
 _run "1b. espeak + sox + hw raw" bash -c "
   espeak -v en-us \"$TEXT\" --stdout | \
     sox -t wav - -t raw -e signed-integer -b 32 -c 2 - rate -v 48000 $(gain_args) | \
     aplay -D hw:0,0 -t raw -f S32_LE -r 48000 -c 2
 "
else
 echo "=== 1. espeak (skipped) ==="
 echo "sudo apt install espeak"
fi


# --- flite ---
if command -v flite >/dev/null 2>&1; then
 _run "2a. flite → plughw" bash -c "
   flite -t \"$TEXT\" -o $WAV16 && aplay -D $DEVICE $WAV16
 "
else
 echo "=== 2. flite (skipped) ==="
 echo "sudo apt install flite"
fi


# --- say (macOS) — for local dev; aplay won't work, use afplay ---
if command -v say >/dev/null 2>&1 && [ "$(uname -s)" = "Darwin" ]; then
 _run "3. say (macOS built‑in)" say -v Samantha "\"$TEXT\""
fi


# --- pico2wave + sox variants (Pi only) ---
if command -v pico2wave >/dev/null 2>&1 && command -v sox >/dev/null 2>&1; then
 echo ""
 echo "Using GAIN_DB=$GAIN_DB for sox steps."
 pico2wave -l en-US -w "$WAV16" "$TEXT" 2>/dev/null || true

 _run "4. pico2wave + sox 48k → plughw" bash -c "
   sox $WAV16 $WAV48 rate -v 48000 $(gain_args) && sox $WAV48 -t alsa $DEVICE
 "
 _run "5. pico2wave + sox pipe → hw raw (hq48 style)" bash -c "
   sox $WAV16 -t raw -e signed-integer -b 32 -c 2 - rate -v 48000 $(gain_args) | \
     aplay -D hw:0,0 -t raw -f S32_LE -r 48000 -c 2
 "
fi


echo ""
echo "Done."



