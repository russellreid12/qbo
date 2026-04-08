export function RecentEventsCard() {
  return (
    <div className="card">
      <h3>Recent Events</h3>
      <ul className="list">
        <li className="list-item">
          <span>Fall detected for Alice</span>
          <span className="pill pill-danger">Critical</span>
        </li>
        <li className="list-item">
          <span>Mode switched to Guardian</span>
          <span className="pill pill-info">Info</span>
        </li>
        <li className="list-item">
          <span>Bohemian Rhapsody uploaded</span>
          <span className="pill pill-info">Media</span>
        </li>
      </ul>
    </div>
  );
}

