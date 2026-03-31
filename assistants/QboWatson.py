#!/usr/bin/env python3


import subprocess
import wave
import pyaudio
import tempfile
import yaml
import threading
import time
import random


# Migrated from watson_developer_cloud to ibm_watson + ibm_cloud_sdk_core
from ibm_watson import SpeechToTextV1
from ibm_watson import TextToSpeechV1
from ibm_watson import AssistantV2
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator


from VisualRecognition import VisualRecognition
from qbo_audio import subprocess_aplay_wav




class QBOWatson(object):


   def __init__(self):
       self.config = yaml.safe_load(open("/opt/qbo/config.yml"))
       self.strAudio = ""
       self.GetAudio = False
       self.Response = "hello"
       self.GetResponse = False
       self.webcam = None
       self.controller = None
       self.is_animating = False

   def set_controller(self, controller):
       """Bind the hardware controller for mouth sync animations."""
       self.controller = controller

       self.onListening = False
       self.onListeningChanged = True
       self.finishThread = False
       self.FORMAT = pyaudio.paInt16
       self.CHANNELS = 1
       self.RATE = 16000
       self.CHUNK = 1024
       self.RECORD_SECONDS = self.config['SpeechToTextListeningTime']
       # --- Text to Speech ---
       tts_authenticator = IAMAuthenticator(self.config['TextToSpeechAPIKey'])
       self.text_to_speech = TextToSpeechV1(authenticator=tts_authenticator)
       self.text_to_speech.set_service_url(self.config['TextToSpeechURL'])
       self.text_to_speech.set_http_config({'verify': False})
       # --- Speech to Text ---
       stt_authenticator = IAMAuthenticator(self.config['SpeechToTextAPIKey'])
       self.speech_to_text = SpeechToTextV1(authenticator=stt_authenticator)
       self.speech_to_text.set_service_url(self.config['SpeechToTextURL'])
       self.speech_to_text.set_http_config({'verify': False})
       # --- Assistant ---
       assistant_authenticator = IAMAuthenticator(self.config['AssistantAPIKey'])
       self.assistant = AssistantV2(
           version='2021-06-14',
           authenticator=assistant_authenticator)
       self.assistant.set_service_url(self.config['AssistantURL'])
       self.assistant.set_http_config({'verify': False})
       self.assistantID = self.config['AssistantID']
       self.sessionID = ""
       self.vc = VisualRecognition()


       # Create thread
       self.thread = threading.Thread(target=self.threadWorker, args=())
       self.thread.daemon = False


   def setWebcam(self, webcam):
       self.webcam = webcam


   def startThread(self):
       self.finishThread = False
       self.thread.start()


   def threadWorker(self):
       while True:


           if self.onListening:


               audio = pyaudio.PyAudio()
               stream = audio.open(format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE, input=True, frames_per_buffer=self.CHUNK)


               print("recording...")
               frames = []
               for i in range(0, int(self.RATE / self.CHUNK * self.RECORD_SECONDS)):
                   data = stream.read(self.CHUNK)
                   frames.append(data)
               print("finished recording")


               # stop Recording
               stream.stop_stream()
               stream.close()
               audio.terminate()


               # Create wav file
               tmp = tempfile.NamedTemporaryFile()
               waveFile = wave.open(tmp, 'wb')
               waveFile.setnchannels(self.CHANNELS)
               waveFile.setsampwidth(audio.get_sample_size(self.FORMAT))
               waveFile.setframerate(self.RATE)
               waveFile.writeframes(b''.join(frames))
               waveFile.close()


               model = 'en-US_BroadbandModel'
               if self.config['language'] == 'spanish':
                   model = 'es-ES_BroadbandModel'


               try:
                   with open(tmp.name, 'rb') as audio_file:
                       results = self.speech_to_text.recognize(
                           audio=audio_file,
                           content_type='audio/wav',
                           model=model
                       ).get_result()
                       if len(results['results']) != 0 and len(results['results'][0]['alternatives']) != 0:
                           self.strAudio = results['results'][0]['alternatives'][0]['transcript']
                       else:
                           self.strAudio = " "
                       self.GetAudio = True
               except Exception as e:
                   print("WATSON RECOGNIZE ERROR: %s" % e)
                   self.strAudio = " "
                   self.GetAudio = True


               self.onListening = False
               self.onListeningChanged = True


               if len(self.strAudio) > 1:
                   if self.vc.askAboutMe(self.strAudio):
                       self.GetResponse = False


                       print("Started visual recognition")
                       subprocess_aplay_wav(self.config, "/opt/qbo/sounds/blip_0.wav")


                       self.vc.captureAndRecognizeImageWatson(self.webcam)


                       if self.vc.resultsAvailable:
                           print(self.vc.results)
                           self.SpeechText(self.vc.results[0])
                           self.vc.resultsAvailable = False


                       self.strAudio = " "
                       self.GetAudio = False
                       self.GetResponse = True
                       self.Response = ""


                   else:
                       self.askToAssistant(self.strAudio)
               else:
                   self.GetResponse = True
                   self.Response = ""


           if self.finishThread:
               exit(1)


           time.sleep(1)


   def stopThread(self):
       self.finishThread = True


   def askToAssistant(self, text):


       print("Understood message: %s" % text)


       try:
           session = self.assistant.create_session(
               assistant_id=self.assistantID
           ).get_result()
           self.sessionID = session['session_id']


           message = self.assistant.message(
               assistant_id=self.assistantID,
               session_id=self.sessionID,
               input={'message_type': 'text', 'text': text}
           ).get_result()


           self.Response = message['output']['generic'][0]['text']
           self.GetResponse = True


           print("Watson Assistant Response: %s" % self.Response)


           self.assistant.delete_session(
               assistant_id=self.assistantID,
               session_id=self.sessionID
           ).get_result()


           return self.Response
       except Exception as e:
           print("WATSON ASK TO ASSISTANT ERROR: %s" % e)
           self.Response = ""
           self.GetResponse = False


   def StartBack(self):
       self.onListening = True
       self.onListeningChanged = True
       return 0


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
   def SpeechText(self, text):
       voice = 'en-US_MichaelV3Voice'
       if self.config['language'] == 'spanish':
           voice = 'es-ES_EnriqueV3Voice'
       try:
           with open('/opt/qbo/sounds/watson.wav', 'wb') as audio_file:
               audio_file.write(
                   self.text_to_speech.synthesize(
                       text,
                       accept='audio/wav',
                       voice=voice
                   ).get_result().content
               )
           self.is_animating = True
           anim_thread = threading.Thread(target=self._animate_mouth_loop)
           anim_thread.daemon = True
           anim_thread.start()
           try:
               subprocess_aplay_wav(self.config, "/opt/qbo/sounds/watson.wav")
           finally:
               self.is_animating = False
               anim_thread.join(timeout=1.0)
       except Exception as e:
           print("WATSON SPEAK ERROR: %s" % e)
