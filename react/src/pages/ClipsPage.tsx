import { useState, useEffect } from 'react';

// The video server always runs on the robot. Use its hostname or IP.
// If QBo.local doesn't resolve on your network, replace with the robot's IP (e.g. 192.168.x.x)
const ROBOT_HOST = import.meta.env.VITE_ROBOT_HOST ?? 'QBo.local';
const API_BASE = `http://${ROBOT_HOST}:5000`;

export function ClipsPage() {
  const [clips, setClips] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchClips = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/clips`);
      if (!response.ok) throw new Error('Failed to fetch clip list');
      const data = await response.json();
      setClips(data);
    } catch (err) {
      console.error(err);
      setError('Could not connect to video server. Ensure video_server.py is running on port 5000.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchClips();
  }, []);

  return (
    <div className="page">
      <div className="app-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Recorded Clips</h1>
          <p className="app-subtitle">Archive of 30-second security and event recordings.</p>
        </div>
        <button className="btn secondary" onClick={fetchClips} disabled={isLoading}>
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="app-content">
        {error && (
          <div className="card" style={{ borderColor: 'var(--danger)', background: 'rgba(239, 68, 68, 0.05)' }}>
            <p className="hint" style={{ color: 'var(--danger)' }}>{error}</p>
          </div>
        )}

        {clips.length === 0 && !isLoading && !error && (
          <div className="card" style={{ textAlign: 'center', padding: '40px' }}>
            <p className="muted">No clips recorded yet. Use the Record button on the Dashboard!</p>
          </div>
        )}

        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
          {clips.map((filename) => (
            <div key={filename} className="card clip-card">
              <div style={{ marginBottom: '12px' }}>
                <h3 style={{ margin: 0, fontSize: '14px' }}>{filename}</h3>
                <span className="hint">{filename.split('_').slice(-2).join(' ').replace('.mp4', '')}</span>
              </div>
              <video 
                src={`${API_BASE}/clips/${filename}`} 
                controls 
                width="100%" 
                style={{ borderRadius: 'var(--radius-md)', background: '#000' }}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
