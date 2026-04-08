import { ModeToggle } from '../components/mode/ModeToggle';

export function ModePage() {
  return (
    <div className="page">
      <h2>Operational Mode</h2>
      <p className="page-description">
        Switch between <strong>Guardian</strong> and <strong>Companion</strong> modes as described in the
        design document. This does not yet call a backend API.
      </p>
      <ModeToggle />
    </div>
  );
}

