import { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';

type Props = {
  children: ReactNode;
};

export function AppLayout({ children }: Props) {
  return (
    <div className="app-root">
      <aside className="app-sidebar">
        <div className="app-logo">
          <span className="logo-dot" />
          <span className="logo-text">QGCR</span>
        </div>
        <nav className="app-nav">
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/mode">Mode</NavLink>
          <NavLink to="/video">Video</NavLink>
          <NavLink to="/control">Control</NavLink>
          <NavLink to="/songs">Songs</NavLink>
          <NavLink to="/users">Users</NavLink>
          <NavLink to="/alerts">Alerts</NavLink>
        </nav>
      </aside>
      <main className="app-main">
        <header className="app-header">
          <h1>Q.Bo Guardian &amp; Companion</h1>
          <p className="app-subtitle">
            Monitor, control, and configure your QGCR robot.
          </p>
        </header>
        <section className="app-content">{children}</section>
      </main>
    </div>
  );
}

