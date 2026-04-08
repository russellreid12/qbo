export function SongsPage() {
  return (
    <div className="page">
      <h2>Songs &amp; Media</h2>
      <p className="page-description">
        Manage songs that QGCR can play in Companion mode (FR-2, FR-11). This prototype keeps all data
        client-side.
      </p>
      <div className="card">
        <form className="form-row">
          <input type="text" placeholder="Song name (e.g., Bohemian Rhapsody)" />
          <button type="submit" className="btn primary">
            Add Song
          </button>
        </form>
        <ul className="list">
          <li className="list-item">
            <span>Bohemian Rhapsody</span>
            <button className="btn ghost">Play</button>
          </li>
        </ul>
      </div>
    </div>
  );
}

