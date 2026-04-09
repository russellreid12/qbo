import subprocess
import os
import time
import glob
from datetime import datetime

CLIP_DIR = "/opt/qbo/recordings"
MAX_STORAGE_MB = 500

def ensure_storage_ready():
    """Ensure CLIP_DIR exists and has enough space (500MB cap)."""
    if not os.path.exists(CLIP_DIR):
        os.makedirs(CLIP_DIR, exist_ok=True)
    
    # Check total size of records
    files = sorted(glob.glob(os.path.join(CLIP_DIR, "*.mp4")), key=os.path.getmtime)
    total_size = sum(os.path.getsize(f) for f in files)
    
    # Delete oldest if exceeding 500MB
    while total_size > (MAX_STORAGE_MB * 1024 * 1024) and files:
        oldest_file = files.pop(0)
        size = os.path.getsize(oldest_file)
        os.remove(oldest_file)
        total_size -= size
        print(f"VideoRecorder: Storage limit reached. Deleted oldest clip: {oldest_file}")

def record_clip(duration=10):
    """
    Triggers a background ffmpeg process to record a 30s clip.
    Uses hardware acceleration (h264_v4l2m2m) for Pi efficiency.
    """
    ensure_storage_ready()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{CLIP_DIR}/qbo_clip_{timestamp}.mp4"
    
    # -y: overwrite
    # -f v4l2: use V4L2 device
    # -i /dev/video0: camera device (adjust if needed via config)
    # -t: duration
    # -c:v: video codec (hardware accelerated)
    # -b:v: bitrate (2M is plenty for 320x240)
    cmd = [
        "ffmpeg", "-y",
        "-i", "/dev/video0",
        "-t", str(duration),
        filename
    ]

    log_path = f"{CLIP_DIR}/ffmpeg_last.log"
    try:
        with open(log_path, "w") as log_f:
            proc = subprocess.Popen(cmd, stdout=log_f, stderr=log_f)
        print(f"VideoRecorder: Started {duration}s recording to {filename} (pid={proc.pid})")
        return filename
    except Exception as e:
        print(f"VideoRecorder: Error starting ffmpeg: {e}")
        return None

if __name__ == "__main__":
    # Test run
    record_clip(5)
