import { ModeStatusCard } from '../components/status/ModeStatusCard';
import { RobotHealthCard } from '../components/status/RobotHealthCard';
import { RecentEventsCard } from '../components/status/RecentEventsCard';

export function DashboardPage() {
  return (
    <div className="grid grid-2">
      <div className="grid-column">
        <ModeStatusCard />
        <RobotHealthCard />
      </div>
      <div className="grid-column">
        <RecentEventsCard />
      </div>
    </div>
  );
}

