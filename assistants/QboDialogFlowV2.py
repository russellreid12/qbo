#!/usr/bin/env python3

import uuid
import os
import yaml
import subprocess
import pyaudio
import wave
import tempfile
import threading
import time
import random
import speech_recognition as sr

from qbo_audio import aplay_wav_shell_play_wav, wait_for_audio_ready

# ---------------------------------------------------------------------------
# Optional LLM providers — imported lazily so missing packages don't crash
# the module when the feature isn't configured.
# ---------------------------------------------------------------------------
try:
    import openai as _openai_module
except ImportError:
    _openai_module = None

try:
    import google.generativeai as _genai_module
except ImportError:
    _genai_module = None


class QboDialogFlowV2(object):
    def __init__(self, credentialFile="/opt/qbo/.config/dialogflowv2.json"):
        self.config = yaml.safe_load(open("/opt/qbo/config.yml"))
        self.project_id = self.config["dialogflowv2_projectid"]
        self.credentialFile = credentialFile
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentialFile
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.CHUNK = 1024
        self.RECORD_SECONDS = self.config['SpeechToTextListeningTime']
        # Required flags by PiFaceFast.py main loop
        self.GetAudio = False
        self.strAudio = ""
        self.GetResponse = False
        self.Response = ""
        self.r = sr.Recognizer()
        self.controller = None
        self.is_animating = False

        # Multi-turn conversation memory (shared across OpenAI / Gemini)
        self._conversation_history = []

        # Robot persona — customise in config.yml under 'robot_persona'
        self._persona = self.config.get(
            "robot_persona",
            (
                "You are QBO, a friendly and curious social robot. "
                "Keep every reply short — 1 to 2 sentences — and conversational. "
                "Never use markdown, bullet points, or lists in your responses."
            )
        )

        # ------------------------------------------------------------------
        # LLM provider selection
        # Priority: config key 'llm_provider' → 'openai' | 'gemini' | 'none'
        # Falls back gracefully if the required library or key is missing.
        # ------------------------------------------------------------------
        self._llm_provider = str(self.config.get("llm_provider", "none")).lower().strip()
        self._openai_client = None
        self._gemini_model = None

        if self._llm_provider == "openai":
            self._init_openai()
        elif self._llm_provider == "gemini":
            self._init_gemini()
        else:
            print("QboDialogFlowV2: LLM disabled (set llm_provider: openai or gemini in config.yml).")

    # -----------------------------------------------------------------------
    # Provider initialisation helpers
    # -----------------------------------------------------------------------

    def _init_openai(self):
        """Set up the OpenAI client using config key 'openai_api_key'."""
        if _openai_module is None:
            print("QboDialogFlowV2: openai package not installed — run: pip3 install openai")
            return
        api_key = self.config.get("openai_api_key", "").strip()
        if not api_key:
            print("QboDialogFlowV2: 'openai_api_key' is empty in config.yml — LLM disabled.")
            return
        try:
            self._openai_client = _openai_module.OpenAI(api_key=api_key)
            model = self.config.get("openai_model", "gpt-4o-mini")
            print("QboDialogFlowV2: OpenAI ready — model: {}".format(model))
        except Exception as e:
            print("QboDialogFlowV2: OpenAI init failed: {}".format(e))

    def _init_gemini(self):
        """Set up the Gemini client using config key 'gemini_api_key'."""
        if _genai_module is None:
            print("QboDialogFlowV2: google-generativeai not installed — run: pip3 install google-generativeai")
            return
        api_key = self.config.get("gemini_api_key", "").strip()
        if not api_key:
            print("QboDialogFlowV2: 'gemini_api_key' is empty in config.yml — LLM disabled.")
            return
        try:
            _genai_module.configure(api_key=api_key)
            model_name = self.config.get("gemini_model", "gemini-1.5-flash")
            self._gemini_model = _genai_module.GenerativeModel(
                model_name=model_name,
                system_instruction=self._persona,
            )
            # Start a persistent chat session so Gemini maintains its own context
            self._gemini_chat = self._gemini_model.start_chat(history=[])
            print("QboDialogFlowV2: Gemini ready — model: {}".format(model_name))
        except Exception as e:
            print("QboDialogFlowV2: Gemini init failed: {}".format(e))

    # -----------------------------------------------------------------------
    # Controller binding
    # -----------------------------------------------------------------------

    def set_controller(self, controller):
        """Bind the hardware controller for mouth sync animations."""
        self.controller = controller

    # -----------------------------------------------------------------------
    # Audio recording
    # -----------------------------------------------------------------------

    def record_wav(self):
        audio = pyaudio.PyAudio()
        stream = audio.open(format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE, input=True, frames_per_buffer=self.CHUNK)

        print("recording...")
        frames = []
        for i in range(0, int(self.RATE / self.CHUNK * self.RECORD_SECONDS)):
            data = stream.read(self.CHUNK)
            frames.append(data)
        print("finished recording")

        stream.stop_stream()
        stream.close()
        audio.terminate()

        tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        waveFile = wave.open(tmp, 'wb')
        waveFile.setnchannels(self.CHANNELS)
        waveFile.setsampwidth(audio.get_sample_size(self.FORMAT))
        waveFile.setframerate(self.RATE)
        waveFile.writeframes(b''.join(frames))
        waveFile.close()

        self.audio_file_path = tmp.name

    def callback_listen(self, recognizer, audio):
        print("callback listen")
        try:
            if self.config["language"] == "spanish":
                self.strAudio = self.r.recognize_google(audio, language="es-ES")
            else:
                self.strAudio = self.r.recognize_google(audio)
            self.GetAudio = True
            print("listen: " + self.strAudio)
        except Exception:
            print("callback listen exception")
            self.strAudio = ""

    # -----------------------------------------------------------------------
    # Dialogflow intent detection
    # -----------------------------------------------------------------------

    def detect_intent_stream(self):
        # google-cloud-dialogflow replaces the discontinued dialogflow-v2 package.
        # Classes are accessed directly on the module (no .enums. or .types. prefix).
        from google.cloud import dialogflow_v2 as dialogflow
        session_client = dialogflow.SessionsClient()

        session_id = uuid.uuid4()

        language_code = 'en-US'
        if self.config["language"] == "spanish":
            language_code = 'es-ES'

        audio_encoding = dialogflow.AudioEncoding.AUDIO_ENCODING_LINEAR_16
        sample_rate_hertz = 16000

        session_path = session_client.session_path(self.project_id, session_id)

        def request_generator(audio_config, audio_file_path):
            query_input = dialogflow.QueryInput(audio_config=audio_config)
            yield dialogflow.StreamingDetectIntentRequest(
                session=session_path, query_input=query_input)
            with open(audio_file_path, 'rb') as audio_file:
                while True:
                    chunk = audio_file.read(4096)
                    if not chunk:
                        break
                    yield dialogflow.StreamingDetectIntentRequest(
                        input_audio=chunk)

        audio_config = dialogflow.InputAudioConfig(
            audio_encoding=audio_encoding, language_code=language_code,
            sample_rate_hertz=sample_rate_hertz)

        requests = request_generator(audio_config, self.audio_file_path)
        responses = session_client.streaming_detect_intent(requests)

        for response in responses:
            print('Intermediate transcript: "{}".'.format(
                response.recognition_result.transcript))

        query_result = response.query_result

        user_query   = format(query_result.query_text)
        intent_name  = format(query_result.intent.display_name)
        df_fallback  = format(query_result.fulfillment_text)

        print('=' * 20)
        print('Query text: {}'.format(user_query))
        print('Detected intent: {} (confidence: {:.2f})'.format(
            intent_name, query_result.intent_detection_confidence))
        print('Dialogflow response: {}'.format(df_fallback))

        # Route through configured LLM for a natural reply; fall back on error.
        final_response = self._llm_respond(user_query, intent_name, df_fallback)
        self.SpeechText(final_response)
        os.remove(self.audio_file_path)

    def detect_intent_gemini_only(self):
        """
        STT via Google Speech Recognition, then route directly to Gemini.
        Skips Dialogflow intent detection entirely — no cloud NLU round-trip.
        """
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        lang = "es-ES" if self.config["language"] == "spanish" else "en-US"

        try:
            with sr.AudioFile(self.audio_file_path) as source:
                audio = recognizer.record(source)
            user_text = recognizer.recognize_google(audio, language=lang)
            print("STT transcript: {}".format(user_text))
        except sr.UnknownValueError:
            print("STT: could not understand audio")
            user_text = ""
        except Exception as e:
            print("STT error: {}".format(e))
            user_text = ""
        finally:
            try:
                os.remove(self.audio_file_path)
            except Exception:
                pass

        if not user_text:
            return

        final_response = self._respond_gemini(user_text, fallback="Sorry, I didn't catch that.")
        self.SpeechText(final_response)

    # -----------------------------------------------------------------------
    # LLM response generation
    # -----------------------------------------------------------------------

    def _llm_respond(self, user_text, intent_name, df_fallback_text):
        """
        Generate a natural conversational reply using the configured LLM.

        - OpenAI: uses chat.completions with full conversation_history list.
        - Gemini: uses a persistent GenerativeModel chat session.
        - Neither configured or call fails: returns df_fallback_text as-is.

        The detected Dialogflow intent is injected as a hint so the LLM
        understands the topic without needing its own NLU.
        """
        if not user_text:
            return df_fallback_text

        # Build an intent hint to steer the LLM without overriding its fluency
        intent_hint = ""
        if intent_name and "fallback" not in intent_name.lower() and "default" not in intent_name.lower():
            intent_hint = " [Detected intent: {}]".format(intent_name)

        augmented_query = user_text + intent_hint

        if self._llm_provider == "openai" and self._openai_client is not None:
            return self._respond_openai(augmented_query, df_fallback_text)

        if self._llm_provider == "gemini" and self._gemini_model is not None:
            return self._respond_gemini(augmented_query, df_fallback_text)

        # No LLM configured — use Dialogflow's canned response
        return df_fallback_text

    def _respond_openai(self, user_text, fallback):
        """Call OpenAI chat completions. Maintains multi-turn history."""
        # Append the user turn
        self._conversation_history.append({"role": "user", "content": user_text})

        # Cap history to last 10 turns (5 exchanges) to control token usage
        history = self._conversation_history[-10:]

        try:
            model = self.config.get("openai_model", "gpt-4o-mini")
            max_tok = int(self.config.get("llm_max_tokens", 80))
            temperature = float(self.config.get("llm_temperature", 0.7))

            resp = self._openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": self._persona}] + history,
                max_tokens=max_tok,
                temperature=temperature,
            )
            reply = resp.choices[0].message.content.strip()
            # Store assistant turn for next exchange
            self._conversation_history.append({"role": "assistant", "content": reply})
            print("OpenAI reply: {}".format(reply))
            return reply
        except Exception as e:
            print("QboDialogFlowV2: OpenAI error — {}, using Dialogflow fallback.".format(e))
            # Remove the user turn we just added so history stays clean
            if self._conversation_history and self._conversation_history[-1]["role"] == "user":
                self._conversation_history.pop()
            return fallback

    def _respond_gemini(self, user_text, fallback):
        """Call Gemini via a persistent chat session. History managed by the SDK."""
        try:
            temperature = float(self.config.get("llm_temperature", 0.7))
            max_tok = int(self.config.get("llm_max_tokens", 80))

            gen_config = _genai_module.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tok,
            )
            response = self._gemini_chat.send_message(
                user_text,
                generation_config=gen_config,
            )
            reply = response.text.strip()
            print("Gemini reply: {}".format(reply))
            return reply
        except Exception as e:
            print("QboDialogFlowV2: Gemini error — {}, using Dialogflow fallback.".format(e))
            return fallback

    # -----------------------------------------------------------------------
    # Mouth animation
    # -----------------------------------------------------------------------

    def _animate_mouth_loop(self):
        """Flickers the mouth LEDs while is_animating is True."""
        mouth_patterns = [0x110E00, 0x0E1100, 0x1F1F00, 0x1B1F0E04]
        while self.is_animating:
            if self.controller:
                pattern = random.choice(mouth_patterns)
                self.controller.SetMouth(pattern)
            time.sleep(0.15)
        if self.controller:
            self.controller.SetMouth(0)

    # -----------------------------------------------------------------------
    # Text-to-speech
    # -----------------------------------------------------------------------

    def _play_pico2wave(self, text, lang):
        import shlex
        # Synchronize: ensure Bluetooth / AirPod delay completes before starting mouth
        wait_for_audio_ready(self.config)

        vol = self.config.get("volume", 100)
        wav = "/opt/qbo/sounds/pico2wave.wav"
        mode = str(self.config.get("audioPlaybackMode", "plughw")).lower()
        
        # Pre-clean text to avoid shell/SSML issues
        clean_text = str(text).replace('"', '').replace("'", "")
        
        gen = (
            f'pico2wave -l {shlex.quote(lang)} '
            f'-w {shlex.quote(wav)} '
            f'"<volume level=\'{vol}\'>{clean_text}"'
        )
        
        hw = self.config.get("audioPlaybackHwDevice") or self.config.get("audioPlaybackDevice") or "default"
        try:
            gain_db = float(self.config.get("audioPlaybackGainDb", 0))
        except (TypeError, ValueError):
            gain_db = 0.0
        gain_sox = " gain {:.1f}".format(gain_db) if gain_db != 0 else ""

        if mode == "hq48":
            cmd = (
                "{gen} && sox {wav} -t raw -e signed-integer -b 32 -c 2 - rate -v 48000{gain} "
                "| aplay -D {hw} -t raw -f S32_LE -r 48000 -c 2"
            ).format(gen=gen, wav=shlex.quote(wav), hw=shlex.quote(str(hw)), gain=gain_sox)
        elif mode == "raw48":
            g0 = ("gain {:.1f} ".format(gain_db) if gain_db != 0 else "")
            cmd = (
                "{gen} && sox {wav} {g0}-t raw -r 48000 -e signed-integer -b 32 -c 2 - "
                "| aplay -D {hw} -t raw -f S32_LE -r 48000 -c 2"
            ).format(gen=gen, wav=shlex.quote(wav), hw=shlex.quote(str(hw)), g0=g0)
        else:
            cmd = "{gen} && {aplay}".format(
                gen=gen, aplay=aplay_wav_shell_play_wav(self.config, wav)
            )

        self.is_animating = True
        anim_thread = threading.Thread(target=self._animate_mouth_loop)
        anim_thread.daemon = True
        anim_thread.start()
        try:
            subprocess.call(cmd, shell=True)
        finally:
            self.is_animating = False
            anim_thread.join(timeout=1.0)

    def SpeechText(self, text_to_speech):
        lang = "es-ES" if self.config["language"] == "spanish" else "en-US"
        self._play_pico2wave(text_to_speech, lang)


if __name__ == '__main__':
    talk = QboDialogFlowV2()
    talk.record_wav()
    talk.detect_intent_stream()
