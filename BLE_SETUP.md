# QBO BLE Bridge Setup (Raspberry Pi 5)

This enables a BLE GATT server on the robot that receives commands and forwards them to:

`/opt/qbo/pipes/pipe_cmd`

The command string format is exactly the one accepted by `PiCmd.py` (for example `-c nose -co blue`).

## 1) Install dependencies

```bash
sudo apt update
sudo apt install -y bluetooth bluez python3-pip
sudo python3 -m pip install bless
```

## 2) Deploy script and service

If your project is at `~/QGCR/qbo_gitlab/QBO`:

```bash
sudo cp ~/QGCR/qbo_gitlab/QBO/BleCmdServer.py /opt/qbo/BleCmdServer.py
sudo chmod +x /opt/qbo/BleCmdServer.py
sudo cp ~/QGCR/qbo_gitlab/QBO/scripts/qbo-ble.service /etc/systemd/system/qbo-ble.service
```

## 3) Ensure PiCmd is running

```bash
sudo /opt/qbo/scripts/QBO_PiCmd.sh start
```

## 4) Enable and start BLE bridge

```bash
sudo systemctl daemon-reload
sudo systemctl enable qbo-ble.service
sudo systemctl start qbo-ble.service
```

## 5) Verify

```bash
sudo systemctl status qbo-ble.service
journalctl -u qbo-ble.service -f
```

You should see the BLE service advertising as `QBO-Command-Bridge`.

## Notes

- The React app must run in a secure context (`https://` or `http://localhost`).
- Use Chrome or Edge for best Web Bluetooth support.
- If your adapter is not `hci0`, edit `ExecStart` in `qbo-ble.service`.
