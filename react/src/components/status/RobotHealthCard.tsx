export function RobotHealthCard() {
  return (
    <div className="card">
      <h3>Robot Status</h3>
      <ul className="kv-list">
        <li>
          <span>Connectivity</span>
          <span className="pill pill-success">Online</span>
        </li>
        <li>
          <span>Temperature</span>
          <span>Nominal</span>
        </li>
        <li>
          <span>Last heartbeat</span>
          <span>Just now</span>
        </li>
      </ul>
    </div>
  );
}

