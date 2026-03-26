# QBO Directory Overview

This repository contains software for the **QBO robot** (targeted at Raspberry Pi). It includes:

- A **Django-based Web Panel** (HTTP server, typically on port 8000)
- A **C WebSocket server** (typically on port 51717) used for real-time control/telemetry (e.g., Scratch integration)
- Robot-control Python entrypoints (speech, listening, motors/servos, vision, etc.)
- Helper scripts, model assets, and documentation

---

## Top-level files (key entrypoints)

- **`README.md`**: Installation and usage overview (including web panel URL and installer instructions).
- **`Start.py`**: Boot entrypoint used on the robot (triggered by installer crontab). Chooses a startup mode based on `/opt/qbo/config.yml` (e.g., Scratch mode vs interactive).
- **`Stop.py`**: Stop/shutdown helper (repo-specific).
- **`Say.py`, `Speak.py`**: Text-to-speech / audio output helpers.
- **`Listen.py`, `ListenBackground.py`**: Audio capture / speech listening helpers.
- **`PiCmd.py`, `PiCmdLine.py`**: Command/control utilities.
- **`PiFace.py`, `PiFaceFast.py`, `PiFace_imgFile.py`**: Vision/face-related scripts (likely using OpenCV cascades).
- **`FindFace.py`**: Face-finding logic / orchestration.
- **`Feel.py`**: Sensor/“feel” logic (touch/proximity/etc., depending on hardware setup).
- **`ServoConfig.py`**, **`RTQR.py`**, **`VisualRecognition.py`**, **`ListAndSay.py`**: Feature-specific scripts and utilities.
- **`.asoundrc`**: ALSA audio configuration (device routing for sound I/O).

---

## Directories

### `web/` — Django web panel (HTTP UI)

The Django project that powers the QBO web UI.

- **`web/manage.py`**: Django management entrypoint.
- **`web/qbo/`**: Django project config (settings, urls, wsgi).
- **`web/panel/`**: Main Django app for the web panel (views, static assets, serializers, tests).

Typical activation (installed robot): started on boot via crontab as `python /opt/qbo/web/manage.py runserver 0.0.0.0:8000`.

---

### `websocket/` — C WebSocket server (real-time bridge)

The WebSocket server used for real-time communication (not the Django server).

- **`websocket/WebsocketServer.c`**: Implements the WebSocket server and bridges messages to other robot processes via named pipes (FIFOs under `/opt/qbo/pipes/`).
- **`websocket/Makefile`**: Build instructions for the WebSocket binary.

Typically started by scripts (especially in Scratch mode) rather than by Django.

---

### `scripts/` — install + run/stop helpers

Shell scripts used for installation, configuration, and starting/stopping processes.

- **`scripts/QBO_Installer.sh`**: Main installer. Compiles components, sets hostname, sets up crontab, etc.
- **`scripts/QBO_Server.sh`**: Start/stop the WebSocket server binary.
- **`scripts/QBO_Scratch.sh`**: Starts/stops a full “Scratch mode” stack (WebSocket server + multiple Python processes).
- **`scripts/QBO_*.sh`**: Per-feature launchers (listen/say/feel/findface/pifacefast/picmd, etc.).
- **WiFi scripts**: `WiFiAdd.sh`, `WiFiSearchQR.sh` for WiFi provisioning/management.
- **`UpdateMyCroft.sh`**, `EnableSourceMyCroft.sh`: Mycroft-related setup/update helpers.

---

### `assistants/` — voice assistant integrations

Adapters/integrations for different assistant backends:

- **`QboMyCroft.py` / `QboTalkMycroft.py`**: Mycroft integration pieces.
- **`QboWatson.py`**: IBM Watson integration.
- **`QboGAssistant.py`**: Google Assistant integration.
- **`QboDialogFlowV2.py`**: Dialogflow V2 integration.
- **`QboTalk.py`**: Common “talk”/speech interaction layer.

---

### `controller/` — robot control abstraction

Core control code for interacting with robot hardware.

- **`controller/QboController.py`**: The main controller module (motors/servos/sensors orchestration, depending on implementation).

---

### `manuals/` — setup documentation

Markdown guides for configuring optional features and integrations:

- Google Assistant, IBM Watson, Mycroft, DialogflowV2, TensorFlow triggers, Visual Recognition, etc.

---

### `scratch/` — Scratch example projects

Scratch `.sbx` project files/demos for controlling the robot through Scratch.

---

### `sounds/` — audio assets

Wave files used for UI/feedback sounds (e.g., “blip” sounds).

---

### `haarcascades/` — OpenCV Haar cascade models

Face detection cascade XML files used by vision scripts (`PiFace*.py`, `FindFace.py`, etc.).

---

### `tfvrmodel/` — TensorFlow visual recognition model

TensorFlow model artifacts (e.g., `.pb` graph definition and label maps) used by visual recognition features.

---

### `voicemodels/` — hotword/voice model assets

Voice/hotword detection model files (e.g., `Hi_QBO.pmdl`).

---

## Related docs

- **Web server activation**: see `WEB_SERVER_ACTIVATION.md` (Django web panel + WebSocket server startup paths).

