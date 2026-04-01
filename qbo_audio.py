"""Central ALSA playback device for QBO (HiFiBerry / convertQBO, Voice HAT / plughw, etc.)."""

import shlex
import subprocess
import time
import sys
import os

_AUDIO_READY = False

# When config.yml omits audio keys, match typical /etc/asound.conf (playback → convertQBO).
DEFAULT_AUDIO_PLAYBACK_MODE = "convertQBO"

# Tried after pulse/default when audioPlaybackAutoFallback is true (Bluetooth late at boot).
_AUTO_FALLBACK_ORDER = ("plughw:0,0", "plughw:1,0", "convertQBO")


def _primary_uses_session_audio(primary: str) -> bool:
    """True if this PCM typically needs PipeWire/Pulse (often missing at @reboot / for user qbo)."""
    p = (primary or "").lower().strip()
    if p in ("pulse", "default", "sysdefault"):
        return True
    if "pulse" in p or "pipewire" in p:
        return True
    return False


def _aplay_wav_primary_device(config):
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


def aplay_wav_device(config):
    """Primary ALSA PCM (backward compatible)."""
    return _aplay_wav_primary_device(config)


def aplay_wav_devices_to_try(config):
    """
    Ordered PCMs for playback. When primary is pulse or default, onboard fallbacks are
    appended so @reboot works before Bluetooth/PipeWire is ready (unless disabled).
    """
    primary = _aplay_wav_primary_device(config)
    out = []
    for d in (primary,):
        if d not in out:
            out.append(d)
    fb = config.get("audioPlaybackFallbackDevice")
    if fb is not None and str(fb).strip():
        d = str(fb).strip()
        if d not in out:
            out.append(d)
        return out
    if config.get("audioPlaybackAutoFallback") is False:
        return out
    if _primary_uses_session_audio(primary):
        for d in _AUTO_FALLBACK_ORDER:
            if d not in out:
                out.append(d)
    return out


def aplay_wav_device_quoted(config):
    """Primary PCM escaped for shell=True when only one device is used."""
    return shlex.quote(aplay_wav_device(config))


def wait_for_audio_ready(config):
    """
    Perform a one-time sleep (boot delay) if not yet ready.
    This can be called from Python BEFORE starting mouth animation to keep them in sync.
    """
    global _AUDIO_READY
    if _AUDIO_READY:
        return
    
    delay = config.get("audioBootDelay", 0)
    if delay:
        try:
            time.sleep(float(delay))
        except (TypeError, ValueError):
            pass
    _AUDIO_READY = True


def aplay_wav_shell_play_wav(config, wav_path: str) -> str:
    """
    Shell fragment: play wav with aplay, trying each PCM until one succeeds.
    Stderr from failed tries is discarded so ALSA pulse.c noise does not fill logs
    when onboard audio succeeds next.
    """
    wav_q = shlex.quote(wav_path)
    devs = aplay_wav_devices_to_try(config)
    parts = []
    for i, d in enumerate(devs):
        # Only the last attempt keeps stderr (easier debugging if everything fails).
        redir = " 2>/dev/null" if i + 1 < len(devs) else ""
        parts.append("aplay -q -D {} {}{}".format(shlex.quote(d), wav_q, redir))
    
    res = "(" + " || ".join(parts) + ")" if len(parts) > 1 else parts[0]
    
    # Optional one-time delay for Bluetooth sinks at boot
    global _AUDIO_READY
    if not _AUDIO_READY:
        delay = config.get("audioBootDelay", 0)
        if delay:
            _AUDIO_READY = True
            return "sleep {} && {}".format(delay, res)
        
    return res


def subprocess_aplay_wav(config, path: str, quiet: bool = True) -> int:
    """Try each PCM from aplay_wav_devices_to_try; return 0 if any aplay succeeds."""
    wait_for_audio_ready(config)

    prefix = ["aplay"] + (["-q"] if quiet else []) + ["-D"]
    devs = aplay_wav_devices_to_try(config)
    prefix = ["aplay"] + (["-q"] if quiet else []) + ["-D"]
    devs = aplay_wav_devices_to_try(config)
    for i, dev in enumerate(devs):
        kwargs = {}
        if i + 1 < len(devs):
            kwargs["stderr"] = subprocess.DEVNULL
        r = subprocess.call(prefix + [dev, path], **kwargs)
        if r == 0:
            return 0
    return 1


def aplay_stdin_shell_play_chain(config) -> str:
    """Shell fragment: read raw audio from stdin (e.g. espeak | aplay), try each PCM."""
    devs = aplay_wav_devices_to_try(config)
    parts = []
    for i, d in enumerate(devs):
        redir = " 2>/dev/null" if i + 1 < len(devs) else ""
        parts.append("aplay -q -D {} -{}".format(shlex.quote(d), redir))
    if len(parts) == 1:
        return parts[0]
    return "(" + " || ".join(parts) + ")"


def wait_for_audio_hardware_visible(max_retries=10, retry_delay=2):
	"""Wait for at least one ALSA soundcard to be visible in 'aplay -l'."""
	print("qbo_audio: checking for audio hardware...")
	for i in range(max_retries):
		try:
			# Check if 'aplay -l' shows any cards
			res = subprocess.run(["aplay", "-l"], capture_output=True, text=True)
			if "card" in res.stdout.lower():
				print("qbo_audio: audio hardware detected.")
				return True
		except Exception:
			pass
		print(f"qbo_audio: no audio hardware found yet (attempt {i+1}), waiting...")
		time.sleep(retry_delay)
	return False
