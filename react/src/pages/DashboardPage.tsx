import { useMemo } from 'react';
import { ModeStatusCard } from '../components/status/ModeStatusCard';
import { RobotHealthCard } from '../components/status/RobotHealthCard';
import { RecentEventsCard } from '../components/status/RecentEventsCard';
import { RecordButton } from '../components/video/RecordButton';
import { BleRobotClient, globalBleClient } from '../services/bleRobot';

export function DashboardPage() {
  const bleClient = globalBleClient;

  return (
    <div className="grid grid-2">
      <div className="grid-column">
        <div className="card">
          <h3>Quick Actions</h3>
          <RecordButton bleClient={bleClient} />
          {!bleClient.isConnected() && (
             <p className="hint" style={{ marginTop: '10px', color: 'var(--warning)', textAlign: 'center' }}>
               Note: BLE must be connected in the 'Control' tab to use this.
             </p>
          )}
        </div>
        <ModeStatusCard />
        <RobotHealthCard />
      </div>
      <div className="grid-column">
        <RecentEventsCard />
      </div>
    </div>
  );
}

