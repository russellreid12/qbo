import os
import threading
import time
from contextlib import contextmanager
from typing import Callable, Optional

import numpy as np


@contextmanager
def _suppress_c_stderr():
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


if not os.environ.get("QBO_VERBOSE_LIBS"):
	os.environ.setdefault("ORT_LOG_SEVERITY_LEVEL", "4")
	try:
		import onnxruntime as ort
		ort.set_default_logger_severity(4)
	except Exception:
		pass

def _download_openwakeword_resources_fallback():
	"""Download FEATURE_MODELS + one wakeword when utils.download_models is absent (newer openWakeWord)."""
	import urllib.request

	fm = getattr(openwakeword, "FEATURE_MODELS", None)
	if not fm:
		return
	for _name, info in fm.items():
		path = info["model_path"]
		url = info.get("download_url")
		if not url:
			continue
		os.makedirs(os.path.dirname(path), exist_ok=True)
		if os.path.isfile(path) and os.path.getsize(path) > 1000:
			continue
		urllib.request.urlretrieve(url, path)
	models = getattr(openwakeword, "MODELS", {})
	for _key, info in models.items():
		path = info["model_path"]
		url = info.get("download_url")
		if not url:
			continue
		os.makedirs(os.path.dirname(path), exist_ok=True)
		if os.path.isfile(path) and os.path.getsize(path) > 1000:
			continue
		urllib.request.urlretrieve(url, path)


HAVE_OPENWAKEWORD = False
openwakeword = None
Model = None
try:
	with _suppress_c_stderr():
		import openwakeword
		from openwakeword.model import Model
	HAVE_OPENWAKEWORD = True
except ImportError:
	openwakeword = None
	Model = None
	HAVE_OPENWAKEWORD = False


class OpenWakeWordListener:
	"""
	Simple wrapper that runs an openWakeWord model in a background thread and
	calls a callback whenever the wake word is detected.
	"""

	def __init__(self, callback: Callable[[], None], sample_rate: int = 16000, block_size: int = 512):
		self.callback = callback
		self.sample_rate = sample_rate
		self.block_size = block_size
		self._stop = threading.Event()
		self._thread: Optional[threading.Thread] = None
		self._model: Optional[Model] = None

	def start(self):
		if not HAVE_OPENWAKEWORD:
			print("Warning: openwakeword is not installed. Hotword will be disabled.")
			return

		if self._thread is not None:
			return

		# Older PyPI: openwakeword.utils.download_models(). Newer git/main: removed — pull URLs from package.
		try:
			utils = getattr(openwakeword, "utils", None)
			if utils is not None and hasattr(utils, "download_models"):
				utils.download_models()
			else:
				_download_openwakeword_resources_fallback()
		except Exception as e:
			print("Warning: openwakeword model fetch:", e)

		try:
			with _suppress_c_stderr():
				self._model = Model()
		except Exception as e:
			print("Error initializing openwakeword Model:", e)
			return

		self._thread = threading.Thread(target=self._run, daemon=True)
		self._thread.start()

	def _run(self):
		import sounddevice as sd

		def audio_callback(indata, frames, time_info, status):
			if self._stop.is_set() or self._model is None:
				raise sd.CallbackStop()

			audio = indata[:, 0].astype(np.float32)
			scores = self._model.predict(audio)

			# If any wake-word model crosses its internal threshold,
			# trigger the callback.
			try:
				if any(score > 0.5 for score in scores.values()):
					self.callback()
			except Exception as e:
				print("Error in hotword callback:", e)

		try:
			with _suppress_c_stderr():
				with sd.InputStream(
					channels=1,
					samplerate=self.sample_rate,
					blocksize=self.block_size,
					callback=audio_callback,
				):
					while not self._stop.is_set():
						time.sleep(0.1)
		except Exception as e:
			print("Error starting audio input stream for openwakeword:", e)

	def stop(self):
		self._stop.set()
		if self._thread is not None:
			self._thread.join(timeout=2.0)
			self._thread = None

