import threading
import time
from typing import Callable, Optional

import numpy as np

try:
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

		# Ensure models are available (downloads pre-trained ones if needed)
		try:
			openwakeword.utils.download_models()
		except Exception as e:
			print("Error downloading openwakeword models:", e)
			return

		try:
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

