# How to Activate the QBO Web Server

This document explains how the web-related components in the QBO project are activated.

---

## Overview

There are **two separate web-related components** in this codebase:

1. **Django Web Panel** – HTTP web server on port **8000** (main web UI)
2. **WebSocket Server** – libwebsockets server on port **51717** (real-time robot communication for Scratch control, etc.)

---

## 1. Django Web Panel (Port 8000)

The main web UI is a Django application located in the `web/` directory.

### Automatic Activation (Production Setup)

When the QBO software is installed via `QBO_Installer.sh`, the installer adds a crontab entry that starts the web server automatically on every reboot:

```bash
@reboot qbo python /opt/qbo/web/manage.py runserver 0.0.0.0:8000
```

The `0.0.0.0:8000` binding means the server listens on all network interfaces, making it accessible from other devices on the local network (e.g., `http://qbo.local:8000/`).

### Manual Activation

To start the web panel manually (for development or testing), run:

```bash
python web/manage.py runserver 0.0.0.0:8000
```

From the project root directory:

```bash
cd /path/to/QBO
python web/manage.py runserver 0.0.0.0:8000
```

Or, if the software is installed in the standard location:

```bash
python /opt/qbo/web/manage.py runserver 0.0.0.0:8000
```

Then open your browser to `http://qbo.local:8000/` or `http://localhost:8000/` (depending on your network setup).

---

## 2. WebSocket Server (Port 51717)

The WebSocket server is a C program built from `websocket/WebsocketServer.c`. It handles real-time bidirectional communication (e.g., for Scratch-based robot control) and relays data via named pipes (FIFOs) to other QBO components.

### How It Gets Activated

The WebSocket server is **not** started automatically at boot. It is started when:

1. **Scratch mode** is enabled – When the config file (`/opt/qbo/config.yml`) has `startWith: scratch`, the `Start.py` script runs `QBO_Scratch.sh start`, which in turn calls `QBO_Server.sh start`.
2. **Manually** – You can run the script directly.

### Manual Activation

Start the WebSocket server with:

```bash
/opt/qbo/scripts/QBO_Server.sh start
```

Or, from the project root:

```bash
bash scripts/QBO_Server.sh start
```

The script checks if `WebsocketServer` is already running before starting it. The server listens on port **51717**.

To stop it:

```bash
/opt/qbo/scripts/QBO_Server.sh stop
```

### Running the Binary Directly

If the C program is already compiled and installed:

```bash
/opt/qbo/websocket/WebsocketServer
```

---

## Quick Reference

| Component | Port | Activation Command |
|-----------|------|--------------------|
| Django Web Panel | 8000 | `python web/manage.py runserver 0.0.0.0:8000` |
| WebSocket Server | 51717 | `scripts/QBO_Server.sh start` (or `QBO_Scratch.sh start`) |

---

## Notes

- **QBO_Server.sh** uses hardcoded paths to `/opt/qbo/`. For local development outside the standard install, you may need to modify those paths in the script.
- The Web Panel is started automatically on boot via crontab after a full QBO installation.
- The WebSocket server is only started automatically when the robot boots in Scratch mode.
