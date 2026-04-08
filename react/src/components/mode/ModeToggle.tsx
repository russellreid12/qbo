import { useState } from 'react';
import type { OperationalMode } from '../../App';

export function ModeToggle() {
  const [mode, setMode] = useState<OperationalMode>('companion');

  return (
    <div className="card mode-toggle">
      <div className="mode-options">
        <button
          type="button"
          className={`btn toggle ${mode === 'companion' ? 'active' : ''}`}
          onClick={() => setMode('companion')}
        >
          Companion
        </button>
        <button
          type="button"
          className={`btn toggle ${mode === 'guardian' ? 'active' : ''}`}
          onClick={() => setMode('guardian')}
        >
          Guardian
        </button>
      </div>
      <p className="mode-description">
        Current mode: <strong>{mode === 'guardian' ? 'Guardian (surveillance)' : 'Companion (interactive)'}</strong>
      </p>
      <p className="hint">
        In the full system, changing mode would notify QGCR over Wi-Fi/BLE and be logged in the app.
      </p>
    </div>
  );
}

