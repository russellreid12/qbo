import { useState, useEffect, useRef } from 'react';
import { globalBleClient, ClipInfo } from '../services/bleRobot';

interface ClipState {
  status: 'idle' | 'downloading' | 'ready' | 'error';
  progress: number;
  blobUrl: string | null;
  errorMsg: string | null;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatEta(receivedPct: number, elapsedMs: number): string {
  if (receivedPct <= 0) return '—';
  const totalMs = (elapsedMs / receivedPct) * 100;
  const remaining = Math.round((totalMs - elapsedMs) / 1000);
  if (remaining < 60) return `~${remaining}s`;
  return `~${Math.ceil(remaining / 60)}m`;
}

export function ClipsPage() {
  const [clips, setClips] = useState<ClipInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [clipStates, setClipStates] = useState<Record<string, ClipState>>({});
  const downloadStartTimes = useRef<Record<string, number>>({});

  const isConnected = globalBleClient.isConnected();

  const fetchClips = async () => {
    if (!isConnected) {
      setListError('Connect to the robot via BLE first.');
      return;
    }
    if (!globalBleClient.hasDataChannel()) {
      setListError('DATA channel not available — restart BleCmdServer.py on the robot.');
      return;
    }
    setIsLoading(true);
    setListError(null);
    try {
      const result = await globalBleClient.listClips();
      setClips(result);
      // Initialise state for any new clips
      setClipStates(prev => {
        const next = { ...prev };
        for (const clip of result) {
          if (!next[clip.name]) {
            next[clip.name] = { status: 'idle', progress: 0, blobUrl: null, errorMsg: null };
          }
        }
        return next;
      });
    } catch (err: any) {
      setListError(err.message ?? 'Failed to fetch clip list');
    } finally {
      setIsLoading(false);
    }
  };

  // Auto-load when page mounts if already connected
  useEffect(() => {
    if (isConnected) fetchClips();
    // Revoke blob URLs on unmount to free memory
    return () => {
      Object.values(clipStates).forEach(s => {
        if (s.blobUrl) URL.revokeObjectURL(s.blobUrl);
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDownload = async (clip: ClipInfo) => {
    setClipStates(prev => ({
      ...prev,
      [clip.name]: { status: 'downloading', progress: 0, blobUrl: null, errorMsg: null },
    }));
    downloadStartTimes.current[clip.name] = Date.now();

    try {
      const blob = await globalBleClient.downloadClip(clip.name, clip.size, (pct) => {
        setClipStates(prev => ({
          ...prev,
          [clip.name]: { ...prev[clip.name], progress: pct },
        }));
      });
      const url = URL.createObjectURL(blob);
      setClipStates(prev => ({
        ...prev,
        [clip.name]: { status: 'ready', progress: 100, blobUrl: url, errorMsg: null },
      }));
    } catch (err: any) {
      setClipStates(prev => ({
        ...prev,
        [clip.name]: { status: 'error', progress: 0, blobUrl: null, errorMsg: err.message },
      }));
    }
  };

  return (
    <div className="page">
      <div className="app-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Recorded Clips</h1>
          <p className="app-subtitle">10-second clips streamed directly from the robot via BLE.</p>
        </div>
        <button className="btn secondary" onClick={fetchClips} disabled={isLoading || !isConnected}>
          {isLoading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      <div className="app-content">
        {!isConnected && (
          <div className="card" style={{ borderColor: 'var(--warning)', background: 'rgba(245,158,11,0.05)' }}>
            <p className="hint" style={{ color: 'var(--warning)' }}>
              ⚠️ Not connected to robot. Go to the Dashboard and connect via BLE first.
            </p>
          </div>
        )}

        {listError && (
          <div className="card" style={{ borderColor: 'var(--danger)', background: 'rgba(239,68,68,0.05)' }}>
            <p className="hint" style={{ color: 'var(--danger)' }}>{listError}</p>
          </div>
        )}

        {isConnected && clips.length === 0 && !isLoading && !listError && (
          <div className="card" style={{ textAlign: 'center', padding: '40px' }}>
            <p className="muted">No clips recorded yet. Use the Record button on the Dashboard!</p>
          </div>
        )}

        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
          {clips.map((clip) => {
            const state = clipStates[clip.name] ?? { status: 'idle', progress: 0, blobUrl: null, errorMsg: null };
            const elapsed = downloadStartTimes.current[clip.name]
              ? Date.now() - downloadStartTimes.current[clip.name]
              : 0;

            return (
              <div key={clip.name} className="card clip-card">
                <div style={{ marginBottom: '12px' }}>
                  <h3 style={{ margin: 0, fontSize: '14px' }}>{clip.name}</h3>
                  <span className="hint">{formatSize(clip.size)}</span>
                </div>

                {/* Video player — shown only after download */}
                {state.status === 'ready' && state.blobUrl && (
                  <video
                    src={state.blobUrl}
                    controls
                    autoPlay
                    width="100%"
                    style={{ borderRadius: 'var(--radius-md)', background: '#000', marginBottom: '10px' }}
                  />
                )}

                {/* Progress bar */}
                {state.status === 'downloading' && (
                  <div style={{ marginBottom: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span className="hint">Downloading via BLE…</span>
                      <span className="hint">{state.progress}% · ETA {formatEta(state.progress, elapsed)}</span>
                    </div>
                    <div style={{
                      height: '6px', borderRadius: '3px',
                      background: 'var(--surface-raised)',
                      overflow: 'hidden',
                    }}>
                      <div style={{
                        height: '100%',
                        width: `${state.progress}%`,
                        background: 'var(--primary)',
                        transition: 'width 0.3s ease',
                        borderRadius: '3px',
                      }} />
                    </div>
                  </div>
                )}

                {/* Error */}
                {state.status === 'error' && (
                  <p className="hint" style={{ color: 'var(--danger)', marginBottom: '8px' }}>
                    ⚠️ {state.errorMsg}
                  </p>
                )}

                {/* Action button */}
                {state.status !== 'ready' && (
                  <button
                    className="btn primary"
                    style={{ width: '100%' }}
                    disabled={state.status === 'downloading'}
                    onClick={() => handleDownload(clip)}
                  >
                    {state.status === 'downloading'
                      ? `Downloading ${state.progress}%…`
                      : state.status === 'error'
                        ? 'Retry Download'
                        : 'Download via BLE'}
                  </button>
                )}

                {state.status === 'ready' && (
                  <button
                    className="btn secondary"
                    style={{ width: '100%', marginTop: '8px' }}
                    onClick={() => handleDownload(clip)}
                  >
                    Re-download
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
