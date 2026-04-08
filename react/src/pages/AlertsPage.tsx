export function AlertsPage() {
  return (
    <div className="page">
      <h2>Alerts &amp; Events</h2>
      <p className="page-description">
        View fall alerts and event history as described in UC-002 and FR-6/FR-10.
      </p>
      <div className="card">
        <ul className="list">
          <li className="list-item">
            <span>Fall Detected for Alice</span>
            <span className="pill pill-danger">Critical</span>
          </li>
          <li className="list-item">
            <span>Unfamiliar user identified (Jon)</span>
            <span className="pill pill-warning">Attention</span>
          </li>
        </ul>
      </div>
    </div>
  );
}

