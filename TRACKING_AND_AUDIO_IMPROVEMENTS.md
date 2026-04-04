# Facial Tracking & Audio Improvements

> **Files changed:** `PiFaceFast.py`, `assistants/QboTalk.py`, `config.example.yml`

---

## Overview

Two areas were improved:

1. **Facial tracking** — the head now holds on faces more steadily, recovers gracefully from brief occlusions, and locks on/starts interacting faster.
2. **Audio listening** — the robot starts listening sooner by eliminating a ~1 s ambient-noise recalibration delay that was added before every utterance.

---

## Facial Tracking (`PiFaceFast.py`)

### Problems Fixed

| Symptom | Root cause |
|---|---|
| Head twitches / oscillates on a face | EMA alpha `0.85` was too high — chased every bbox jitter frame-by-frame |
| Robot looks away briefly then snaps back | `face_not_found_idx` threshold was only 5 frames — transient occlusions immediately dropped tracking |
| Long pause before robot engages | `track_lock_threshold_sec = 2.0` — needed 2 seconds centred before any interaction |
| Head snaps home abruptly when face lost | No gradual return — jumped to home position instantly |
| Tracking jitters after a servo move | `_stabilize_sec = 0.35` wait was longer than needed |

### Changes Made

| Parameter | Before | After | Reason |
|---|---|---|---|
| `faceTrackingSmoothAlpha` default | `0.85` | `0.55` | Reduces jitter-chasing; head holds steadier on a stable face |
| `track_lock_threshold_sec` | `2.0 s` | `0.8 s` | Robot engages 1.2 s faster once face is centred |
| Miss frame tolerance | `> 5` frames | `> 10` frames | ~0.3–0.7 s grace period for blinks, hand waves, head turns |
| `faceTrackingStabilizeSec` default | `0.35 s` | `0.20 s` | Tracking resumes sooner after each servo move |
| Camera buffer drain | 2 grabs | 3 grabs | Gets the freshest frame, reducing detection lag |
| Interaction trigger interval | `2.0 s` | `1.5 s` | Robot starts listening 0.5 s faster on face detection |
| Main loop sleep | `0.033 s` (30 Hz) | `0.05 s` (20 Hz) | Gives the Pi more headroom for DNN inference |
| Home return behaviour | Instant snap | Gradual drift at speed 60 | Looks natural — no abrupt snap when no face found |
| Servo write guard | Always writes | Only writes if position changed | Reduces unnecessary serial bus traffic |

### How the State Machine Works (recap)

```
Camera frame
     │
     ▼
[SEARCHING] ──face detected──► [DETECTING] ──centred ≥ 0.8 s──► [LOCKED]
    ▲                               │                                │
    │          face lost            │         face drifts off-centre │
    └───────── (10 missed frames) ──┘◄───────────────────────────────┘
```

- **SEARCHING** — nose off, head slowly drifts back toward home
- **DETECTING** — nose green, PID tracking active, waiting for centring
- **LOCKED** — nose blue, voice recording active, interaction triggered

---

## Audio Listening (`assistants/QboTalk.py`)

### Problem Fixed

`StartBack()` (called every time a face is seen) was running `adjust_for_ambient_noise()` before each listening session. This call blocks for ~0.5–1 s, adding noticeable lag between the robot seeing a face and actually starting to listen.

### Changes Made

| Change | Effect |
|---|---|
| **Ambient noise calibration cached** with a 60 s TTL | ~1 s delay removed from every listening turn after the first |
| `adjust_for_ambient_noise(duration=0.5)` on first run | Initial calibration cut from ~1 s to 0.5 s |
| `phrase_time_limit` added to `listen_in_background()` | Capture stops after `SpeechToTextListeningTime` seconds — no more endless silence waits |

### Calibration Cache Logic

```python
# Only recalibrate if >60 s have passed since last calibration
if (now - self._last_calibration_time) > 60.0:
    self.r.adjust_for_ambient_noise(source, duration=0.5)
    self._last_calibration_time = now
else:
    # Skip — use existing energy_threshold; saves ~1s per turn
    pass
```

---

## Config Tuning (`config.example.yml`)

`SpeechToTextListeningTime` raised from `5` → `7` seconds to match the new `phrase_time_limit` cap.

New commented-out knobs added for face tracking (uncomment and adjust as needed):

```yaml
# faceTrackingSmoothAlpha: 0.55      # 0.0=very smooth, 1.0=raw jitter
# faceTrackingLockThreshold: 0.8     # seconds centred before locking on
# faceTrackingMissThreshold: 10      # missed frames before face considered lost
# faceTrackingStabilizeSec: 0.20     # seconds to pause tracking after a servo move
```

---

## Tuning Guide

If the head still looks away too often:
- **Lower** `faceTrackingSmoothAlpha` (e.g. `0.40`) for a smoother, slower follow
- **Raise** `faceTrackingMissThreshold` (e.g. `15`) for more occlusion tolerance

If the head is slow to find a face:
- **Raise** `faceTrackingSmoothAlpha` (e.g. `0.70`) for quicker initial acquisition
- **Lower** `faceTrackingStabilizeSec` (e.g. `0.10`)

If the robot starts talking before you're ready:
- **Raise** `faceTrackingLockThreshold` (e.g. `1.5`)

If audio recognition starts too slowly:
- Check `SpeechToTextListeningTime` — lower it (e.g. `5`) for shorter capture windows
