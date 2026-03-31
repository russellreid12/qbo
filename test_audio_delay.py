import sys
import os
import time

# Mock the config
config = {
    "audioBootDelay": 1
}
#xx
# Add current directory to sys.path to import qbo_audio
# Assuming we are running from the workspace root
sys.path.append(os.path.abspath("./qbo"))
import qbo_audio

print("--- Testing aplay_wav_shell_play_wav (Shell Fragment) ---")
# Reset state for clean test
qbo_audio._AUDIO_READY = False

cmd = qbo_audio.aplay_wav_shell_play_wav(config, "dummy.wav")
print(f"Generated command with 1s delay: {cmd}")
if "sleep 1" in cmd:
    print("SUCCESS: Delay included in shell command.")
else:
    print("FAILURE: Delay NOT included in shell command.")

cmd2 = qbo_audio.aplay_wav_shell_play_wav(config, "dummy.wav")
print(f"Generated command (second call): {cmd2}")
if "sleep" not in cmd2:
    print("SUCCESS: Second call has no delay.")
else:
    print("FAILURE: Second call still has delay.")

print("\n--- Testing subprocess_aplay_wav (Python Blocking) ---")
qbo_audio._AUDIO_READY = False
start = time.time()
# This will try to run 'aplay', which might fail, but we care about the sleep before it.
try:
    qbo_audio.subprocess_aplay_wav(config, "nonexistent.wav")
except Exception as e:
    pass

elapsed = time.time() - start
print(f"Elapsed time for 1s delay: {elapsed:.2f}s")
if elapsed >= 1.0:
    print("SUCCESS: subprocess_aplay_wav slept.")
else:
    print("FAILURE: subprocess_aplay_wav did not sleep.")

qbo_audio._AUDIO_READY = True # Should prevent sleep
start = time.time()
try:
    qbo_audio.subprocess_aplay_wav(config, "nonexistent.wav")
except Exception as e:
    pass
elapsed = time.time() - start
print(f"Elapsed time (already ready): {elapsed:.2f}s")
if elapsed < 0.5:
    print("SUCCESS: No sleep when already ready.")
else:
    print("FAILURE: Unexpected sleep.")
