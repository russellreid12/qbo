#!/usr/bin/env python3
# -*- coding: latin-1 -*-

# Before onnxruntime (hotword): reduce GPU discovery warning on Pi.
import os
if not os.environ.get("QBO_VERBOSE_LIBS"):
    # 3=ERROR still shows some ORT warnings; 4=FATAL suppresses GPU discovery noise on Pi.
    os.environ.setdefault("ORT_LOG_SEVERITY_LEVEL", "4")

import datetime
import subprocess
import cv2
import serial
import sys
import time
import Speak
import _thread
import yaml
from qbo_audio import subprocess_aplay_wav
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


   # Lazy import: ibm-watson stack only needed when distro == ibmwatson.
   from assistants.QboWatson import QBOWatson

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


# ---------------------------------------------------------------------------
# PID Controller — replaces proportional-only tracking for accuracy
# ---------------------------------------------------------------------------
class PIDController:
    """Simple PID with anti-windup for servo face tracking."""
    def __init__(self, kp, ki, kd, integral_max=30.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral_max = integral_max
        self._integral = 0.0
        self._prev_error = 0.0
        # Diagnostic: last computed P, I, D terms (readable for debug output)
        self.last_p = 0.0
        self.last_i = 0.0
        self.last_d = 0.0
        self.last_output = 0.0

    def reset(self):
        self._integral = 0.0
        self._prev_error = 0.0
        self.last_p = 0.0
        self.last_i = 0.0
        self.last_d = 0.0
        self.last_output = 0.0

    def decay_integral(self, factor=0.7):
        """Bleed off accumulated integral when error is within deadband.
        Prevents stale integral from causing drift after the face is centered."""
        self._integral *= factor
        self._prev_error = 0.0

    def update(self, error, dt):
        # Clamp dt to prevent derivative spikes from near-zero or very stale values
        dt = max(0.016, min(0.5, dt))
        # Proportional
        p = self.kp * error
        # Integral with anti-windup clamp
        self._integral += error * dt
        self._integral = max(-self.integral_max, min(self.integral_max, self._integral))
        i = self.ki * self._integral
        # Derivative (rate of error change)
        d = self.kd * (error - self._prev_error) / dt
        self._prev_error = error
        # Store for debug inspection
        self.last_p = p
        self.last_i = i
        self.last_d = d
        self.last_output = p + i + d
        return p + i + d


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
   """Start recording via arecord. Use microphoneAlsaDevice in config.yml (e.g. pulse for AirPods HFP)."""
   global recording_process
   if recording_process is not None:
       return  # already recording
   dev = str(config.get("microphoneAlsaDevice") or "dmicQBO_sv").strip() or "dmicQBO_sv"
   try:
       rate = int(config.get("microphoneAlsaSampleRate", config.get("microphoneSampleRate", 16000)))
   except (TypeError, ValueError):
       rate = 16000
   timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
   os.makedirs("/opt/qbo/recordings", exist_ok=True)
   filepath = "/opt/qbo/recordings/voice_{}.wav".format(timestamp)
   recording_process = subprocess.Popen(
       ["arecord", "-D", dev, "-f", "S16_LE", "-r", str(rate), "-c", "1", filepath],
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
# 0.4 balances responsiveness with PID-dampened stability.
# ---------------------------------------------------------------------------
_smooth_alpha = float(config.get("faceTrackingSmoothAlpha", 0.85))
_smoothed_cx = 160.0   # initialise to frame centre
_smoothed_cy = 120.0


# FIX: Tracked servo speed cap — use SetServo (with speed) instead of
#      SetAngle (instant snap) so the motor can't accelerate past target.
#      Range 10–100. Lower = slower but less overshoot on fast moves.
_track_servo_speed = int(config.get("faceTrackingServoSpeed", 100))


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
   controller.SetEnableSpeaker(True)
except Exception as e:
   print("SetEnableSpeaker: %s" % e)


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


def _touch_reaction_lights_on():
   """Nose + servo ring LEDs on capacitive touch (GET_TOUCH 1/2/3)."""
   if not _cfg_bool(config.get("touchReactionLights"), True):
       return
   if config["distro"] != "ibmwatson":
       try:
           controller.SetNoseColor(int(config.get("touchNoseColor", 2)))
       except (TypeError, ValueError):
           controller.SetNoseColor(2)
   if _cfg_bool(config.get("touchReactionServoLeds"), True):
       try:
           controller.GetHeadCmd("SET_SERVO_LED", [1, 1])
           controller.GetHeadCmd("SET_SERVO_LED", [2, 1])
       except Exception:
           pass


def _touch_reaction_lights_off():
   if not _cfg_bool(config.get("touchReactionLights"), True):
       return
   if _cfg_bool(config.get("touchReactionServoLeds"), True):
       try:
           controller.GetHeadCmd("SET_SERVO_LED", [1, 0])
           controller.GetHeadCmd("SET_SERVO_LED", [2, 0])
       except Exception:
           pass
   if config["distro"] != "ibmwatson":
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


_face_invert_pan  = True  # FORCED TRUE: proven by coordinate analysis
_face_invert_tilt = _cfg_bool(config.get("faceTrackingInvertTilt"), False)
_camera_flip_h    = _cfg_bool(config.get("cameraFlipHorizontal"),   False)
_face_debug       = _cfg_bool(config.get("faceTrackingDebug"),      False)
_face_debug_interval = int(config.get("faceTrackingDebugInterval", 10))  # print every N frames
_track_dbg_n      = 0
_track_dead       = int(config.get("faceTrackingDeadband", 8))
_stabilize_sec    = float(config.get("faceTrackingStabilizeSec", 0.35))
_face_stabilize_until = 0.0

# ---------------------------------------------------------------------------
# Debug / telemetry counters
# ---------------------------------------------------------------------------
_dbg_fps_t0        = time.time()     # FPS window start
_dbg_fps_frames    = 0               # frames in current window
_dbg_fps_value     = 0.0             # computed FPS
_dbg_detect_count  = 0               # total successful detections
_dbg_miss_count    = 0               # total missed frames (no face)
_dbg_last_conf     = 0.0             # last DNN confidence (0 for Haar)
_dbg_last_det_ms   = 0.0             # last detection time in ms
_dbg_last_face_w   = 0               # last face bbox width
_dbg_last_face_h   = 0               # last face bbox height
_dbg_state_names   = {TRACK_SEARCHING: "SEARCHING", TRACK_DETECTING: "DETECTING", TRACK_LOCKED: "LOCKED"}

# PID gains — tuned for ~5 FPS tracking loop on Pi 5
# (old defaults 0.35/0.05/0.15/60 caused runaway at low FPS)
_pid_kp = float(config.get("faceTrackingKp", 0.35))
_pid_ki = float(config.get("faceTrackingKi", 0.02))
_pid_kd = float(config.get("faceTrackingKd", 0.08))
_pid_integral_max = float(config.get("faceTrackingIntegralMax", 30.0))

# Max servo units the PID can move per frame — hard cap prevents overshoot
# regardless of PID tuning.  At ~5 FPS, 40 units/frame ≈ 200 units/sec.
_track_max_step = int(config.get("faceTrackingMaxStep", 40))

pid_pan  = PIDController(_pid_kp, _pid_ki, _pid_kd, _pid_integral_max)
pid_tilt = PIDController(_pid_kp, _pid_ki, _pid_kd, _pid_integral_max)
_last_track_time = time.time()

# ---------------------------------------------------------------------------
# DNN face detector (much more accurate than Haar cascades)
# ---------------------------------------------------------------------------
_face_detector_type = config.get("faceDetector", "dnn")  # "dnn" or "haar"
_dnn_confidence_min = float(config.get("faceDetectorConfidence", 0.5))
_dnn_net = None

if _face_detector_type == "dnn":
    _dnn_proto = "/opt/qbo/models/deploy.prototxt"
    _dnn_model = "/opt/qbo/models/res10_300x300_ssd_iter_140000.caffemodel"
    if os.path.isfile(_dnn_proto) and os.path.isfile(_dnn_model):
        try:
            _dnn_net = cv2.dnn.readNetFromCaffe(_dnn_proto, _dnn_model)
            print("DNN face detector loaded successfully.")
        except Exception as e:
            print("DNN face detector failed to load: {} — falling back to Haar.".format(e))
            _dnn_net = None
    else:
        print("DNN model files not found at /opt/qbo/models/ — falling back to Haar.")
        print("Run: bash /opt/qbo/scripts/download_face_model.sh")


def detect_faces_dnn(frame):
    """Detect faces using OpenCV DNN SSD. Returns list of (x,y,w,h) tuples.
    Also stores best confidence in _dbg_last_conf for debug output."""
    global _dbg_last_conf
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104.0, 177.0, 123.0))
    _dnn_net.setInput(blob)
    detections = _dnn_net.forward()
    faces = []
    best_conf = 0.0
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence < _dnn_confidence_min:
            continue
        box = detections[0, 0, i, 3:7] * [w, h, w, h]
        x1, y1, x2, y2 = box.astype(int)
        x1 = max(0, x1)
        y1 = max(0, y1)
        fw = x2 - x1
        fh = y2 - y1
        if fw > 20 and fh > 20:
            faces.append((x1, y1, fw, fh))
            if confidence > best_conf:
                best_conf = float(confidence)
    _dbg_last_conf = best_conf
    return faces


def detect_faces_frame(frame):
    """Unified face detection — uses DNN if available, otherwise Haar cascades."""
    if _dnn_net is not None:
        return detect_faces_dnn(frame)
    # Haar cascade fallback
    fface = frontalface.detectMultiScale(
        frame, 1.3, 4,
        (cv2.CASCADE_DO_CANNY_PRUNING | cv2.CASCADE_FIND_BIGGEST_OBJECT |
         cv2.CASCADE_DO_ROUGH_SEARCH),
        (60, 60))
    if len(fface) > 0:
        return [tuple(f) for f in fface]
    pfacer = profileface.detectMultiScale(
        frame, 1.3, 4,
        (cv2.CASCADE_DO_CANNY_PRUNING | cv2.CASCADE_FIND_BIGGEST_OBJECT |
         cv2.CASCADE_DO_ROUGH_SEARCH),
        (80, 80))
    if len(pfacer) > 0:
        return [tuple(f) for f in pfacer]
    return []


print("Camera resolution: {}x{}, detect center: ({},{})".format(frame_w, frame_h, frame_cx, frame_cy))
print("faceDetector={} dnnLoaded={} confidence={}".format(
     _face_detector_type, _dnn_net is not None, _dnn_confidence_min))
print("PID: Kp={} Ki={} Kd={} integralMax={} deadband={} maxStep={}".format(
     _pid_kp, _pid_ki, _pid_kd, _pid_integral_max, _track_dead, _track_max_step))
print("faceTrackingInvertPan={} cameraFlipHorizontal={} "
     "stabilizeSec={} smoothAlpha={} trackServoSpeed={} debug={} debugInterval={}".format(
     _face_invert_pan, _camera_flip_h,
     _stabilize_sec, _smooth_alpha, _track_servo_speed, _face_debug, _face_debug_interval))
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
   global Xcoor, Ycoor, touch_tm, _face_stabilize_until, _smoothed_cx, _smoothed_cy, _last_track_time


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


   # Reset PID controllers so stale integral doesn't cause overshoot
   pid_pan.reset()
   pid_tilt.reset()
   _last_track_time = time.time()


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
           subprocess_aplay_wav(config, "/opt/qbo/sounds/blip_0.wav")


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
_dbg_loop_iter = 0   # main-loop iteration counter for debug summary




# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


while True:
   fr_time = time.time()
   _last_track_time = fr_time  # keep fresh every loop to prevent stale dt spikes

   # ---- Debug: FPS and loop counter ----
   _dbg_loop_iter += 1
   _dbg_fps_frames += 1
   _fps_elapsed = fr_time - _dbg_fps_t0
   if _fps_elapsed >= 2.0:
       _dbg_fps_value = _dbg_fps_frames / _fps_elapsed
       _dbg_fps_frames = 0
       _dbg_fps_t0 = fr_time
       if _face_debug:
           print("FPS: {:.1f} | loop#{} | detections={} misses={} | state={}".format(
               _dbg_fps_value, _dbg_loop_iter, _dbg_detect_count, _dbg_miss_count,
               _dbg_state_names.get(track_state, "??")))


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


   # --- Face detection (DNN or Haar) ---
   if not faceFound and not _webcam_busy:
       _det_t0 = time.time()
       aframe = read_webcam_detection_frame(webcam)
       if aframe is not None:
           detected = detect_faces_frame(aframe)
           _dbg_last_det_ms = (time.time() - _det_t0) * 1000.0
           if len(detected) > 0:
               face_not_found_idx = 0
               lastface = 1
               face = pick_largest_face_rect(detected)
               faceFound = True
               _dbg_detect_count += 1
               _dbg_last_face_w = int(face[2])
               _dbg_last_face_h = int(face[3])
               if _face_debug and _track_dbg_n % _face_debug_interval == 0:
                   print("DET: {} faces | best={}x{} at ({},{}) | conf={:.2f} | {:.1f}ms | method={}".format(
                       len(detected), _dbg_last_face_w, _dbg_last_face_h,
                       int(face[0]), int(face[1]), _dbg_last_conf, _dbg_last_det_ms,
                       "DNN" if _dnn_net is not None else "Haar"))


   # --- No face found ---
   # Don't count missed frames while webcam is busy with background recognition
   if not faceFound and not _webcam_busy:
       face_not_found_idx += 1
       _dbg_miss_count += 1


       if face_not_found_idx > 5:
           face_not_found_idx = 0
           lastface = 0
           face = [0, 0, 0, 0]


           # ---- State machine: transition to SEARCHING ----
           if track_state != TRACK_SEARCHING:
               print("Face lost -> SEARCHING")
               stop_voice_recording()
               track_state = TRACK_SEARCHING
               track_centered_since = 0.0
               pid_pan.reset()
               pid_tilt.reset()
               _last_track_time = time.time()


           if config["distro"] != "ibmwatson":
               controller.SetNoseColor(0)  # Nose off


           if Facedet != 0:
               Facedet = 0
               no_face_tm = time.time()
               print("No face, 5 times!")


           elif time.time() - no_face_tm > 3:
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
           _last_track_time = time.time()
           pid_pan.reset()
           pid_tilt.reset()
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


       # --- Pan / tilt servo tracking (PID) ---
       if touch_det == False and time.time() >= _face_stabilize_until:
           now = time.time()
           dt = now - _last_track_time
           _last_track_time = now


           if abs(faceOffset_X) > _track_dead:
               pan_out = pid_pan.update(faceOffset_X, dt)
               pan_step = max(-_track_max_step, min(_track_max_step, int(pan_out)))
               Xcoor = max(Xmin, min(Xmax, Xcoor + pan_step))
               controller.SetServo(1, Xcoor, _track_servo_speed)
           else:
               pid_pan.decay_integral()  # bleed off stale integral in deadband


           if abs(faceOffset_Y) > _track_dead:
               tilt_out = pid_tilt.update(faceOffset_Y, dt)
               tilt_step = max(-_track_max_step, min(_track_max_step, int(tilt_out)))
               Ycoor = max(Ymin, min(Ymax, Ycoor + tilt_step))
               controller.SetServo(2, Ycoor, _track_servo_speed)
           else:
               pid_tilt.decay_integral()  # bleed off stale integral in deadband
           if _face_debug:
                _track_dbg_n += 1
                if _track_dbg_n % _face_debug_interval == 0:
                    # Smoothing delta (how much EMA is shifting the raw reading)
                    _sm_dx = _smoothed_cx - raw_cx
                    _sm_dy = _smoothed_cy - raw_cy
                    print("TRACK #{}: raw=({:.0f},{:.0f}) smooth=({:.0f},{:.0f}) Δsmooth=({:.1f},{:.1f}) "
                          "offset=({:.1f},{:.1f}) centered={} state={}".format(
                          _track_dbg_n, raw_cx, raw_cy, _smoothed_cx, _smoothed_cy,
                          _sm_dx, _sm_dy, faceOffset_X, faceOffset_Y,
                          face_is_centered, _dbg_state_names.get(track_state, "??")))
                    print("  PAN  pid: P={:.2f} I={:.2f} D={:.2f} out={:.2f} | integral={:.2f} | servo X={}".format(
                          pid_pan.last_p, pid_pan.last_i, pid_pan.last_d, pid_pan.last_output,
                          pid_pan._integral, Xcoor))
                    print("  TILT pid: P={:.2f} I={:.2f} D={:.2f} out={:.2f} | integral={:.2f} | servo Y={}".format(
                          pid_tilt.last_p, pid_tilt.last_i, pid_tilt.last_d, pid_tilt.last_output,
                          pid_tilt._integral, Ycoor))
                    print("  face={}x{} conf={:.2f} det={:.1f}ms dt={:.3f}s deadband={} FPS={:.1f}".format(
                          _dbg_last_face_w, _dbg_last_face_h, _dbg_last_conf,
                          _dbg_last_det_ms, dt, _track_dead, _dbg_fps_value))


   # --- Touch sensor ---
   if _serial_touch_probe and (time.time() - touch_samp > 0.5):
       touch_samp = time.time()
       last_face_det_tm = time.time()
       qbo_touch = controller.GetHeadCmd("GET_TOUCH", 0)
       time.sleep(0.002)


       if touch_tm == 0 and qbo_touch:
           _touch_reaction_lights_on()
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
       _touch_reaction_lights_off()


   # Throttle main loop to ~30 Hz max
   time.sleep(0.033)




stop_voice_recording()
StopHotwordListener()







