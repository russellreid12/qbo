from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
import os
import glob

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

CLIP_DIR = "/opt/qbo/recordings"

@app.route("/clips", methods=["GET"])
def list_clips():
    """Returns a list of all recorded mp4 files, newest first."""
    if not os.path.exists(CLIP_DIR):
        return jsonify([])
    
    # Get all .mp4 files and sort by modification time (descending)
    files = sorted(glob.glob(os.path.join(CLIP_DIR, "*.mp4")), 
                   key=os.path.getmtime, 
                   reverse=True)
    
    return jsonify([os.path.basename(f) for f in files])

@app.route("/clips/<filename>", methods=["GET"])
def get_clip(filename):
    """Serves a specific video file."""
    return send_from_directory(CLIP_DIR, filename)

if __name__ == "__main__":
    # Start server on port 5000, accessible from all network interfaces
    app.run(host="0.0.0.0", port=5000)
