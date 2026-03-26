"""Central ALSA playback device for QBO (HiFiBerry / convertQBO, Voice HAT / plughw, etc.)."""

import shlex

# When config.yml omits audio keys, match typical /etc/asound.conf (playback → convertQBO).
DEFAULT_AUDIO_PLAYBACK_MODE = "convertQBO"


def aplay_wav_device(config):
    """
    PCM name for: aplay -D <name> file.wav

    config.yml (optional):
      audioPlaybackDevice: <any ALSA PCM>   # highest priority if set
      audioPlaybackMode: convertQBO | plughw | default

    Modes (if audioPlaybackDevice unset):
      convertqbo — use PCM "convertQBO" (HiFiBerry + plug chain in asound.conf)
      plughw     — use "plughw:0,0" (Pi 5 Google Voice HAT style; try plughw:1,0 if needed)
      default    — use ALSA "default" (follows pcm.!default in asound.conf / .asoundrc)
    """
    dev = config.get("audioPlaybackDevice")
    if dev is not None and str(dev).strip():
        return str(dev).strip()
    mode = str(config.get("audioPlaybackMode", DEFAULT_AUDIO_PLAYBACK_MODE)).lower()
    if mode == "plughw":
        return "plughw:0,0"
    if mode in ("default", "alsa_default"):
        return "default"
    # convertqbo and unknown → legacy QBO installer PCM
    return "convertQBO"


def aplay_wav_device_quoted(config):
    """PCM name escaped for shell=True pipelines (pico2wave | aplay, espeak | aplay)."""
    return shlex.quote(aplay_wav_device(config))
