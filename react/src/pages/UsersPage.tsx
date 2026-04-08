export function UsersPage() {
  return (
    <div className="page">
      <h2>Authorized Users</h2>
      <p className="page-description">
        Manage known faces and users as described in the unfamiliar user story and FR-1/FR-11.
      </p>
      <div className="card">
        <form className="form-row">
          <input type="text" placeholder="Full name (e.g., Alice)" />
          <input type="text" placeholder="Relationship (e.g., Caregiver)" />
          <button type="submit" className="btn primary">
            Add User
          </button>
        </form>
        <ul className="list">
          <li className="list-item">
            <span>Alice (Primary User)</span>
          </li>
          <li className="list-item">
            <span>Emily (Caregiver)</span>
          </li>
        </ul>
      </div>
    </div>
  );
}

