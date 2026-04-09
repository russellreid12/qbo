#!/usr/bin/env python3

import argparse
import asyncio
import errno
import logging
import os
from typing import Optional

from bless import BlessServer
from bless.backends.characteristic import GATTCharacteristicProperties

# kevincar/bless: older builds expose this on backends.service; newer versions re-export from bless.
try:
    from bless.backends.service import GATTAttributePermissions
except ImportError:
    from bless import GATTAttributePermissions

FIFO_CMD = "/opt/qbo/pipes/pipe_cmd"
SERVICE_UUID = "7f4b0001-0c56-4a58-9b20-52d2b4f35a01"
COMMAND_CHARACTERISTIC_UUID = "7f4b0002-0c56-4a58-9b20-52d2b4f35a01"
STATUS_CHARACTERISTIC_UUID = "7f4b0003-0c56-4a58-9b20-52d2b4f35a01"

logger = logging.getLogger("qbo_ble")
last_status = "idle"


def ensure_pipe(path: str) -> None:
    try:
        os.mkfifo(path)
    except OSError as error:
        if error.errno != errno.EEXIST:
            raise


def publish_to_qbo(command: str) -> None:
    ensure_pipe(FIFO_CMD)
    try:
        fd = os.open(FIFO_CMD, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd, (command + "\n").encode("utf-8"))
            logger.info("Command written to pipe: %s", command)
        finally:
            os.close(fd)
    except OSError as e:
        if e.errno == errno.ENXIO:
            logger.warning("pipe_cmd: no reader attached (PiFaceFast not running?), command dropped: %s", command)
        else:
            raise


def parse_payload(value: bytearray) -> str:
    text = bytes(value).decode("utf-8", errors="ignore").strip()
    if not text:
        raise ValueError("Command payload is empty.")
    return text


def read_status(_: int, **__) -> bytearray:
    return bytearray(last_status.encode("utf-8"))


def build_write_callback(server: BlessServer):
    def write_request(characteristic, value: bytearray, **kwargs):
        global last_status
        if str(characteristic.uuid).lower() != COMMAND_CHARACTERISTIC_UUID.lower():
            return

        try:
            command = parse_payload(value)
            logger.info("BLE command received: %s", command)
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
    server = BlessServer(name=name, adapter=adapter)
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

    server.read_request_func = read_status
    server.write_request_func = build_write_callback(server)

    await server.start()
    logger.info("BLE command server started as '%s'", name)
    logger.info("Service UUID: %s", SERVICE_UUID)
    logger.info("Command Characteristic UUID: %s", COMMAND_CHARACTERISTIC_UUID)

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
