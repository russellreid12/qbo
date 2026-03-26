# Pi 5 + Google Voice HAT audio

`pico2wave` always outputs **16 kHz, 16-bit, mono** WAV. The Voice HAT hardware wants **48 kHz** (often **S32_LE stereo**). ALSA’s **`plughw`** layer performs that conversion correctly on many systems; a fixed `convertQBO` or hand-built 32-bit WAV files can sound noisy on Pi 5 if the format does not match the driver.

## `qbo_audio` + `config.yml`

All Python playback paths use **`qbo_audio.aplay_wav_device(config)`**.

**Default (no keys in config):** `audioPlaybackMode` behaves as **`convertqbo`** → ALSA PCM **`convertQBO`**. That matches typical QBO **`/etc/asound.conf`** (e.g. HiFiBerry DAC via a plug to `hw:0,0`).

```yaml
# Pi 5 Google Voice HAT (try plughw:1,0 if card is not 0)
audioPlaybackMode: plughw

# Or force an explicit PCM / hardware node:
# audioPlaybackDevice: plughw:0,0
# audioPlaybackDevice: plughw:1,0

# Follow pcm.!default from asound.conf (same as many “aplay file.wav” setups)
# audioPlaybackMode: default

# Last resort: resample with sox to raw S32 48k stereo (QboTalk only)
# audioPlaybackMode: raw48
# audioPlaybackHwDevice: hw:0,0

# hq48 only if plughw is bad; gain only if you hear clipping
# audioPlaybackMode: hq48
# audioPlaybackGainDb: -6
```

## If playback got worse

1. Match **`audioPlaybackMode`** to your hardware ( **`convertqbo`** for HiFiBerry + `convertQBO` in **`asound.conf`**, **`plughw`** for Voice HAT).
2. Or set **`audioPlaybackDevice`** explicitly to whatever works in **`aplay -l`**.

## Test script

```bash
MINIMAL=1 bash scripts/test_audio_modes.sh
GAIN_DB=-12 bash scripts/test_audio_modes.sh
```

## Quick test

```bash
pico2wave -l en-US -w /tmp/t.wav "test one two" && aplay -D plughw:0,0 /tmp/t.wav
```

If that sounds clean on a Voice HAT, use **`audioPlaybackMode: plughw`** (or **`audioPlaybackDevice: plughw:0,0`**).
