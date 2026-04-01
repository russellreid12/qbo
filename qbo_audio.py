"""Central ALSA playback device for QBO (HiFiBerry / convertQBO, Voice HAT / plughw, etc.)."""

import shlex
import subprocess
import time

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
    Perform a one-time system-wide sleep (boot delay) if not yet ready.
    Uses a temporary file in /tmp/ to coordinate across different processes
    (e.g., Start.py and PiFaceFast.py).
    """
    global _AUDIO_READY
    if _AUDIO_READY:
        return
    
    flag_path = "/tmp/qbo_audio.ready"
    if os.path.exists(flag_path):
        _AUDIO_READY = True
        return

    delay = config.get("audioBootDelay", 0)
    if delay:
        try:
            time.sleep(float(delay))
        except (TypeError, ValueError):
            pass
    
    # Mark as ready for all future processes this boot
    try:
        with open(flag_path, "w") as f:
            f.write("ready")
    except Exception:
        pass
    _AUDIO_READY = True


def aplay_wav_shell_play_wav(config, wav_path: str) -> str:
    """
    Shell fragment: play wav with aplay, trying each PCM until one succeeds.
    """
    wav_q = shlex.quote(wav_path)
    devs = aplay_wav_devices_to_try(config)
    parts = []
    for i, d in enumerate(devs):
        redir = " 2>/dev/null" if i + 1 < len(devs) else ""
        parts.append("aplay -q -D {} {}{}".format(shlex.quote(d), wav_q, redir))
    
    res = "(" + " || ".join(parts) + ")" if len(parts) > 1 else parts[0]
    
    # Optional cross-process delay for Bluetooth sinks at boot
    global _AUDIO_READY
    flag_path = "/tmp/qbo_audio.ready"
    if not _AUDIO_READY and not os.path.exists(flag_path):
        delay = config.get("audioBootDelay", 0)
        if delay:
            _AUDIO_READY = True
            # The shell command will both wait and create the flag for others
            return "sleep {} && touch {} && {}".format(delay, flag_path, res)
        
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
