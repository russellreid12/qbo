#!/usr/bin/env python3




import importlib
import sys
import re
import yaml
import subprocess
import threading
import time
import random

from qbo_audio import aplay_wav_shell_play_wav, subprocess_aplay_wav




# read config file
config = yaml.safe_load(open("/opt/qbo/config.yml"))




# Voice options per language — V3 neural voices sound significantly better
VOICES = {
   'english': 'en-US_MichaelV3Voice',  # Options: MichaelV3Voice, AllisonV3Voice, LisaV3Voice, EmilyV3Voice
   'spanish': 'es-ES_EnriqueV3Voice',  # Options: EnriqueV3Voice, LauraV3Voice
}




# SSML templates give the TTS engine extra pronunciation hints.
# Wrap text in <speak> and add optional pauses, emphasis, or rate tweaks here.
SSML_TEMPLATE = '<speak>{}</speak>'

# Global controller for mouth sync
controller = None
is_animating = False

def set_controller(ctrl):
    global controller
    controller = ctrl

def _animate_mouth_loop():
    """Flickers the mouth LEDs while is_animating is True."""
    global is_animating
    mouth_patterns = [0x110E00, 0x0E1100, 0x1F1F00, 0x1B1F0E04]
    while is_animating:
        if controller:
            pattern = random.choice(mouth_patterns)
            controller.SetMouth(pattern)
        time.sleep(0.15)
    if controller:
        controller.SetMouth(0)




# Characters that can confuse TTS if read literally
_CLEANUP_RE = re.compile(r'[<>{}\[\]|\\]')








def _clean_text(text: str) -> str:
   """Strip characters that break TTS or SSML parsing."""
   return _CLEANUP_RE.sub('', text).strip()








def _ssml(text: str) -> str:
   """Wrap cleaned text in a basic SSML envelope."""
   return SSML_TEMPLATE.format(_clean_text(text))



def _try_watson_tts(text: str, voice: str) -> bool:
   """
   Attempt to synthesize speech via IBM Watson TTS (modern ibm_watson SDK).
   Returns True on success, False on any failure.
   """
   try:
       ibm_watson = importlib.import_module("ibm_watson")
       ibm_core = importlib.import_module("ibm_cloud_sdk_core.authenticators")




       IAMAuthenticator = getattr(ibm_core, "IAMAuthenticator")
       TextToSpeechV1 = getattr(ibm_watson, "TextToSpeechV1")




       authenticator = IAMAuthenticator(config['TextToSpeechAPIKey'])
       tts = TextToSpeechV1(authenticator=authenticator)
       tts.set_service_url(config['TextToSpeechURL'])
       tts.set_http_config({'verify': False})




       # Use SSML for better prosody; fall back to plain text on parse error
       ssml_text = _ssml(text)
       try:
           result = tts.synthesize(
               ssml_text,
               accept='audio/wav',
               voice=voice,
               # SSML input unlocks <break>, <emphasis>, <prosody> etc.
           ).get_result()
       except Exception:
           # If SSML is rejected (e.g. markup error), retry with plain text
           result = tts.synthesize(
               _clean_text(text),
               accept='audio/wav',
               voice=voice,
           ).get_result()




       with open('/opt/qbo/sounds/watson.wav', 'wb') as audio_file:
           audio_file.write(result.content)




        global is_animating
        is_animating = True
        anim_thread = threading.Thread(target=_animate_mouth_loop)
        anim_thread.daemon = True
        anim_thread.start()

        try:
            subprocess_aplay_wav(config, "/opt/qbo/sounds/watson.wav")
        finally:
            is_animating = False
            anim_thread.join(timeout=1.0)
        return True




   except ImportError:
       print("ibm_watson not installed. Run: pip install ibm-watson ibm-cloud-sdk-core")
       return False
   except Exception as e:
       print(f"Watson TTS error: {e}")
       return False








def _speak_pico2wave(text: str, lang_code: str) -> None:
   """
   Fallback: synthesize with pico2wave (offline, no internet needed).
   pico2wave has limited SSML support — pass plain text only.
   """
   clean = _clean_text(text)
   # Escape single quotes for the shell command
   clean = clean.replace("'", "'\\''")
   _wav = "/opt/qbo/sounds/pico2wave.wav"
   cmd = (
       f"pico2wave -l \"{lang_code}\" "
       f"-w {_wav} "
       f"\"<volume level='{config['volume']}'>{clean}\" "
       f"&& {aplay_wav_shell_play_wav(config, _wav)}"
   )
    global is_animating
    is_animating = True
    anim_thread = threading.Thread(target=_animate_mouth_loop)
    anim_thread.daemon = True
    anim_thread.start()

    try:
        subprocess.call(cmd, shell=True)
    finally:
        is_animating = False
        anim_thread.join(timeout=1.0)





# Fallback messages when Watson is unreachable
_WATSON_UNAVAILABLE = {
   'english': (
       "en-US",
       "I cannot connect to Watson. Watson services are disabled. "
       "Please restart Q B O and check your internet connection."
   ),
   'spanish': (
       "es-ES",
       "No es posible establecer conexión con Watson. Los servicios de Watson están deshabilitados. "
       "Por favor, reinicia Q B O y comprueba tu conexión a Internet."
   ),
}








def SpeechText_2(text_english: str, text_spain: str, forceStandalone: bool = False) -> None:
   """
   Speak text using Watson TTS when available, pico2wave otherwise.




   Args:
       text_english:    English text to speak.
       text_spain:      Spanish text to speak.
       forceStandalone: Skip Watson entirely and use pico2wave directly.
   """
   lang = config.get('language', 'english')
   is_spanish = (lang == 'spanish')
   lang_code = 'es-ES' if is_spanish else 'en-US'
   text = text_spain if is_spanish else text_english
   voice = VOICES['spanish'] if is_spanish else VOICES['english']




   use_watson = (config.get('distro') == 'ibmwatson') and not forceStandalone




   if use_watson:
       success = _try_watson_tts(text, voice)
       if not success:
           # Watson failed — announce it via pico2wave, then silence Watson
           fallback_lang, fallback_text = _WATSON_UNAVAILABLE['spanish' if is_spanish else 'english']
           _speak_pico2wave(fallback_text, fallback_lang)
   else:
       _speak_pico2wave(text, lang_code)








if __name__ == "__main__":
   action = sys.argv[1] if len(sys.argv) > 1 else "default"




   if action == "custom":
       if len(sys.argv) < 3:
           print("Usage: SpeechText.py custom <text>")
           sys.exit(1)
       custom = sys.argv[2]
       SpeechText_2(custom, custom)




   elif action == "update":
       SpeechText_2(
           "Update completed. Wait while I restart.",
           "El sistema se ha actualizado correctamente. Espera mientras reinicio."
       )




   else:
       SpeechText_2("Hi. I am Cubo", "Hola. Soy Cubo")


