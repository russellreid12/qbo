#!/usr/bin/env python3








import json
import os
try:
 import speech_recognition as sr  # type: ignore[import-not-found]
except ImportError:
 # The robot depends on this at runtime; if it's missing we avoid crashing
 # at import-time so other modes/tools can still run.
 sr = None
try:
 import apiai  # type: ignore[import-not-found]
except ImportError:
 apiai = None
import subprocess
import wave
import yaml
from contextlib import contextmanager

from qbo_audio import aplay_wav_shell_play_wav








def _config_int_optional(config, key):
  v = config.get(key)
  if v is None:
      return None
  try:
      return int(v)
  except (TypeError, ValueError):
      return None








@contextmanager
def _suppress_c_stderr():
    """PortAudio/ALSA/JACK log from C via fd 2; Python's redirect_stderr cannot hide it."""
    if os.environ.get("QBO_VERBOSE_LIBS"):
        yield
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved = os.dup(2)
    try:
        os.dup2(devnull, 2)
        os.close(devnull)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)


@contextmanager
def open_microphone_source(mic):
  """
  Enter sr.Microphone safely. Some speech_recognition versions swallow
  PyAudio open() errors in __enter__ and return with stream=None; then
  adjust_for_ambient_noise asserts and __exit__ raises on close(None).
  """
  if mic is None:
      raise ValueError("microphone is None")
  src = mic.__enter__()
  try:
      if getattr(src, "stream", None) is None:
          raise OSError(
              "Microphone stream did not open (ALSA/PortAudio). "
              "Try arecord -l, ~/.asoundrc, and config.yml "
              "microphoneDeviceIndex / microphoneSampleRate."
          )
      yield src
  finally:
      if getattr(src, "stream", None) is not None:
          src.__exit__(None, None, None)
      else:
          audio = getattr(src, "audio", None)
          if audio is not None:
              try:
                  audio.terminate()
              except Exception:
                  pass








class QBOtalk(object):








 def __init__(self):
     # Always define attributes up-front so later code can't fail with
     # AttributeError even if initialization steps raise/short-circuit.
     self.m = None








     self.config = yaml.safe_load(open("/opt/qbo/config.yml"))
     self.r = sr.Recognizer() if sr is not None else None
     if sr is not None and apiai is not None:
         self.ai = apiai.ApiAI(self.config["tokenAPIai"])
     else:
         self.ai = None
         if sr is not None and apiai is None:
             print("Warning: 'apiai' not installed; install with pip (see requirements-robot.txt).")
     self.Response = "hello"
     self.GetResponse = False
     self.GetAudio = False
     self.strAudio = ""








     if sr is None:
         print("Warning: 'speech_recognition' module not installed; speech capture disabled.")
         return








     # Optional overrides for Pi / ALSA (channel or rate mismatches).
     cfg_mic_index = _config_int_optional(self.config, "microphoneDeviceIndex")
     cfg_sample_rate = _config_int_optional(self.config, "microphoneSampleRate")




     # Try to find the QBO microphone by name. Accept any of the known
     # device names used across different QBO hardware revisions.
     QBO_MIC_NAMES = (
         "dmicQBO_sv",
         "googlevoicehat",
         "voicehat",
         "bluez",
         "airpods",
         "hands-free",
         "handsfree",
     )
     mic_index = None
     with _suppress_c_stderr():
         mic_names = sr.Microphone.list_microphone_names()
     for i, mic_name in enumerate(mic_names):
         if not mic_name or "_hw" in mic_name.lower() or "hw:" in mic_name.lower():
             continue
         if any(known in mic_name.lower() for known in QBO_MIC_NAMES):
             mic_index = i
             break








     try:
         if cfg_mic_index is not None:
             with _suppress_c_stderr():
                 self.m = sr.Microphone(
                     device_index=cfg_mic_index, sample_rate=cfg_sample_rate
                 )
         elif mic_index is not None:
             with _suppress_c_stderr():
                 self.m = sr.Microphone(
                     device_index=mic_index, sample_rate=cfg_sample_rate
                 )
         else:
             print("Warning: QBO microphone not found by name. Using default microphone.")
             with _suppress_c_stderr():
                 self.m = sr.Microphone(sample_rate=cfg_sample_rate)
     except OSError as e:
         # No usable microphone found – log and leave self.m as None so callers can handle it.
         print("Error initializing microphone for QBOtalk:", e)
         self.m = None








     if self.m is not None:
         try:
             with _suppress_c_stderr():
                 with open_microphone_source(self.m) as source:
                     self.r.adjust_for_ambient_noise(source)
         except Exception as e:
             print("Warning: microphone ambient calibration skipped:", e)
             self.m = None








 def Decode(self, audio):
     str_heard = ""
     try:
         if self.config["language"] == "spanish":
             str_heard = self.r.recognize_google(audio, language="es-ES")
         else:
             str_heard = self.r.recognize_google(audio)
     except sr.UnknownValueError:
         return ""
     except sr.RequestError:
         return "Could not request results from Speech Recognition service"

     self.strAudio = str_heard
     self.GetAudio = True
     print("listen: " + self.strAudio)

     str_resp = ""
     if self.ai is None:
         str_resp = str_heard
     else:
         try:
             request = self.ai.text_request()
             request.query = str_heard
             response = request.getresponse()
             data = json.loads(response.read())
             fulf = data.get("result", {}).get("fulfillment", {})
             str_resp = fulf.get("speech") or ""
         except Exception as e:
             # Legacy apiai → api.api.ai: TLS/hostname often fails today; prefer Dialogflow V2 or empty tokenAPIai.
             print("Dialogflow / apiai error:", e)
             str_resp = str_heard

     if not (str_resp or "").strip():
         str_resp = str_heard

     return str_resp








 def downsampleWav(self, src):
     print("src: " + src)
     s_read = wave.open(src, 'r')
     print("frameRate: " + str(s_read.getframerate()))
     s_read.setframerate(16000)
     print("frameRate_2: " + str(s_read.getframerate()))
     return








 def downsampleWave_2(self, src, dst, inrate, outrate, inchannels, outchannels):








     if not os.path.exists(src):
         print('Source not found!')
         return False








     if not os.path.exists(os.path.dirname(dst)):
         print("dst: " + dst)
         print("path: " + os.path.dirname(dst))
         os.makedirs(os.path.dirname(dst))








     try:
         s_read = wave.open(src, 'r')
         s_write = wave.open(dst, 'w')








     except:
         print('Failed to open files!')
         return False








     n_frames = s_read.getnframes()
     data = s_read.readframes(n_frames)








     try:
         converted = audioop.ratecv(data, 2, inchannels, inrate, outrate, None)
         if outchannels == 1:
             converted = audioop.tomono(converted[0], 2, 1, 0)








     except:
         print('Failed to downsample wav')
         return False








     try:
         s_write.setparams((outchannels, 2, outrate, 0, 'NONE', 'Uncompressed'))
         s_write.writeframes(converted)








     except:
         print('Failed to write wav')
         return False








     try:
         s_read.close()
         s_write.close()








     except:
         print('Failed to close wav files')
         return False








     return True








 def _play_pico2wave(self, text, lang):
     """
     Play TTS from pico2wave on Google Voice HAT / Pi 5.








     config.yml (all optional):
       audioPlaybackMode: plughw          # default in code — simplest
       audioPlaybackDevice: plughw:0,0
       # Only if plughw is unusable: audioPlaybackMode: hq48
       # Only if hq48 clips: audioPlaybackGainDb: -6








     If audio got worse: remove audioPlaybackMode / audioPlaybackGainDb lines
     so TTS uses plain pico2wave + plughw again.
     """
     vol = self.config["volume"]
     wav = "/opt/qbo/sounds/pico2wave.wav"
     mode = str(self.config.get("audioPlaybackMode", "plughw")).lower()








     gen = (
         'pico2wave -l "{lang}" -w {wav} "<volume level=\'{vol}\'>{text}"'
     ).format(lang=lang, wav=wav, vol=vol, text=text)








     hw = self.config.get("audioPlaybackHwDevice", "hw:0,0")
     try:
         gain_db = float(self.config.get("audioPlaybackGainDb", 0))
     except (TypeError, ValueError):
         gain_db = 0.0
     gain_sox = " gain {:.1f}".format(gain_db) if gain_db != 0 else ""








     if mode == "hq48":
         # Bypass ALSA resampling: sox rate -v + gain (clip often sounds like noise).
         cmd = (
             "{gen} && sox {wav} -t raw -e signed-integer -b 32 -c 2 - rate -v 48000{gain} "
             "| aplay -D {hw} -t raw -f S32_LE -r 48000 -c 2"
         ).format(gen=gen, wav=wav, hw=hw, gain=gain_sox)
     elif mode == "raw48":
         g0 = ("gain {:.1f} ".format(gain_db) if gain_db != 0 else "")
         cmd = (
             "{gen} && sox {wav} {g0}-t raw -r 48000 -e signed-integer -b 32 -c 2 - "
             "| aplay -D {hw} -t raw -f S32_LE -r 48000 -c 2"
         ).format(gen=gen, wav=wav, hw=hw, g0=g0)
     else:
         cmd = "{gen} && {aplay}".format(
             gen=gen, aplay=aplay_wav_shell_play_wav(self.config, wav)
         )








     subprocess.call(cmd, shell=True)








 def SpeechText(self, text_to_speech):
     lang = "es-ES" if self.config["language"] == "spanish" else "en-US"
     self._play_pico2wave(text_to_speech, lang)








 def SpeechText_2(self, text_to_speech, text_spain):
     if self.config["language"] == "spanish":
         self._play_pico2wave(text_spain, "es-ES")
     else:
         self._play_pico2wave(text_to_speech, "en-US")








 def callback(self, recognizer, audio):
     try:
         self.Response = self.Decode(audio)
         print("Google say ")
     except Exception as e:
         print("QBOtalk callback error:", e)
         self.Response = ""
     # Always clear — otherwise Listening stays True forever and face LEDs / hotword stay broken.
     self.GetResponse = True








 def callback_listen(self, recognizer, audio):
     print("callback listen")
     try:
         if self.config["language"] == "spanish":
             self.strAudio = self.r.recognize_google(audio, language="es-ES")
         else:
             self.strAudio = self.r.recognize_google(audio)


         self.GetAudio = True

         print("listen: " + self.strAudio)


     except:
         print("callback listen exception")
         self.strAudio = ""
         return




 def Start(self):


     print("Say something!")
     self.r.operation_timeout = 10



     if self.m is None:
         print("Warning: microphone not initialized; cannot start speech capture.")
         return
     if self.r is None:
         print("Warning: speech recognizer not available.")
         return


     with _suppress_c_stderr():
         with open_microphone_source(self.m) as source:
             audio = self.r.listen(source=source, timeout=2)


     response = self.Decode(audio)
     self.SpeechText(response)



 def StartBack(self):
     if self.m is None:
         print("Warning: microphone not initialized; cannot start background listening.")
         return None
     if self.r is None:
         print("Warning: speech recognizer not available.")
         return None



     with _suppress_c_stderr():
         with open_microphone_source(self.m) as source:
             self.r.adjust_for_ambient_noise(source)


     print("start background listening")


     with _suppress_c_stderr():
         return self.r.listen_in_background(self.m, self.callback)




 def StartBackListen(self):
     if self.m is None:
         print("Warning: microphone not initialized; cannot start background listening (listen-only).")
         return None
     if self.r is None:
         print("Warning: speech recognizer not available.")
         return None



     with _suppress_c_stderr():
         with open_microphone_source(self.m) as source:
             self.r.adjust_for_ambient_noise(source)


     print("start background only listening")



     with _suppress_c_stderr():
         return self.r.listen_in_background(self.m, self.callback_listen)





