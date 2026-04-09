#!/usr/bin/env python3
# -*- coding: latin-1 -*-

# Before onnxruntime (hotword): reduce GPU discovery warning on Pi.
import os
if not os.environ.get("QBO_VERBOSE_LIBS"):
    # 3=ERROR still shows some ORT warnings; 4=FATAL suppresses GPU discovery noise on Pi.
    os.environ.setdefault("ORT_LOG_SEVERITY_LEVEL", "4")

import datetime
import errno
import subprocess
import cv2
import serial
import sys
import time
import Speak
import _thread
import threading
import yaml
from qbo_audio import subprocess_aplay_wav, wait_for_audio_hardware_visible
from assistants.QboTalk import QBOtalk
from assistants.QboTalkMycroft import QBOtalkMycroft
from controller.QboController import Controller
from VisualRecognition import VisualRecognition
from assistants.QboDialogFlowV2 import QboDialogFlowV2
from hotword_openwakeword import OpenWakeWordListener
import video_recorder




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




# ---------------------------------------------------------------------------
# Hardware Initialization: Serial port and Mouth Controller
# (Moved to the beginning so the mouth is accessible for early startup speech)
# ---------------------------------------------------------------------------
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
import queue as _queue_mod
_serial_lock = threading.Lock()   # Prevent concurrent serial access from tracking loop and background threads

# ---------------------------------------------------------------------------
# Serial Write Queue — Fix from qbo_priority_queue.md
# Two queues: Priority for servo tracking, Normal for UI/cosmetic updates.
# ---------------------------------------------------------------------------
_serial_queue_priority = _queue_mod.Queue()  # servo tracking — time sensitive
_serial_queue = _queue_mod.Queue()           # nose color, LEDs, etc — low priority

def _serial_worker():
    while True:
        # Always drain priority queue first
        try:
            fn = _serial_queue_priority.get_nowait()
            try:
                with _serial_lock:
                    fn()
            finally:
                _serial_queue_priority.task_done()
            continue  # loop back and check priority again before normal queue
        except _queue_mod.Empty:
            pass

        # Then normal queue — but priority is checked again on next iteration
        try:
            fn = _serial_queue.get(timeout=0.05)
            try:
                with _serial_lock:
                    fn()
            finally:
                _serial_queue.task_done()
        except _queue_mod.Empty:
            pass

threading.Thread(target=_serial_worker, daemon=True, name="serial_worker").start()

def serial_send(fn):
    """Queue a low-priority serial command — skips cosmetic updates during active recording."""
    if recording_process is not None and time.time() < _recording_grace_until + 1.0:
        return
    _serial_queue.put(fn)

def serial_send_tracking(fn):
    """Queue a high-priority servo tracking command — drops stale commands."""
    while not _serial_queue_priority.empty():
        try:
            _serial_queue_priority.get_nowait()
            _serial_queue_priority.task_done()
        except _queue_mod.Empty:
            break
    _serial_queue_priority.put(fn)

Speak.set_controller(controller)
# (Note: talk.set_controller will be called after assistants are initialized below)


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
   # talk.set_controller(controller) will be called after controller is defined below
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
       # talk.set_controller(controller) will be called after controller is defined below
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

    def update(self, error, dt, saturated=False):
        """
        Compute PID output.

        saturated: True when the servo is already at its mechanical limit in
                   the direction of the error.  When saturated we skip the
                   integral accumulation (back-calculation anti-windup) so the
                   integrator doesn't wind up against a wall and keep pushing
                   after the face re-enters the reachable range.
        """
        # Clamp dt to prevent derivative spikes from near-zero or very stale values
        raw_dt = dt
        dt = max(0.016, min(0.5, dt))
        # Proportional
        p = self.kp * error
        # Integral — skip accumulation if the actuator is saturated in the
        # same direction as the error (prevents windup against mechanical limits).
        if not saturated:
            self._integral += error * dt
            self._integral = max(-self.integral_max, min(self.integral_max, self._integral))
        i = self.ki * self._integral
        # Derivative — zero it out after a large frame gap (raw_dt > 0.25s).
        # prev_error is stale after an audio freeze; computing D from it would
        # produce a misleading kick on the first recovery frame.
        if raw_dt > 0.25:
            d = 0.0
            self._prev_error = error  # restart derivative from fresh position
        else:
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


## Initial head position (Y from config; X from headXPosition % or legacy 511)
def _home_xcoor():
    hp = config.get("headXPosition")
    if hp is None:
        return 511
    try:
        return int(Xmin + float(hp) / 100.0 * (Xmax - Xmin))
    except (TypeError, ValueError):
        return 511


Xcoor = _home_xcoor()
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

# Serialize WaitForSpeech — the main loop spawns this often; without a lock, races leave
# Listening stuck True and face LEDs frozen after the first utterance.
_wait_speech_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Face tracking state machine
# States: 0=SEARCHING (nose off), 1=DETECTING (nose green), 2=LOCKED (nose blue + recording)
# ---------------------------------------------------------------------------
TRACK_SEARCHING = 0
TRACK_DETECTING = 1
TRACK_LOCKED = 2
track_state = TRACK_SEARCHING
track_centered_since = 0.0          # time face first appeared centered
track_lock_threshold_sec = 0.8      # seconds centered before locking on (was 2.0 — faster engagement)
recording_process = None

_recording_grace_sec = float(config.get("recordingGraceSec", 2.0))
_recording_grace_until = 0.0

_recording_target_duration = 0
_cv_video_writer = None
_cv_record_end_time = 0

_last_servo_cmd_time = 0.0          # rate-limit servo writes to avoid overloading serial
_servo_cmd_min_interval = 0.04      # minimum seconds between servo commands (~25 Hz cap)
_servo_cmd_min_interval = float(config.get("faceTrackingServoInterval", _servo_cmd_min_interval))



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

def _stop_recording_if_grace_expired():
   """Stop recording only if the grace period has passed."""
   if time.time() >= _recording_grace_until:
       stop_voice_recording()


# ---------------------------------------------------------------------------
# FIX: Smoothed face centre — exponential moving average prevents the servo
#      chasing every single-frame bbox jitter that causes overshoot.
# Alpha closer to 1.0 = more responsive but jitterier.
# Alpha closer to 0.0 = smoother but slower to react.
# 0.55 balances responsiveness with PID-dampened stability without chasing jitter.
# ---------------------------------------------------------------------------
_smooth_alpha = float(config.get("faceTrackingSmoothAlpha", 0.55))
# _smoothed_cx / _smoothed_cy set after target_cx/target_cy (camera section below)


# FIX: Tracked servo speed cap — use SetServo (with speed) instead of
#      SetAngle (instant snap) so the motor can't accelerate past target.
#      Range 10–100. Lower = slower but less overshoot on fast moves.
_track_servo_speed = int(config.get("faceTrackingServoSpeed", 100))


if talk and hasattr(talk, "set_controller"):
    talk.set_controller(controller)

# Visual Recognition — optional; requires face_recognition + Pillow packages.
# Wrapped in try/except so a missing dependency doesn't prevent boot.
try:
    vc = VisualRecognition()
    print("VisualRecognition initialised.")
except Exception as _vc_err:
    vc = None
    print("VisualRecognition unavailable ({}); face greeting disabled.".format(_vc_err))

# Robust speaker initialization (retry loop using existing controller)
def _retry_enable_speaker(ctrl, max_retries=5, delay=2):
    print("PiFaceFast: ensuring speaker is enabled...")
    for i in range(max_retries):
        try:
            ctrl.SetEnableSpeaker(True)
            print("PiFaceFast: speaker enabled successfully.")
            return True
        except Exception as e:
            print(f"PiFaceFast: speaker enable attempt {i+1} failed: {e}")
            time.sleep(delay)
    return False

_retry_enable_speaker(controller)
wait_for_audio_hardware_visible()

try:
   controller.SetTouchAutoOff(0, 0, 0)
except Exception as e:
   print("SetTouchAutoOff error: %s" % e)


try:
   controller.SetMicrophoneGain(config['microphoneGain'])
except KeyError:
   controller.SetMicrophoneGain(100)


# Unlock hardware limits for the swapped orientation
try:
    controller.SetServoCwLimit(2, Xmin)
    controller.SetServoCcwLimit(2, Xmax)
    time.sleep(0.05)
    controller.SetServoCwLimit(1, Ymin)
    controller.SetServoCcwLimit(1, Ymax)
    time.sleep(0.05)
except Exception as e:
    print(f"Warning: could not set servo limits: {e}")

controller.SetServo(2, Xcoor, int(config["servoSpeed"]))
controller.SetServo(1, Ycoor, int(config["servoSpeed"]))
print("Positioning head: XCoor " + str(Xcoor) + ", YCoor " + str(Ycoor))


time.sleep(1)
controller.SetPid(2, 26, 2, 16)
time.sleep(1)
controller.SetPid(1, 26, 2, 16)
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
           controller.SetServoLed(2, 1)
           controller.SetServoLed(1, 1)
       except Exception:
           pass


def _touch_reaction_lights_off():
   if not _cfg_bool(config.get("touchReactionLights"), True):
       return
   if _cfg_bool(config.get("touchReactionServoLeds"), True):
       try:
           controller.SetServoLed(2, 0)
           controller.SetServoLed(1, 0)
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


# Detection always runs on a 320x240 frame; nominal centre (160, 120).
# Optional pixel offsets correct lens crop / mounting bias so "centered" matches where the face should sit.
frame_cx = 160
frame_cy = 120
_target_cx_offset = float(config.get("faceTrackingCenterOffsetX", 0) or 0)
_target_cy_offset = float(config.get("faceTrackingCenterOffsetY", 0) or 0)
target_cx = frame_cx + _target_cx_offset
target_cy = frame_cy + _target_cy_offset


_face_invert_pan  = _cfg_bool(config.get("faceTrackingInvertPan"), True)
_face_invert_tilt = _cfg_bool(config.get("faceTrackingInvertTilt"), False)
_camera_flip_h    = _cfg_bool(config.get("cameraFlipHorizontal"),   False)
_face_debug       = _cfg_bool(config.get("faceTrackingDebug"),      False)
_face_debug_interval = int(config.get("faceTrackingDebugInterval", 10))  # print every N frames
_track_dbg_n      = 0
_track_dead = int(config.get("faceTrackingDeadband", 16))   # widened: 14px error no longer chases
_stabilize_sec    = float(config.get("faceTrackingStabilizeSec", 0.20))  # was 0.35 — resume tracking sooner after a servo move
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

# PID gains — tuned for ~7 FPS tracking loop on Pi 5
_pid_kp = float(config.get("faceTrackingKp", 0.35))
_pid_ki = float(config.get("faceTrackingKi", 0.01))          # halved: less windup, less drift
_pid_kd = float(config.get("faceTrackingKd", 0.08))
_pid_integral_max = float(config.get("faceTrackingIntegralMax", 3.0))  # reduced: unwinds faster

# Max servo units the PID can move per frame — hard cap prevents overshoot
# regardless of PID tuning.  At ~5 FPS, 40 units/frame ≈ 200 units/sec.
_track_max_step = int(config.get("faceTrackingMaxStep", 40))

def _scheduled_kp(error, base_kp):
    """Reduce Kp for large errors to prevent overshoot at distance.
    Full gain within 30px, tapered down to 40% for errors above 80px."""
    abs_err = abs(error)
    if abs_err <= 30:
        return base_kp              # full gain when close to target
    elif abs_err >= 80:
        return base_kp * 0.4        # 40% gain for large distant errors
    else:
        # Linear taper between 30px and 80px
        t = (abs_err - 30) / 50.0
        return base_kp * (1.0 - 0.6 * t)

pid_pan  = PIDController(_pid_kp, _pid_ki, _pid_kd, _pid_integral_max)
pid_tilt = PIDController(_pid_kp, _pid_ki, _pid_kd, _pid_integral_max)
_last_track_time = time.time()

# ---------------------------------------------------------------------------
# DNN face detector (much more accurate than Haar cascades)
# ---------------------------------------------------------------------------
_face_detector_type = config.get("faceDetector", "dnn")  # "dnn" or "haar"
_dnn_confidence_min = float(config.get("faceDetectorConfidence", 0.35))
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


print("Camera resolution: {}x{}, track target: ({:.1f},{:.1f}) (frame center + offset)".format(
    frame_w, frame_h, target_cx, target_cy))
print("faceDetector={} dnnLoaded={} confidence={}".format(
     _face_detector_type, _dnn_net is not None, _dnn_confidence_min))
print("PID: Kp={} Ki={} Kd={} integralMax={} deadband={} maxStep={}".format(
     _pid_kp, _pid_ki, _pid_kd, _pid_integral_max, _track_dead, _track_max_step))
print("faceTrackingInvertPan={} faceTrackingCenterOffset=({},{}) cameraFlipHorizontal={} "
     "stabilizeSec={} smoothAlpha={} trackServoSpeed={} debug={} debugInterval={}".format(
     _face_invert_pan, _target_cx_offset, _target_cy_offset, _camera_flip_h,
     _stabilize_sec, _smooth_alpha, _track_servo_speed, _face_debug, _face_debug_interval))
print("serialTouchProbe={} (set false in config.yml to silence GET_TOUCH if UART is down)".format(
     _serial_touch_probe))


_smoothed_cx = float(target_cx)
_smoothed_cy = float(target_cy)


# ---------------------------------------------------------------------------
# Face recognition greeting state
# ---------------------------------------------------------------------------
_last_greeted_name = None          # avoid greeting the same person repeatedly
_greet_cooldown_sec = 30.0         # seconds before greeting the same person again
_last_greeted_tm = 0.0
_face_recog_pending = False        # flag set when a new face is first acquired
_webcam_busy = False               # guard against concurrent webcam access
_last_det_frame = None             # most recent detection frame — shared with greet thread




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
   # Drain 1 buffered frame so we get a fresh one without wasting detection cycles.
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
   Uses _last_det_frame (the most recent frame grabbed by the main loop)
   so it NEVER opens a second VideoCapture — V4L2 does not allow two
   concurrent opens of the same device and the attempt disrupts the
   main capture pipeline.
   """
   global _last_greeted_name, _last_greeted_tm, _face_recog_pending


   _face_recog_pending = False


   # vc is None when face_recognition / VisualRecognition failed to load at boot.
   if vc is None:
       if config["distro"] != "ibmwatson" and not Listening:
           serial_send(lambda: controller.SetNoseColor(4))
       return


   # Small delay so the main loop registers the face and sets green nose first.
   time.sleep(0.5)


   # Use the last frame the main loop already captured — no camera access needed.
   frame = _last_det_frame
   if frame is None:
       if config["distro"] != "ibmwatson" and not Listening:
           serial_send(lambda: controller.SetNoseColor(4))
       return


   try:
       # Write the shared frame to disk so vc.recognizeFaces() can read it.
       cv2.imwrite(vc.tmp_file, frame)
       vc.recognizeFaces()
   except Exception as _ge:
       print("greet_face_async recognition error: {}".format(_ge))
       if config["distro"] != "ibmwatson" and not Listening:
           serial_send(lambda: controller.SetNoseColor(4))
       return


   if not vc.faceResultsAvailable or not vc.faceResults:
       # Still make sure nose is green even if recognition found nothing
       if config["distro"] != "ibmwatson" and not Listening:
           serial_send(lambda: controller.SetNoseColor(4))
       return


   # Only act on the first (largest / most prominent) face in the frame
   name = vc.faceResults[0]


   if name == "Unknown":
       # Unknown face — green nose, no speech
       if config["distro"] != "ibmwatson" and not Listening:
           serial_send(lambda: controller.SetNoseColor(4))
       return


   now = time.time()
   # Only greet if it's a different person OR enough time has passed
   if name == _last_greeted_name and (now - _last_greeted_tm) < _greet_cooldown_sec:
       if config["distro"] != "ibmwatson" and not Listening:
           serial_send(lambda: controller.SetNoseColor(4))
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
       serial_send(lambda: controller.SetNoseColor(1))


   # QBOtalk.SpeechText() takes exactly one argument — the string to speak
   try:
       talk.SpeechText(greeting)
   except Exception as e:
       print("greet_face_async speech error: {}".format(e))


   if config["distro"] != "ibmwatson" and not Listening:
       serial_send(lambda: controller.SetNoseColor(4))




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


   Xcoor = _home_xcoor()
   Ycoor = int(Ymin + float(config["headYPosition"]) / 100 * (Ymax - Ymin))
   controller.SetServo(2, Xcoor, int(config["servoSpeed"]))
   time.sleep(0.1)
   controller.SetServo(1, Ycoor, int(config["servoSpeed"]))
   touch_tm = time.time()
   _face_stabilize_until = time.time() + _stabilize_sec


   # Reset smoother so stale position doesn't yank the head on next detection
   _smoothed_cx = float(target_cx)
   _smoothed_cy = float(target_cy)


   # Reset PID controllers so stale integral doesn't cause overshoot
   pid_pan.reset()
   pid_tilt.reset()
   _last_track_time = time.time()


   print("Repositioning head: XCoor " + str(Xcoor) + ", YCoor " + str(Ycoor))




def WaitForSpeech():
   global WaitingSpeech, Listening, listen_thd

   if not _wait_speech_lock.acquire(blocking=False):
       return

   try:
       if config["distro"] == "ibmwatson":
           if talk.onListeningChanged:
               talk.onListeningChanged = False
               if talk.onListening:
                   serial_send(lambda: controller.SetNoseColor(1))
               else:
                   serial_send(lambda: controller.SetNoseColor(0))


       # FIX: use 'and' not '&' for boolean logic
       if WaitingSpeech == False and interactiveTypeGAssistant == False:
           WaitingSpeech = True


           if Listening == False:
               WaitingSpeech = False
               return


           elif config["distro"] != "ibmwatson" and vc is not None and vc.askAboutMe(talk.strAudio):
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
               if config["distro"] != "ibmwatson" and listen_thd:
                   listen_thd(wait_for_stop=True)


               if len(talk.Response) > 0:
                   talk.SpeechText(talk.Response)


               if config["distro"] != "ibmwatson":
                   serial_send(lambda: controller.SetNoseColor(0))


               talk.GetResponse = False
               Listening = False
               StartHotwordListener()


           WaitingSpeech = False

   finally:
       _wait_speech_lock.release()




def WaitTouchMove():
   global Xcoor, Ycoor, touch_tm, mutex_wait_touch, faceFound


   if mutex_wait_touch:
       return


   mutex_wait_touch = True
   time.sleep(3)


   if faceFound:
       return


   _wx, _wy, _wspeed = Xcoor, Ycoor, int(config["servoSpeed"])
   serial_send(lambda: controller.SetServo(2, _wx, _wspeed))
   time.sleep(0.1)
   serial_send(lambda: controller.SetServo(1, _wy, _wspeed))
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
   global Listening
   try:
       talk.record_wav()
       talk.detect_intent_stream()
   except Exception as e:
       print("DialogflowV2SeeFace error: {}".format(e))
   finally:
       # Always release the Listening gate so the main loop can trigger again.
       Listening = False
       StartHotwordListener()




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
# External Command Listener (from BLE / Web Dashboard)
# ---------------------------------------------------------------------------
FIFO_CMD = "/opt/qbo/pipes/pipe_cmd"

def external_command_listener():
    """Reads commands from named pipe and executes them via controller."""
    if not os.path.exists(os.path.dirname(FIFO_CMD)):
        os.makedirs(os.path.dirname(FIFO_CMD), exist_ok=True)
    
    try:
        os.mkfifo(FIFO_CMD)
    except OSError as e:
        if e.errno != errno.EEXIST:
            print(f"Error creating command pipe: {e}")

    print(f"External command listener started: {FIFO_CMD}")
    while True:
        try:
            # open blocks until someone writes to it
            with open(FIFO_CMD, "r") as fifo:
                line = fifo.read().strip()
                if not line:
                    continue
                
                print(f"External command received: {line}")
                
                # Handle recording commands e.g. REC_10, REC_30
                if line.startswith("REC_"):
                    try:
                        duration = int(line.split("_")[1])
                        global _recording_target_duration
                        _recording_target_duration = duration
                    except (IndexError, ValueError):
                        print(f"External command: invalid REC format: {line}")
                    continue
                
                # Handle standard QBO command strings (e.g. -c nose -co blue)
                # We can reuse the logic from PiCmd.py or implement a simple one here.
                # For now, let's support basic nose and servo commands.
                parts = line.split()
                if "-c" in parts:
                    cmd_idx = parts.index("-c") + 1
                    if cmd_idx < len(parts):
                        cmd_name = parts[cmd_idx]
                        
                        if cmd_name == "nose" and "-co" in parts:
                            color_idx = parts.index("-co") + 1
                            if color_idx < len(parts):
                                color = parts[color_idx]
                                colors = {"none": 0, "blue": 1, "red": 2, "green": 4}
                                if color in colors:
                                    _c = colors[color]
                                    serial_send(lambda: controller.SetNoseColor(_c))
                        
                        elif cmd_name == "move_rel" and "-x" in parts and "-a" in parts:
                            try:
                                ax = int(parts[parts.index("-x") + 1])
                                ang = int(parts[parts.index("-a") + 1])
                                serial_send(lambda: controller.SetAngleRelative(ax, ang))
                            except: pass

        except Exception as e:
            print(f"External command listener error: {e}")
            time.sleep(1)

_thread.start_new_thread(external_command_listener, ())


# ---------------------------------------------------------------------------
# Speech worker — Fix 2 from qbo_serial_improvements.md
# Single persistent thread replaces spawning a new WaitForSpeech thread every
# loop iteration (~20× per second = thread storm).
# ---------------------------------------------------------------------------
_speech_event = threading.Event()

def _speech_worker():
    while True:
        _speech_event.wait()   # sleeps until signalled
        _speech_event.clear()
        WaitForSpeech()

threading.Thread(target=_speech_worker, daemon=True, name="speech_worker").start()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


while True:
   fr_time = time.time()

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


   if _recording_target_duration > 0:
       timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
       filename = f"/opt/qbo/recordings/clip_{timestamp}.avi"
       os.makedirs(os.path.dirname(filename), exist_ok=True)
       fourcc = cv2.VideoWriter_fourcc(*'MJPG')
       fps = _dbg_fps_value if _dbg_fps_value > 2 else 15.0
       _cv_video_writer = cv2.VideoWriter(filename, fourcc, fps, (320, 240))
       if _cv_video_writer.isOpened():
           _cv_record_end_time = time.time() + _recording_target_duration
           global _cv_last_filename
           _cv_last_filename = filename
           print(f"VideoRecorder: Started OpenCV recording to {filename} for {_recording_target_duration}s")
       else:
           print("VideoRecorder: Failed to open cv2.VideoWriter codec")
           _cv_video_writer = None
       _recording_target_duration = 0
   faceFound = False
   _speech_event.set()   # signal the persistent speech_worker instead of spawning a new thread


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
           if _cv_video_writer is not None:
               if time.time() > _cv_record_end_time:
                   _cv_video_writer.release()
                   _cv_video_writer = None
                   print("VideoRecorder: OpenCV recording finished.")
                   if '_cv_last_filename' in globals() and _cv_last_filename:
                       import subprocess
                       mp4_file = _cv_last_filename.replace('.avi', '.mp4')
                       print(f"VideoRecorder: Transcoding {_cv_last_filename} to {mp4_file} via ffmpeg...")
                       subprocess.Popen([
                           "ffmpeg", "-y", "-i", _cv_last_filename,
                           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", mp4_file
                       ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
               else:
                   _cv_video_writer.write(aframe)
           _last_det_frame = aframe  # share with greet_face_async (avoids 2nd camera open)
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


       # 25 missed frames (~1.25s at 7 FPS) before losing lock — tolerates brief
       # occlusions, blinks, and head turns without dropping the tracking state.
       if face_not_found_idx > 25:
           face_not_found_idx = 0
           lastface = 0
           face = [0, 0, 0, 0]


           # ---- State machine: transition to SEARCHING ----
           if track_state != TRACK_SEARCHING:
               print("Face lost -> SEARCHING")
               _stop_recording_if_grace_expired()
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
               print("No face, 10 times!")


           elif time.time() - no_face_tm > 4:
               # Slow search sweep before snapping fully home — looks more natural
               # than instantly centering. Sweeps gently left then right.
               _sweep_x = Xcoor
               _home_x = _home_xcoor()
               if abs(_sweep_x - _home_x) > 30:
                   # Drift back toward home gradually rather than snapping
                   _step = 20 if _sweep_x > _home_x else -20
                   Xcoor = max(Xmin, min(Xmax, Xcoor + _step))
                   controller.SetServo(2, Xcoor, 60)  # slow, natural return
               else:
                   ServoHome()
               Cface = [0, 0]
               no_face_tm = time.time()


   # --- Face found ---
   else:
       last_face_det_tm = time.time()
       x, y, w, h = face


       # Raw face centre from Haar bbox
       raw_cx = float(x) + float(w) * 0.5
       raw_cy = float(y) + float(h) * 0.5


       # Exponential moving average smoothing — kills jitter-driven overshoot.
       # _smooth_alpha default lowered from 0.85 to 0.55 to reduce jitter chasing.
       if Facedet == 0:
           _smoothed_cx = raw_cx
           _smoothed_cy = raw_cy
       else:
           _smoothed_cx = _smooth_alpha * raw_cx + (1.0 - _smooth_alpha) * _smoothed_cx
           _smoothed_cy = _smooth_alpha * raw_cy + (1.0 - _smooth_alpha) * _smoothed_cy


       Cface = [_smoothed_cx, _smoothed_cy]


       # ---- Compute face offsets for state machine & servo tracking ----
       faceOffset_X = float(target_cx) - Cface[0]
       if _face_invert_pan:
           faceOffset_X = -faceOffset_X
       faceOffset_Y = Cface[1] - float(target_cy)
       if _face_invert_tilt:
           faceOffset_Y = -faceOffset_Y
       face_is_centered = (abs(faceOffset_X) <= _track_dead and abs(faceOffset_Y) <= _track_dead)


       # ---- State machine: SEARCHING -> DETECTING (green) ----
       if Facedet == 0:
           Facedet = 1
           face_det_tm = time.time()
           # _stabilize_sec default lowered from 0.35 to 0.20 so tracking resumes faster
           _face_stabilize_until = time.time() + _stabilize_sec
           track_state = TRACK_DETECTING
           track_centered_since = 0.0
           _last_track_time = time.time()
           pid_pan.reset()
           pid_tilt.reset()
           print("Face found -> DETECTING (green)")


           if config["distro"] != "ibmwatson":
               controller.SetNoseColor(4)  # Green


           # Trigger background face recognition + greeting
           _face_recog_pending = True
           _thread.start_new_thread(greet_face_async, ())


       # ---- State machine: DETECTING -> LOCKED ----
       elif track_state == TRACK_DETECTING:
           if config["distro"] != "ibmwatson":
               controller.SetNoseColor(4)  # Stay green while detecting


           if face_is_centered:
               if track_centered_since == 0.0:
                   track_centered_since = time.time()
               # Reduced threshold from 2.0s to 0.8s for faster locking
               elif time.time() - track_centered_since >= 0.8:
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
           # Nose already set blue on state entry — do NOT resend every frame (serial spam)
           # If face drifts off-center significantly, drop back to DETECTING
           if not face_is_centered:
               track_state = TRACK_DETECTING
               track_centered_since = 0.0
               # Don't stop recording immediately — brief drift or detection wobble
               # should not cut an active conversation
               _recording_grace_until = time.time() + _recording_grace_sec
               print("Face moved -> DETECTING (recording grace period {:.1f}s)".format(_recording_grace_sec))
               if config["distro"] != "ibmwatson":
                   serial_send(lambda: controller.SetNoseColor(4))  # Green


       # ---- Hotword/assistant: trigger only when face is LOCKED (confirmed centered) ----
       if (Listening == False and WaitingSpeech == False and
             track_state == TRACK_LOCKED and
             (time.time() - face_det_tm > 1.5)):
           face_det_tm = time.time()


           if Listening == False:
               StopHotwordListener()


               if interactiveTypeGAssistant == True:
                   gassistant.start_conversation_from_face()
               elif interactiveTypeGAssistant == False and config["startWith"] == "interactive-dialogflow-v2":
                   # Run in a background thread — recording takes 5-7s and would
                   # freeze the tracking loop if called directly here.
                   _thread.start_new_thread(DialogflowV2SeeFace, ())
                   Listening = True
               else:
                   listen_thd = talk.StartBack()
                   Listening = True


       # --- Pan / tilt servo tracking (PID) ---
       # Guard: skip while LOCKED — face already centered, head holds position during recording.
       # This removes 25Hz SetServo spam from the Arduino's busiest serial window.
       if touch_det == False and time.time() >= _face_stabilize_until and track_state != TRACK_LOCKED:
           now = time.time()
           dt = now - _last_track_time
           _last_track_time = now

           # Saturated = servo already at its limit in the error direction.
           # Passing True stops integral accumulation against the wall (back-calc anti-windup).
           _pan_sat = (Xcoor <= Xmin and faceOffset_X < 0) or (Xcoor >= Xmax and faceOffset_X > 0)
           _tilt_sat = (Ycoor <= Ymin and faceOffset_Y < 0) or (Ycoor >= Ymax and faceOffset_Y > 0)

           _kp_pan  = _scheduled_kp(faceOffset_X, _pid_kp)
           _kp_tilt = _scheduled_kp(faceOffset_Y, _pid_kp)
           pid_pan.kp  = _kp_pan
           pid_tilt.kp = _kp_tilt
           pan_out = pid_pan.update(faceOffset_X, dt, saturated=_pan_sat)
           tilt_out = pid_tilt.update(faceOffset_Y, dt, saturated=_tilt_sat)

           # Combined rate-limited block
           if now - _last_servo_cmd_time >= _servo_cmd_min_interval:
               pan_moved = False
               if abs(faceOffset_X) > _track_dead:
                   if dt > 0.25:
                       _smoothed_cx = raw_cx
                       _smoothed_cy = raw_cy
                       print("Frame gap {:.2f}s — EMA smoother reset to raw position.".format(dt))
                   pan_step = max(-_track_max_step, min(_track_max_step, int(pan_out)))
                   Xcoor = max(Xmin, min(Xmax, Xcoor + pan_step))
                   serial_send_tracking(lambda x=Xcoor: controller.SetServo(2, x, _track_servo_speed))
                   pan_moved = True
               else:
                   pid_pan.decay_integral()

               if abs(faceOffset_Y) > _track_dead:
                   if pan_moved:
                       time.sleep(0.01)
                   tilt_step = max(-_track_max_step, min(_track_max_step, int(tilt_out)))
                   Ycoor = max(Ymin, min(Ymax, Ycoor + tilt_step))
                   serial_send_tracking(lambda y=Ycoor: controller.SetServo(1, y, _track_servo_speed))
               else:
                   pid_tilt.decay_integral()

               _last_servo_cmd_time = now


           if _face_debug:
               _track_dbg_n += 1
               if _track_dbg_n % _face_debug_interval == 0:
                   _sm_dx = _smoothed_cx - raw_cx
                   _sm_dy = _smoothed_cy - raw_cy
                   print("TRACK #{}: raw=({:.0f},{:.0f}) smooth=({:.0f},{:.0f}) Dsmooth=({:.1f},{:.1f}) "
                         "offset=({:.1f},{:.1f}) centered={} state={}".format(
                         _track_dbg_n, raw_cx, raw_cy, _smoothed_cx, _smoothed_cy,
                         _sm_dx, _sm_dy, faceOffset_X, faceOffset_Y,
                         face_is_centered, _dbg_state_names.get(track_state, "??")))
                   print("  PAN  pid: P={:.2f} I={:.2f} D={:.2f} out={:.2f} | integral={:.2f} | servo X={} sat={}".format(
                         pid_pan.last_p, pid_pan.last_i, pid_pan.last_d, pid_pan.last_output,
                         pid_pan._integral, Xcoor, _pan_sat))
                   print("  TILT pid: P={:.2f} I={:.2f} D={:.2f} out={:.2f} | integral={:.2f} | servo Y={} sat={}".format(
                         pid_tilt.last_p, pid_tilt.last_i, pid_tilt.last_d, pid_tilt.last_output,
                         pid_tilt._integral, Ycoor, _tilt_sat))
                   print("  face={}x{} conf={:.2f} det={:.1f}ms dt={:.3f}s deadband={} FPS={:.1f}".format(
                         _dbg_last_face_w, _dbg_last_face_h, _dbg_last_conf,
                         _dbg_last_det_ms, dt, _track_dead, _dbg_fps_value))


   # --- Touch sensor ---
   if _serial_touch_probe and (time.time() - touch_samp > 0.5):
       if time.time() - _last_servo_cmd_time < 0.05:
           time.sleep(0.02)
       touch_samp = time.time()
       last_face_det_tm = time.time()
       qbo_touch = controller.GetHeadCmd("GET_TOUCH", 0)
       time.sleep(0.002)


       if touch_tm == 0 and qbo_touch and qbo_touch != [0]:
           _touch_reaction_lights_on()
           if qbo_touch == [1]:
               controller.SetServo(2, Xmax - 25, int(config["servoSpeed"]))
               time.sleep(0.002)
               controller.SetServo(1, Ymin - 5, int(config["servoSpeed"]))
               _thread.start_new_thread(WaitTouchMove, ())
               time.sleep(1)


           elif qbo_touch == [2]:
               time.sleep(0.002)
               controller.SetServo(1, Ymin - 5, int(config["servoSpeed"]))
               _thread.start_new_thread(WaitTouchMove, ())
               time.sleep(1)


           elif qbo_touch == [3]:
               controller.SetServo(2, Xmin + 25, int(config["servoSpeed"]))
               time.sleep(0.002)
               controller.SetServo(1, Ymin - 5, int(config["servoSpeed"]))
               _thread.start_new_thread(WaitTouchMove, ())
               time.sleep(1)


   if touch_tm != 0 and time.time() - touch_tm > touch_wait:
       print("touch ready")
       touch_tm = 0
       _touch_reaction_lights_off()


   # Throttle main loop to ~20 Hz max — gives the Pi more time per frame for DNN inference
   # and reduces serial bus contention. 0.05s = 20 FPS cap (was 0.033 / 30 FPS).
   time.sleep(0.05)




stop_voice_recording()







