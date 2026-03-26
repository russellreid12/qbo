# Pi 5 + Google Voice HAT audio

`pico2wave` always outputs **16 kHz, 16-bit, mono** WAV. The Voice HAT hardware wants **48 kHz** (often **S32_LE stereo**). ALSA’s **`plughw`** layer performs that conversion correctly on many systems; a fixed `convertQBO` or hand-built 32-bit WAV files can sound noisy on Pi 5 if the format does not match the driver.

## `config.yml` (optional)

```yaml
# Default for Pi 5 (recommended first try)
audioPlaybackMode: plughw
audioPlaybackDevice: plughw:0,0

# If the sound card is not index 0, e.g. card 1:
# audioPlaybackDevice: plughw:1,0

# Legacy Pi 3 style (only if /etc/asound.conf defines convertQBO correctly)
# audioPlaybackMode: convertQBO
# audioPlaybackDevice: convertQBO

# Last resort: resample with sox to raw S32 48k stereo, play to hardware
# audioPlaybackMode: raw48
# audioPlaybackHwDevice: hw:0,0

# hq48 only if plughw is bad; gain only if you hear clipping (default is 0)
# audioPlaybackMode: hq48
# audioPlaybackGainDb: -6
```

## If playback got worse

1. In **`config.yml`**, remove **`audioPlaybackMode`**, **`audioPlaybackGainDb`**, and **`audioPlaybackDevice`** (or set mode to **`plughw`** only).
2. Redeploy **`QboTalk.py`** — default is **pico2wave + aplay plughw**, no sox.

## Test script

```bash
# Only the simple path (pico2wave + plughw)
MINIMAL=1 bash scripts/test_audio_modes.sh

# Full comparisons; optional clipping fix
GAIN_DB=-12 bash scripts/test_audio_modes.sh
```

`QboTalk` uses these keys. Other modules (`Speak.py`, `Start.py`, etc.) still use `convertQBO` until updated; point `convertQBO` at a **plug → plughw** chain in `/etc/asound.conf` for consistent behaviour.

## Quick test

```bash
pico2wave -l en-US -w /tmp/t.wav "test one two" && aplay -D plughw:0,0 /tmp/t.wav
```

If that sounds clean, use `audioPlaybackMode: plughw` and the same device.
