import { useMemo, useState } from 'react';
import { BleRobotClient, globalBleClient } from '../services/bleRobot';

const PRESET_COMMANDS = {
  forward: '-c move -x 2 -a 100',
  left: '-c move_rel -x 1 -a -50',
  right: '-c move_rel -x 1 -a 50',
  stop: '-c move -x 2 -a 0',
};

export function ControlPage() {
  const [status, setStatus] = useState(globalBleClient.isConnected() ? 'Connected' : 'Disconnected');
  const [error, setError] = useState('');
  const [customCommand, setCustomCommand] = useState('-c nose -co blue');

  const connect = async () => {
    setError('');
    try {
      await globalBleClient.connect();
      setStatus('Connected');
    } catch (connectError) {
      setStatus('Disconnected');
      setError((connectError as Error).message);
    }
  };

  const disconnect = async () => {
    await globalBleClient.disconnect();
    setStatus('Disconnected');
  };

  const send = async (command: string) => {
    setError('');
    try {
      await globalBleClient.sendCommand(command);
      setStatus(`Sent: ${command}`);
    } catch (sendError) {
      setError((sendError as Error).message);
    }
  };

  return (
    <div className="page">
      <h2>Robot Control</h2>
      <p className="page-description">
        Connect to the Raspberry Pi BLE server, then send QBO commands. Preset movement strings can be
        adjusted to match your robot mappings.
      </p>

      <div className="card control-actions">
        <div className="control-row">
          <button className="btn primary" onClick={connect} disabled={!BleRobotClient.isSupported()}>
            Connect BLE
          </button>
          <button className="btn ghost" onClick={disconnect}>
            Disconnect
          </button>
        </div>
        <p className="hint">Status: {status}</p>
        {!BleRobotClient.isSupported() ? (
          <p className="hint control-error">Web Bluetooth not supported in this browser.</p>
        ) : null}
        {error ? <p className="hint control-error">Error: {error}</p> : null}
      </div>

      <div className="card control-grid">
        <button className="btn primary" onClick={() => send(PRESET_COMMANDS.forward)}>
          Forward
        </button>
        <div className="control-row">
          <button className="btn secondary" onClick={() => send(PRESET_COMMANDS.left)}>
            Turn Left
          </button>
          <button className="btn secondary" onClick={() => send(PRESET_COMMANDS.right)}>
            Turn Right
          </button>
        </div>
        <button className="btn danger" onClick={() => send(PRESET_COMMANDS.stop)}>
          Stop
        </button>
      </div>

      <div className="card">
        <h3>Custom QBO Command</h3>
        <div className="form-row">
          <input
            type="text"
            value={customCommand}
            onChange={(event) => setCustomCommand(event.target.value)}
            placeholder="-c nose -co red"
          />
          <button className="btn secondary" onClick={() => send(customCommand)}>
            Send
          </button>
        </div>
        <p className="hint">
          Use the same command format accepted by `PiCmd.py` (example: <code>-c nose -co green</code>).
        </p>
      </div>
    </div>
  );
}

