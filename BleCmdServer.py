#!/usr/bin/env python3

import argparse
import asyncio
import errno
import glob
import json
import logging
import os
import threading
from typing import Optional

from bless import BlessServer
from bless.backends.characteristic import GATTCharacteristicProperties

# kevincar/bless: older builds expose this on backends.service; newer versions re-export from bless.
try:
    from bless.backends.service import GATTAttributePermissions
except ImportError:
    from bless import GATTAttributePermissions

FIFO_CMD = "/opt/qbo/pipes/pipe_cmd"
CLIP_DIR = "/opt/qbo/recordings"
CHUNK_SIZE = 490  # Safe BLE payload: 512 - 4 byte header - overhead

SERVICE_UUID = "7f4b0001-0c56-4a58-9b20-52d2b4f35a01"
COMMAND_CHARACTERISTIC_UUID = "7f4b0002-0c56-4a58-9b20-52d2b4f35a01"
STATUS_CHARACTERISTIC_UUID = "7f4b0003-0c56-4a58-9b20-52d2b4f35a01"
DATA_CHARACTERISTIC_UUID = "7f4b0004-0c56-4a58-9b20-52d2b4f35a01"

logger = logging.getLogger("qbo_ble")
last_status = "idle"

# Global references set inside run() so sync callbacks can schedule async tasks
_event_loop: Optional[asyncio.AbstractEventLoop] = None
_ble_server: Optional[BlessServer] = None


def ensure_pipe(path: str) -> None:
    try:
        os.mkfifo(path)
    except OSError as error:
        if error.errno != errno.EEXIST:
            raise


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


def parse_payload(value: bytearray) -> str:
    text = bytes(value).decode("utf-8", errors="ignore").strip()
    if not text:
        raise ValueError("Command payload is empty.")
    return text


def read_status(_: int, **__) -> bytearray:
    return bytearray(last_status.encode("utf-8"))


async def _notify_data(data: bytearray) -> None:
    """Push data to the DATA characteristic and trigger a BLE notification."""
    if _ble_server is None:
        return
    char = _ble_server.get_characteristic(DATA_CHARACTERISTIC_UUID)
    if char is None:
        logger.warning("DATA characteristic not found — cannot notify")
        return
    char.value = data
    _ble_server.update_value(SERVICE_UUID, DATA_CHARACTERISTIC_UUID)
    # Yield briefly so the BLE stack can flush the notification
    await asyncio.sleep(0.01)


async def _list_clips_async() -> None:
    """Scan recordings dir and send clip metadata as a JSON notification."""
    os.makedirs(CLIP_DIR, exist_ok=True)
    files = sorted(
        glob.glob(os.path.join(CLIP_DIR, "*.mp4")),
        key=os.path.getmtime,
        reverse=True,
    )[:5]  # Limit to 5 clips so JSON string fits inside 512-byte BLE MTU limit
    info = [{"name": os.path.basename(f), "size": os.path.getsize(f)} for f in files]
    payload = ("LIST:" + json.dumps(info)).encode("utf-8")
    
    # If it's still too large, fallback to a simpler structure or just 1 clip
    if len(payload) > 500:
        files = files[:2]
        info = [{"name": os.path.basename(f), "size": os.path.getsize(f)} for f in files]
        payload = ("LIST:" + json.dumps(info)).encode("utf-8")
        
    await _notify_data(bytearray(payload))
    logger.info("Clip list sent: %d clips", len(info))


async def _stream_clip_async(filename: str) -> None:
    """Stream a video file to the React app as chunked BLE notifications."""
    # Sanitize to prevent directory traversal
    filename = os.path.basename(filename)
    path = os.path.join(CLIP_DIR, filename)

    if not os.path.isfile(path):
        err = f"CLIP_ERR:File not found: {filename}".encode("utf-8")
        await _notify_data(bytearray(err))
        return

    file_size = os.path.getsize(path)
    logger.info("Streaming clip %s (%d bytes)", filename, file_size)

    seq = 0
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                # 4-byte big-endian sequence number prefix
                header = seq.to_bytes(4, "big")
                await _notify_data(bytearray(header + chunk))
                seq += 1
                # Small delay so BLE stack isn't overwhelmed
                await asyncio.sleep(0.015)
    except Exception as e:
        logger.exception("Error streaming clip %s", filename)
        await _notify_data(bytearray(f"CLIP_ERR:{e}".encode("utf-8")))
        return

    await _notify_data(bytearray(b"CLIP_END"))
    logger.info("Clip stream complete: %s (%d chunks)", filename, seq)


def build_write_callback(server: BlessServer):
    def write_request(characteristic, value: bytearray, **kwargs):
        global last_status
        if str(characteristic.uuid).lower() != COMMAND_CHARACTERISTIC_UUID.lower():
            return

        try:
            command = parse_payload(value)
            logger.info("BLE command received: %s", command)

            if command == "LIST_CLIPS":
                if _event_loop:
                    asyncio.run_coroutine_threadsafe(_list_clips_async(), _event_loop)
                last_status = "ok:LIST_CLIPS"

            elif command.startswith("GET_CLIP:"):
                filename = command[len("GET_CLIP:"):]
                if _event_loop:
                    asyncio.run_coroutine_threadsafe(_stream_clip_async(filename), _event_loop)
                last_status = f"ok:streaming:{filename}"

            else:
                # Regular robot command — forward to pipe
                publish_to_qbo(command)
                last_status = f"ok:{command}"

        except Exception as error:
            logger.exception("Failed to process BLE command")
            last_status = f"error:{error}"
        finally:
            status_char = server.get_characteristic(STATUS_CHARACTERISTIC_UUID)
            if status_char is not None:
                status_char.value = bytearray(last_status.encode("utf-8"))

    return write_request


async def run(adapter: Optional[str], name: str) -> None:
    global _event_loop, _ble_server
    _event_loop = asyncio.get_running_loop()

    server = BlessServer(name=name, adapter=adapter)
    _ble_server = server

    await server.add_new_service(SERVICE_UUID)

    await server.add_new_characteristic(
        SERVICE_UUID,
        COMMAND_CHARACTERISTIC_UUID,
        GATTCharacteristicProperties.write,
        None,
        GATTAttributePermissions.writeable,
    )
    await server.add_new_characteristic(
        SERVICE_UUID,
        STATUS_CHARACTERISTIC_UUID,
        GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
        bytearray(last_status.encode("utf-8")),
        GATTAttributePermissions.readable,
    )
    await server.add_new_characteristic(
        SERVICE_UUID,
        DATA_CHARACTERISTIC_UUID,
        GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
        bytearray(b""),
        GATTAttributePermissions.readable,
    )

    server.read_request_func = read_status
    server.write_request_func = build_write_callback(server)

    await server.start()
    logger.info("BLE command server started as '%s'", name)
    logger.info("Service UUID      : %s", SERVICE_UUID)
    logger.info("Command Char UUID : %s", COMMAND_CHARACTERISTIC_UUID)
    logger.info("Data Char UUID    : %s", DATA_CHARACTERISTIC_UUID)

    try:
        while True:
            await asyncio.sleep(1.0)
    finally:
        await server.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="QBO BLE command bridge to /opt/qbo/pipes/pipe_cmd")
    parser.add_argument("--adapter", default=None, help="BlueZ adapter (example: hci0)")
    parser.add_argument("--name", default="QBO-Command-Bridge", help="BLE peripheral name")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(run(adapter=args.adapter, name=args.name))


if __name__ == "__main__":
    main()
