# BLE Server Troubleshooting Guide

This document covers all known issues with the Q.bo BLE command pipeline and their fixes.

---

## Architecture Overview

```
React App (browser)
    │  BLE writeValue()
    ▼
BleCmdServer.py  (runs on Pi, advertises GATT service)
    │  writes to named pipe
    ▼
/opt/qbo/pipes/pipe_cmd  (Linux FIFO)
    │  reads from named pipe
    ▼
PiFaceFast.py  →  external_command_listener()  →  executes command
```

---

## Issue 1 — GATT Errors: "NetworkError: GATT operation already in progress"

### Symptom
The React app throws one or both of:
```
NetworkError: GATT operation already in progress.
NotSupportedError: GATT operation failed for unknown reason.
```

### Cause
The heartbeat in `bleRobot.ts` sends `-c nose -co none` every 5 seconds to keep
the BLE link alive. If a user action (e.g. Record button) fires at the same time
as a heartbeat write, two `writeValue()` calls overlap on the same GATT
characteristic. Web Bluetooth does not allow concurrent GATT operations.

### Fix — `react/src/services/bleRobot.ts`
Added a **write queue** so only one BLE write executes at a time:
- `sendCommand()` enqueues every write as a Promise.
- `processQueue()` drains the queue one-at-a-time, preventing overlapping GATT operations.

---

## Issue 2 — Commands Received by BleCmdServer but Not Executed

### Symptom
BleCmdServer logs show `BLE command received: ...` but the robot does nothing.
Manually writing to the pipe hangs:
```bash
echo "-c nose -co blue" > /opt/qbo/pipes/pipe_cmd   # hangs indefinitely
```
`lsof /opt/qbo/pipes/pipe_cmd` returns nothing (no reader attached).

### Root Cause — Missing `import errno` in `PiFaceFast.py`
`external_command_listener()` (added to `PiFaceFast.py`) uses `errno.EEXIST`
when creating the pipe with `os.mkfifo()`. Because `errno` was never imported,
the listener thread crashed immediately with:
```
NameError: name 'errno' is not defined
```
Python's `_thread` silently swallows this exception, so PiFaceFast.py continued
running normally — but with no pipe listener active.

### Fix — `PiFaceFast.py`
Added `import errno` to the imports at the top of the file (line ~11).

---

## Issue 3 — BleCmdServer Hangs, Causing GATT Timeouts

### Symptom
After fixing Issue 2, `BleCmdServer.py` itself blocked on pipe writes, still
causing GATT timeouts. The BLE asyncio event loop froze.

### Root Cause
`publish_to_qbo()` originally used:
```python
with open(FIFO_CMD, "w", encoding="utf-8") as fifo:
    fifo.write(command + "\n")
```
On Linux, opening a named FIFO for writing **blocks until a reader opens the
other end**. If PiFaceFast's listener was between read cycles, `BleCmdServer`
would freeze indefinitely — stalling the asyncio event loop and causing all
subsequent BLE writes to fail with GATT errors.

An intermediate attempt using `O_NONBLOCK` caused commands to be silently
dropped during the brief window between PiFaceFast read cycles.

### Fix — `BleCmdServer.py`
The pipe write is now done in a **background daemon thread**:
```python
def _write_to_pipe(command: str) -> None:
    """Blocking write — runs in its own thread so it never stalls the BLE event loop."""
    try:
        with open(FIFO_CMD, "w", encoding="utf-8") as fifo:
            fifo.write(command + "\n")
        logger.info("Command written to pipe: %s", command)
    except OSError as e:
        logger.warning("pipe_cmd write error for '%s': %s", command, e)

def publish_to_qbo(command: str) -> None:
    ensure_pipe(FIFO_CMD)
    t = threading.Thread(target=_write_to_pipe, args=(command,), daemon=True)
    t.start()
```
- The BLE callback returns instantly → no GATT timeouts.
- The thread blocks until PiFaceFast reads → commands are reliably delivered.

---

## Issue 4 — "Maximum advertisements reached" on BleCmdServer Restart

### Symptom
```
dbus_next.errors.DBusError: Maximum advertisements reached
```

### Cause
BlueZ still holds a stale BLE advertisement registration from the previous
BleCmdServer run that did not clean up (e.g. killed with Ctrl+C or SIGKILL).

### Fix
Reset the Bluetooth stack before restarting:
```bash
sudo systemctl restart bluetooth
sleep 2
python3 /opt/qbo/BleCmdServer.py
```

---

## Issue 5 — Video Clips Page Cannot Connect to Video Server

### Symptom
```
Could not connect to video server. Ensure video_server.py is running on port 5000.
```

### Cause
`ClipsPage.tsx` originally used `window.location.hostname` to build the API URL.
When the React dev server runs on a Windows machine, `window.location.hostname`
resolves to `localhost` — not the Pi. The video server on port 5000 is on the Pi,
not localhost.

### Fix — `react/src/pages/ClipsPage.tsx`
Changed to always target the robot's hostname, using an optional env variable for
flexibility:
```tsx
const ROBOT_HOST = import.meta.env.VITE_ROBOT_HOST ?? 'QBo.local';
const API_BASE = `http://${ROBOT_HOST}:5000`;
```

If `QBo.local` does not resolve on your network, create `react/.env.local`:
```
VITE_ROBOT_HOST=192.168.x.x
```
Find the Pi's IP with: `hostname -I`

---

## Startup Checklist

Run these on the Pi before using the React dashboard:

```bash
# 1. Ensure PiFaceFast is running (interactive mode starts it automatically)
ps aux | grep PiFaceFast

# 2. Verify the pipe listener is active (should show PiFaceFast as reader)
lsof /opt/qbo/pipes/pipe_cmd

# 3. Quick pipe test — should return immediately and nose turns blue
echo "-c nose -co blue" > /opt/qbo/pipes/pipe_cmd

# 4. Start BLE server (reset Bluetooth first if it was previously running)
sudo systemctl restart bluetooth && sleep 2
python3 /opt/qbo/BleCmdServer.py

# 5. Start the video clip server
nohup python3 /opt/qbo/video_server.py &

# 6. Confirm PiCmd.py is NOT running (it competes for pipe_cmd)
/opt/qbo/scripts/QBO_PiCmd.sh stop
```

---

## Supported BLE Commands

| Command string         | Action                              |
|------------------------|-------------------------------------|
| `-c nose -co blue`     | Set nose LED to blue                |
| `-c nose -co red`      | Set nose LED to red                 |
| `-c nose -co green`    | Set nose LED to green               |
| `-c nose -co none`     | Turn nose LED off                   |
| `-c move_rel -x 1 -a N`| Rotate tilt servo by N degrees      |
| `-c move_rel -x 2 -a N`| Rotate pan servo by N degrees       |
| `REC_30`               | Record a 30-second H.264 video clip |

> **Note:** `-c nose -co none` is also sent automatically every 5 seconds by the
> React app as a BLE keepalive heartbeat. This is expected behaviour.
