# Q.bo Video Recording & BLE Transfer Architecture

This document outlines how video clips are recorded directly on the Q.bo robot and transferred over Bluetooth Low Energy (BLE) to the React dashboard.

## 1. Recording Architecture (PiFaceFast.py)

Historically, Q.bo tried to record video using an external `ffmpeg` subprocess (`video_recorder.py`). However, because `PiFaceFast.py`'s face tracking system holds an exclusive V4L2 lock on the primary webcam (`/dev/video0`), `ffmpeg` would silently fail with a `Device or resource busy` error. 

To solve this, recording is now handled **natively inside the main face tracking loop** using OpenCV's `cv2.VideoWriter`.

### How it Works:
1. **Command Reception**: When `PiFaceFast.py` receives a `REC_10` command over its local pipe (`/opt/qbo/pipes/pipe_cmd`), it sets a global `_recording_target_duration` to 10 seconds.
2. **File Initialization**: The main loop detects this flag, generates a unique timestamped filename (e.g., `/opt/qbo/recordings/clip_20240409_120000.mp4`), and initializes a `cv2.VideoWriter` object using the `mp4v` codec.
3. **Seamless Capture**: On exactly the same frame the robot uses to run face detection, a copy of the frame is written directly to the `VideoWriter`. **This means face tracking does not pause or stutter during recording.**
4. **Finalization**: After 10 seconds, the loop automatically releases the `VideoWriter`, safely closing the file so it can be streamed over BLE.

## 2. BLE Data Transfer (BleCmdServer.py)

Because BLE has very strict Maximum Transmission Unit (MTU) limitations and is not designed for heavy payloads, sending a whole video file requires a specialized chunking architecture.

The BLE server has a dedicated **DATA Characteristic** (`7f4b0004-...`) created specifically for bulk data.

### Requesting the Clip List
- **Command**: The React app sends the text string `LIST_CLIPS` to the standard COMMAND characteristic.
- **Processing**: The BLE server asynchronously scans `/opt/qbo/recordings/`, gathers file sizes, and serializes the list as JSON.
- **Response**: The server pushes a notification to the DATA characteristic prefixed with `LIST:` followed by the JSON array.

### Downloading a Clip
- **Command**: The React app sends `GET_CLIP:clip_name.mp4` to the COMMAND characteristic.
- **Chunking Pipeline**: The BLE server reads the MP4 file and slices it into **490-byte chunks**. 
- **Header Injection**: To prevent out-of-order packets if the connection drops, each chunk is prefixed with a 4-byte Big-Endian sequence number:
  `[ 4-byte Seq # ] + [ Up to 490 bytes of H.264 binary data ]`
- **Streaming**: These chunks are blasted over BLE Notifications with a slight `asyncio.sleep(0.015)` delay between chunks to avoid overwhelming the Linux kernel's Bluetooth queues.
- **Completion**: Once the file is exhausted, a final `CLIP_END` text notification is sent.

### React Client Pipeline (bleRobot.ts)
On the browser side, the `BleRobotClient` intercepts these notifications:
1. Extracts the sequence number.
2. Stores the binary chunk in a Javascript `Map`.
3. Updates the live progress bar.
4. On `CLIP_END`, it extracts all chunks in sequential order, combines them, and generates an in-memory blob URL (`blob:http://...`) that can be played by a standard HTML5 `<video>` tag.

---

## 3. Troubleshooting Guide

#### "Clip list request timed out after 15s"
The React app is trying to listen to the new DATA characteristic, but the old version of `BleCmdServer.py` is running on the robot. 
**Fix**: `pkill -f BleCmdServer.py` and restart it using the latest code.

#### Video records but cannot be played in browser
The `mp4v` codec requires the browser to support MP4 playback. All modern browsers (Chrome/Edge/Safari) support it, but if OpenCV failed to locate the `mp4v` extension properly, the file might just be a wrapper. 
**Fix**: You can pull the file off manually to test: `scp pi@qbo.local:/opt/qbo/recordings/clip_*.mp4 .`

#### Heartbeat/Connection drops during wide video transfers
Transferring ~500KB over BLE saturates the connection for 30–60 seconds. If the React app sends standard heartbeat commands (`nose off`) at the same time, it can crash the GATT queue.
**Fix**: `bleRobot.ts` is explicitly designed to call `this.stopHeartbeat()` before a download, and `this.startHeartbeat()` upon `CLIP_END`. If crashes persist, increase the `asyncio.sleep()` delay in `BleCmdServer.py`'s `_stream_clip_async` function. 

#### "Device or resource busy" in `video_recorder.py` logs
If you see this, it means you attempted to trigger `ffmpeg` while `PiFaceFast.py` was holding the camera. `video_recorder.py` is entirely obsolete in the new architecture and is no longer called by the system. All recording should run exclusively via the internal `cv2.VideoWriter`.
