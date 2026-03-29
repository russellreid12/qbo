"""Central ALSA playback device for QBO (HiFiBerry / convertQBO, Voice HAT / plughw, etc.)."""

import shlex
import subprocess

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
    if len(parts) == 1:
        return parts[0]
    return "(" + " || ".join(parts) + ")"


def subprocess_aplay_wav(config, path: str, quiet: bool = True) -> int:
    """Try each PCM from aplay_wav_devices_to_try; return 0 if any aplay succeeds."""
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
