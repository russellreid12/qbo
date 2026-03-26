#!/usr/bin/env python3
# -*- coding: latin-1 -*-


import datetime
import os
import subprocess
import cv2
import serial
import sys
import time
import Speak
import _thread
import yaml
from qbo_audio import aplay_wav_device
from assistants.QboWatson import QBOWatson
from assistants.QboTalk import QBOtalk
from assistants.QboTalkMycroft import QBOtalkMycroft
from controller.QboController import Controller
from VisualRecognition import VisualRecognition
from assistants.QboDialogFlowV2 import QboDialogFlowV2
from hotword_openwakeword import OpenWakeWordListener




config = yaml.safe_load(open("/opt/qbo/config.yml"))




def _cfg_bool(val, default=False):
   """YAML / web forms often use strings; bool('false') is True in Python — never use bare bool(s)."""
   if val is None:
       return default
   if isinstance(val, bool):
       return val
   if isinstance(val, str):
       s = val.strip().lower()
       if s in ("0", "false", "no", "off", ""):
           return False
       if s in ("1", "true", "yes", "on"):
           return True
       return False
   if isinstance(val, (int, float)):
       return val != 0
   return bool(val)




def _open_camera(cam_idx):
   """Try V4L2 then default backend; require a real frame (avoids 0x0 / silent failure on Pi 5)."""
   idx = int(cam_idx)
   attempts = (
       ("V4L2", lambda: cv2.VideoCapture(idx, cv2.CAP_V4L2)),
       ("default", lambda: cv2.VideoCapture(idx)),
   )
   for label, factory in attempts:
       cap = factory()
       if not cap.isOpened():
           cap.release()
           continue
       cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
       cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
       cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
       for _ in range(5):
           cap.grab()
       ok, frame = cap.read()
       if ok and frame is not None and getattr(frame, "size", 0) > 0:
           h, w = frame.shape[:2]
           print("Camera OK: index {} via {} backend ({}x{}).".format(idx, label, w, h))
           return cap, w, h
       cap.release()
       print("Camera: {} opened index {} but read failed or empty frame — trying next backend.".format(label, idx))
   return None, 0, 0




_serial_touch_probe = _cfg_bool(config.get("serialTouchProbe"), True)




if config["distro"] == "ibmwatson":
   print("Mode: IBM Watson")


   if (len(config['AssistantAPIKey']) < 2 and len(config['AssistantURL']) < 2 and
           len(config['AssistantID']) < 2 and len(config['TextToSpeechAPIKey']) < 2 and
           len(config['TextToSpeechURL']) < 2 and len(config['SpeechToTextAPIKey']) < 2 and
           len(config['SpeechToTextURL']) < 2):
       print("Warning: Missing IBM Watson configuration parameters.")
       Speak.SpeechText_2(
           "Notice. In order to use the IBM Watson service you must specify the tokens APIs. "
           "Access the web panel, fill in the information and click on Save and restart.",
           "Aviso. Para poder usar el servicio IBM Watson debe especificar los API tokens. "
           "Acceda al panel web, complete los datos y presione sobre Guardar y reiniciar.", True)
       exit(0)


   talk = QBOWatson()
   interactiveTypeGAssistant = False


   Speak.SpeechText_2(
       "Loading the IBM Watson system. Wait until I tell you that I'm ready.",
       "Cargando el sistema IBM Watson. Espera hasta que te diga que estoy listo.", True)
   time.sleep(10)
   talk.startThread()
   time.sleep(1)


else:
   gassistant = None
   if config["startWith"] == "interactive-dialogflow":
       print("Mode: Dialogflow")
       talk = QBOtalk()
       interactiveTypeGAssistant = False


   elif config["startWith"] == "interactive-dialogflow-v2":
       print("Mode: Dialogflow V2")
       if not os.path.isfile("/opt/qbo/.config/dialogflowv2.json"):
           print("Warning: Missing Dialogflow V2 JSON file.")
           Speak.SpeechText_2(
               "Notice. Set the Dialogflow V2 configuration file as indicated in the instruction manual.",
               "Aviso. Establezca el archivo de configuracion de Dialogflow V2 como indica el manual.", True)
           exit(0)
       talk = QboDialogFlowV2()
       interactiveTypeGAssistant = False


   elif config["startWith"] == "interactive-mycroft":
       print("Mode: MyCroft")
       subprocess.call(
           'sudo bash /opt/qbo/mycroft-core/start-mycroft.sh audio && '
           'sudo bash /opt/qbo/mycroft-core/start-mycroft.sh bus && '
           'sudo bash /opt/qbo/mycroft-core/start-mycroft.sh skills', shell=True)
       talk = QBOtalkMycroft()
       interactiveTypeGAssistant = False


   else:
       print("Mode: Google Assistant")
       if (not os.path.isfile("/opt/qbo/.config/google-oauthlib-tool/credentials.json") or
               len(config["gassistant_proyectid"]) < 2):
           print("Warning: Missing Google Assistant JSON file or proyectid token.")
           Speak.SpeechText_2(
               "Notice. Set the Google Assistant configuration file as indicated in the instruction manual "
               "and set the Project ID on the configuration web.",
               "Aviso. Establezca el archivo de configuracion de Google Assistant como indica el manual "
               "y establezca el Project ID en la web de configuracion.", True)
           exit(0)
       # Lazy import: google-assistant-library is not installed for Dialogflow / Watson / Mycroft.
       from assistants.QboGAssistant import GAssistant


       gassistant = GAssistant(config["gassistant_proyectid"], True)
       gassistant.start()
       interactiveTypeGAssistant = True




# ---------------------------------------------------------------------------
# Global hotword detector
# ---------------------------------------------------------------------------


threaded_detector = 0


Kpx = 1
Kpy = 1
Ksp = 40


## Head X and Y angle limits
Xmax = 725
Xmin = 290
Ymax = 550
Ymin = 420


## Initial head position
Xcoor = 511
Ycoor = int(Ymin + float(config["headYPosition"]) / 100 * (Ymax - Ymin))
print("Calculated initial head position: XCoor " + str(Xcoor) + ", YCoor " + str(Ycoor))
Facedet = 0


touch_wait = 2


no_face_tm = time.time()
face_det_tm = time.time()
last_face_det_tm = time.time()
touch_tm = 0
touch_samp = time.time()
qbo_touch = 0
touch_det = False
Listening = False
WaitingSpeech = False
listen_thd = 0
face_not_found_idx = 0
mutex_wait_touch = False
faceFound = False
HotwordListened = False


# ---------------------------------------------------------------------------
# Face tracking state machine
# States: 0=SEARCHING (nose off), 1=DETECTING (nose green), 2=LOCKED (nose blue + recording)
# ---------------------------------------------------------------------------
TRACK_SEARCHING = 0
TRACK_DETECTING = 1
TRACK_LOCKED = 2
track_state = TRACK_SEARCHING
track_centered_since = 0.0          # time face first appeared centered
track_lock_threshold_sec = 2.0      # seconds centered before locking on
recording_process = None




def start_voice_recording():
   """Start recording voice through the QBO microphone via arecord."""
   global recording_process
   if recording_process is not None:
       return  # already recording
   timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
   os.makedirs("/opt/qbo/recordings", exist_ok=True)
   filepath = "/opt/qbo/recordings/voice_{}.wav".format(timestamp)
   recording_process = subprocess.Popen(
       ["arecord", "-D", "dmicQBO_sv", "-f", "S16_LE", "-r", "16000", "-c", "1", filepath],
       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
   )
   print("Recording started: " + filepath)




def stop_voice_recording():
   """Stop any active voice recording."""
   global recording_process
   if recording_process is not None:
       recording_process.terminate()
       try:
           recording_process.wait(timeout=3)
       except subprocess.TimeoutExpired:
           recording_process.kill()
       print("Recording stopped")
       recording_process = None


# ---------------------------------------------------------------------------
# FIX: Smoothed face centre — exponential moving average prevents the servo
#      chasing every single-frame bbox jitter that causes overshoot.
# Alpha closer to 1.0 = more responsive but jitterier.
# Alpha closer to 0.0 = smoother but slower to react.
# 0.25 is a good starting point for a Pi camera at 320x240.
# ---------------------------------------------------------------------------
_smooth_alpha = float(config.get("faceTrackingSmoothAlpha", 0.25))
_smoothed_cx = 160.0   # initialise to frame centre
_smoothed_cy = 120.0


# FIX: Tracked servo speed cap — use SetServo (with speed) instead of
#      SetAngle (instant snap) so the motor can't accelerate past target.
#      Range 10–100. Lower = slower but less overshoot on fast moves.
_track_servo_speed = int(config.get("faceTrackingServoSpeed", 30))


if len(sys.argv) > 1:
   port = sys.argv[1]
else:
   port = config.get("serialPort", "/dev/serial0")


try:
   ser = serial.Serial(port, baudrate=115200, bytesize=serial.EIGHTBITS,
                       stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE,
                       rtscts=False, dsrdtr=False, timeout=0.1)
   print("Open serial port successfully: " + str(ser.name))
except Exception:
   print("Error opening serial port.")
   sys.exit()


controller = Controller(ser)
vc = VisualRecognition()


try:
   controller.SetMicrophoneGain(config['microphoneGain'])
except KeyError:
   controller.SetMicrophoneGain(100)


controller.SetServo(1, Xcoor, int(config["servoSpeed"]))
controller.SetServo(2, Ycoor, int(config["servoSpeed"]))
print("Positioning head: XCoor " + str(Xcoor) + ", YCoor " + str(Ycoor))


time.sleep(1)
controller.SetPid(1, 26, 2, 16)
time.sleep(1)
controller.SetPid(2, 26, 2, 16)
time.sleep(1)
controller.SetNoseColor(0)


webcam, frame_w, frame_h = _open_camera(config["camera"])
if webcam is None:
   print("FATAL: Camera could not capture frames. Set 'camera' in config.yml (often 2 on Pi 5).")
   print("       Close anything else using /dev/video* (FindFace, ffmpeg, libcamera apps).")
   sys.exit(1)


if frame_w <= 0 or frame_h <= 0:
   frame_w = int(webcam.get(cv2.CAP_PROP_FRAME_WIDTH)) or frame_w
   frame_h = int(webcam.get(cv2.CAP_PROP_FRAME_HEIGHT)) or frame_h


# Detection always runs on a 320x240 frame so the tracking centre is always (160, 120).
frame_cx = 160
frame_cy = 120


_face_invert_pan  = _cfg_bool(config.get("faceTrackingInvertPan"),  False)
_face_invert_tilt = _cfg_bool(config.get("faceTrackingInvertTilt"), False)
_camera_flip_h    = _cfg_bool(config.get("cameraFlipHorizontal"),   False)
_face_debug       = _cfg_bool(config.get("faceTrackingDebug"),      False)
_track_dbg_n      = 0
_track_dead       = int(config.get("faceTrackingDeadband", 20))
_pan_gain         = float(config.get("faceTrackingPanGain",  0.5))
_tilt_gain        = float(config.get("faceTrackingTiltGain", 0.5))
_stabilize_sec    = float(config.get("faceTrackingStabilizeSec", 0.35))
_face_stabilize_until = 0.0


print("Camera resolution: {}x{}, detect center: ({},{})".format(frame_w, frame_h, frame_cx, frame_cy))
print("faceTrackingInvertPan={} cameraFlipHorizontal={} deadband={} panGain={} tiltGain={} "
     "stabilizeSec={} smoothAlpha={} trackServoSpeed={} debug={}".format(
     _face_invert_pan, _camera_flip_h, _track_dead, _pan_gain, _tilt_gain,
     _stabilize_sec, _smooth_alpha, _track_servo_speed, _face_debug))
print("serialTouchProbe={} (set false in config.yml to silence GET_TOUCH if UART is down)".format(
     _serial_touch_probe))


# ---------------------------------------------------------------------------
# Face recognition greeting state
# ---------------------------------------------------------------------------
_last_greeted_name = None          # avoid greeting the same person repeatedly
_greet_cooldown_sec = 30.0         # seconds before greeting the same person again
_last_greeted_tm = 0.0
_face_recog_pending = False        # flag set when a new face is first acquired
_webcam_busy = False                # guard against concurrent webcam access




# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def pick_largest_face_rect(faces):
   """If Haar returns several boxes, track the largest (area), not the last."""
   if faces is None or len(faces) == 0:
       return None
   best = faces[0]
   ba = int(best[2]) * int(best[3])
   for i in range(1, len(faces)):
       f = faces[i]
       a = int(f[2]) * int(f[3])
       if a > ba:
           best, ba = f, a
   return best




def read_webcam_detection_frame(cap):
   """Grab+demux to reduce latency; resize to 320x240; optional horizontal flip."""
   for _ in range(2):
       cap.grab()
   ret, frame = cap.read()
   if not ret or frame is None:
       return None
   if _camera_flip_h:
       frame = cv2.flip(frame, 1)
   h, w = frame.shape[:2]
   if w != 320 or h != 240:
       frame = cv2.resize(frame, (320, 240))
   return frame




def greet_face_async():
   """
   Run in a background thread when a new face is first acquired.
   Nose goes green immediately, then blue while speaking the greeting,
   then back to green. Unknown faces get green nose but no speech.
   """
   global _last_greeted_name, _last_greeted_tm, _face_recog_pending, _webcam_busy


   _face_recog_pending = False


   # If the main loop is actively using the webcam, skip recognition this
   # cycle to avoid a race on cv2.VideoCapture (causes empty frames).
   if _webcam_busy:
       if config["distro"] != "ibmwatson" and not Listening:
           controller.SetNoseColor(4)
       return


   # Small delay so the main loop has time to set Facedet=1 and green nose
   time.sleep(0.5)


   _webcam_busy = True
   try:
       vc.captureImage(webcam)
       vc.recognizeFaces()
   finally:
       _webcam_busy = False


   if not vc.faceResultsAvailable or not vc.faceResults:
       # Still make sure nose is green even if recognition found nothing
       if config["distro"] != "ibmwatson" and not Listening:
           controller.SetNoseColor(4)
       return


   # Only act on the first (largest / most prominent) face in the frame
   name = vc.faceResults[0]


   if name == "Unknown":
       # Unknown face — green nose, no speech
       if config["distro"] != "ibmwatson" and not Listening:
           controller.SetNoseColor(4)
       return


   now = time.time()
   # Only greet if it's a different person OR enough time has passed
   if name == _last_greeted_name and (now - _last_greeted_tm) < _greet_cooldown_sec:
       if config["distro"] != "ibmwatson" and not Listening:
           controller.SetNoseColor(4)
       return


   _last_greeted_name = name
   _last_greeted_tm = now


   lang = config.get("language", "english")
   if lang == "spanish":
       greeting = "Hola, {}.".format(name)
   else:
       greeting = "Hello, {}.".format(name)


   print("Face recognised: {}".format(name))


   # Nose blue while speaking, then back to green when done
   if config["distro"] != "ibmwatson":
       controller.SetNoseColor(1)


   # QBOtalk.SpeechText() takes exactly one argument — the string to speak
   try:
       talk.SpeechText(greeting)
   except Exception as e:
       print("greet_face_async speech error: {}".format(e))


   if config["distro"] != "ibmwatson" and not Listening:
       controller.SetNoseColor(4)




if config["distro"] == "ibmwatson":
   talk.setWebcam(webcam)


frontalface = cv2.CascadeClassifier("/opt/qbo/haarcascades/haarcascade_frontalface_alt2.xml")
profileface  = cv2.CascadeClassifier("/opt/qbo/haarcascades/haarcascade_profileface.xml")


face   = [0, 0, 0, 0]
Cface  = [0, 0]
lastface = 0


time.sleep(1)




def ServoHome():
   global Xcoor, Ycoor, touch_tm, _face_stabilize_until, _smoothed_cx, _smoothed_cy


   Xcoor = 511
   Ycoor = int(Ymin + float(config["headYPosition"]) / 100 * (Ymax - Ymin))
   controller.SetServo(1, Xcoor, int(config["servoSpeed"]))
   time.sleep(0.1)
   controller.SetServo(2, Ycoor, int(config["servoSpeed"]))
   touch_tm = time.time()
   _face_stabilize_until = time.time() + _stabilize_sec


   # Reset smoother so stale position doesn't yank the head on next detection
   _smoothed_cx = float(frame_cx)
   _smoothed_cy = float(frame_cy)


   print("Repositioning head: XCoor " + str(Xcoor) + ", YCoor " + str(Ycoor))




def WaitForSpeech():
   global WaitingSpeech, Listening, listen_thd


   if config["distro"] == "ibmwatson":
       if talk.onListeningChanged:
           talk.onListeningChanged = False
           if talk.onListening:
               controller.SetNoseColor(1)
           else:
               controller.SetNoseColor(0)


   # FIX: use 'and' not '&' for boolean logic
   if WaitingSpeech == False and interactiveTypeGAssistant == False:
       WaitingSpeech = True


       if Listening == False:
           WaitingSpeech = False
           return


       elif config["distro"] != "ibmwatson" and vc.askAboutMe(talk.strAudio):
           talk.GetResponse = False


           print("Started visual recognition")
           subprocess.call(
               ["aplay", "-D", aplay_wav_device(config), "/opt/qbo/sounds/blip_0.wav"]
           )


           # Capture + run both object detection AND face recognition together
           vc.captureImage(webcam)
           vc.recognizeImage()
           vc.recognizeFaces()


           # Build a response that only mentions people, not objects
           spoken = None
           if vc.faceResultsAvailable and vc.faceResults:
               known = [n for n in vc.faceResults if n != "Unknown"]
               if known:
                   lang = config.get("language", "english")
                   if lang == "spanish":
                       spoken = "Veo a {}.".format(", ".join(known))
                   else:
                       spoken = "I see {}.".format(", ".join(known))


           # Fall back to object label only if no person was identified
           if spoken is None and vc.resultsAvailable and vc.results:
               spoken = vc.results[0]


           if spoken:
               print("Visual recognition response: {}".format(spoken))
               talk.SpeechText(spoken)
               vc.resultsAvailable = False
               vc.faceResultsAvailable = False


           talk.strAudio = " "
           talk.GetAudio = False
           talk.GetResponse = False


       elif talk.GetResponse == True:
           if config["distro"] != "ibmwatson":
               listen_thd(wait_for_stop=True)


           if len(talk.Response) > 0:
               talk.SpeechText(talk.Response)


           if config["distro"] != "ibmwatson":
               controller.SetNoseColor(0)


           talk.GetResponse = False
           Listening = False
           StartHotwordListener()


       WaitingSpeech = False




def WaitTouchMove():
   global Xcoor, Ycoor, touch_tm, mutex_wait_touch, faceFound


   if mutex_wait_touch:
       return


   mutex_wait_touch = True
   time.sleep(3)


   if faceFound:
       return


   controller.SetServo(1, Xcoor, int(config["servoSpeed"]))
   time.sleep(0.1)
   controller.SetServo(2, Ycoor, int(config["servoSpeed"]))
   time.sleep(1)
   touch_tm = time.time()
   mutex_wait_touch = False




hotword_listener = None




def StartHotwordListener():
   global hotword_listener
   if interactiveTypeGAssistant:
       return
   if hotword_listener is None:
       hotword_listener = OpenWakeWordListener(HotwordListenedEvent)
       hotword_listener.start()




def StopHotwordListener():
   global hotword_listener
   if interactiveTypeGAssistant:
       return
   if hotword_listener is not None:
       hotword_listener.stop()
       hotword_listener = None




def DialogflowV2SeeFace():
   talk.record_wav()
   talk.detect_intent_stream()




def HotwordListenedEvent():
   global HotwordListened
   HotwordListened = True




StartHotwordListener()


print(" Face tracking running.")
print(" QBO nose bright green when see your face")


Speak.SpeechText_2("I am ready.", "Estoy preparado.")


touch_tm = time.time()
fr_time = 0




# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


while True:
   fr_time = time.time()


   faceFound = False
   _thread.start_new_thread(WaitForSpeech, ())


   if HotwordListened:
       if Listening == False:
           if config["distro"] != "ibmwatson":
               controller.SetNoseColor(1)


           StopHotwordListener()


           if interactiveTypeGAssistant == True:
               gassistant.start_conversation_from_face()
           else:
               listen_thd = talk.StartBack()
               Listening = True


       HotwordListened = False


   # --- Frontal face detection ---
   if not faceFound and not _webcam_busy:
       if lastface == 0 or lastface == 1:
           aframe = read_webcam_detection_frame(webcam)
           if aframe is not None:
               fface = frontalface.detectMultiScale(
                   aframe, 1.3, 4,
                   (cv2.CASCADE_DO_CANNY_PRUNING | cv2.CASCADE_FIND_BIGGEST_OBJECT |
                    cv2.CASCADE_DO_ROUGH_SEARCH),
                   (60, 60))
               if len(fface) > 0:
                   face_not_found_idx = 0
                   lastface = 1
                   face = pick_largest_face_rect(fface)
                   faceFound = True


   # --- Profile face detection ---
   if not faceFound and not _webcam_busy:
       if lastface == 0 or lastface == 2:
           aframe = read_webcam_detection_frame(webcam)
           if aframe is not None:
               pfacer = profileface.detectMultiScale(
                   aframe, 1.3, 4,
                   (cv2.CASCADE_DO_CANNY_PRUNING | cv2.CASCADE_FIND_BIGGEST_OBJECT |
                    cv2.CASCADE_DO_ROUGH_SEARCH),
                   (80, 80))
               if len(pfacer) > 0:
                   face_not_found_idx = 0
                   lastface = 2
                   face = pick_largest_face_rect(pfacer)
                   faceFound = True


   # --- No face found ---
   # Don't count missed frames while webcam is busy with background recognition
   if not faceFound and not _webcam_busy:
       face_not_found_idx += 1


       if face_not_found_idx > 20:
           face_not_found_idx = 0
           lastface = 0
           face = [0, 0, 0, 0]


           # ---- State machine: transition to SEARCHING ----
           if track_state != TRACK_SEARCHING:
               print("Face lost -> SEARCHING")
               stop_voice_recording()
               track_state = TRACK_SEARCHING
               track_centered_since = 0.0


           if config["distro"] != "ibmwatson":
               controller.SetNoseColor(0)  # Nose off


           if Facedet != 0:
               Facedet = 0
               no_face_tm = time.time()
               print("No face, 5 times!")


           elif time.time() - no_face_tm > 10:
               ServoHome()
               Cface[0] = [0, 0]
               no_face_tm = time.time()


   # --- Face found ---
   else:
       last_face_det_tm = time.time()
       x, y, w, h = face


       # Raw face centre from Haar bbox
       raw_cx = float(x) + float(w) * 0.5
       raw_cy = float(y) + float(h) * 0.5


       # Exponential moving average smoothing — kills jitter-driven overshoot.
       if Facedet == 0:
           _smoothed_cx = raw_cx
           _smoothed_cy = raw_cy
       else:
           _smoothed_cx = _smooth_alpha * raw_cx + (1.0 - _smooth_alpha) * _smoothed_cx
           _smoothed_cy = _smooth_alpha * raw_cy + (1.0 - _smooth_alpha) * _smoothed_cy


       Cface = [_smoothed_cx, _smoothed_cy]


       # ---- Compute face offsets for state machine & servo tracking ----
       faceOffset_X = float(frame_cx) - Cface[0]
       if _face_invert_pan:
           faceOffset_X = -faceOffset_X
       faceOffset_Y = Cface[1] - float(frame_cy)
       if _face_invert_tilt:
           faceOffset_Y = -faceOffset_Y
       face_is_centered = (abs(faceOffset_X) <= _track_dead and abs(faceOffset_Y) <= _track_dead)


       # ---- State machine: SEARCHING -> DETECTING (green) ----
       if Facedet == 0:
           Facedet = 1
           face_det_tm = time.time()
           _face_stabilize_until = time.time() + _stabilize_sec
           track_state = TRACK_DETECTING
           track_centered_since = 0.0
           print("Face found -> DETECTING (green)")


           if config["distro"] != "ibmwatson" and not Listening:
               controller.SetNoseColor(4)  # Green


           # Trigger background face recognition + greeting
           _face_recog_pending = True
           _thread.start_new_thread(greet_face_async, ())


       # ---- State machine: DETECTING -> LOCKED ----
       elif track_state == TRACK_DETECTING:
           if config["distro"] != "ibmwatson" and not Listening:
               controller.SetNoseColor(4)  # Stay green while detecting


           if face_is_centered:
               if track_centered_since == 0.0:
                   track_centered_since = time.time()
               elif time.time() - track_centered_since >= track_lock_threshold_sec:
                   # Lock on!
                   track_state = TRACK_LOCKED
                   print("Face centered -> LOCKED (blue + recording)")
                   if config["distro"] != "ibmwatson":
                       controller.SetNoseColor(1)  # Blue
                   start_voice_recording()
           else:
               track_centered_since = 0.0  # reset if face moves off center


       # ---- State machine: LOCKED — stay blue, keep recording ----
       elif track_state == TRACK_LOCKED:
           if config["distro"] != "ibmwatson":
               controller.SetNoseColor(1)  # Blue while locked
           # If face drifts off-center significantly, drop back to DETECTING
           if not face_is_centered:
               track_state = TRACK_DETECTING
               track_centered_since = 0.0
               stop_voice_recording()
               print("Face moved -> DETECTING (green)")
               if config["distro"] != "ibmwatson":
                   controller.SetNoseColor(4)  # Green


       # ---- Hotword/assistant: preserved from original code ----
       if (Listening == False and WaitingSpeech == False and
             (time.time() - face_det_tm > 2)):
           face_det_tm = time.time()


           if Listening == False:
               StopHotwordListener()


               if interactiveTypeGAssistant == True:
                   gassistant.start_conversation_from_face()
               elif interactiveTypeGAssistant == False and config["startWith"] == "interactive-dialogflow-v2":
                   DialogflowV2SeeFace()
               else:
                   listen_thd = talk.StartBack()
                   Listening = True


       # --- Pan / tilt servo tracking ---
       if touch_det == False and time.time() >= _face_stabilize_until:


           if abs(faceOffset_X) > _track_dead:
               Xcoor = max(Xmin, min(Xmax, Xcoor + int(faceOffset_X * _pan_gain)))
               controller.SetServo(1, Xcoor, _track_servo_speed)
               if _face_debug:
                   _track_dbg_n += 1
                   if _track_dbg_n % 25 == 0:
                       print("faceTrack dbg: raw_x={:.1f} smooth_x={:.1f} offX={:.1f} "
                             "Xcoor={} (invertPan={})".format(
                             raw_cx, _smoothed_cx, faceOffset_X, Xcoor, _face_invert_pan))
               time.sleep(0.05)


           if abs(faceOffset_Y) > _track_dead:
               Ycoor = max(Ymin, min(Ymax, Ycoor + int(faceOffset_Y * _tilt_gain)))
               controller.SetServo(2, Ycoor, _track_servo_speed)
               time.sleep(0.05)


   # --- Touch sensor ---
   if _serial_touch_probe and (time.time() - touch_samp > 0.5):
       touch_samp = time.time()
       last_face_det_tm = time.time()
       qbo_touch = controller.GetHeadCmd("GET_TOUCH", 0)
       time.sleep(0.002)


       if touch_tm == 0 and qbo_touch:
           if qbo_touch == [1]:
               controller.SetServo(1, Xmax - 25, int(config["servoSpeed"]))
               time.sleep(0.002)
               controller.SetServo(2, Ymin - 5, int(config["servoSpeed"]))
               _thread.start_new_thread(WaitTouchMove, ())
               time.sleep(1)


           elif qbo_touch == [2]:
               time.sleep(0.002)
               controller.SetServo(2, Ymin - 5, int(config["servoSpeed"]))
               _thread.start_new_thread(WaitTouchMove, ())
               time.sleep(1)


           elif qbo_touch == [3]:
               controller.SetServo(1, Xmin + 25, int(config["servoSpeed"]))
               time.sleep(0.002)
               controller.SetServo(2, Ymin - 5, int(config["servoSpeed"]))
               _thread.start_new_thread(WaitTouchMove, ())
               time.sleep(1)


   if touch_tm != 0 and time.time() - touch_tm > touch_wait:
       print("touch ready")
       touch_tm = 0




stop_voice_recording()
StopHotwordListener()







