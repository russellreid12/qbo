import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { DashboardPage } from './pages/DashboardPage';
import { ModePage } from './pages/ModePage';
import { VideoPage } from './pages/VideoPage';
import { ControlPage } from './pages/ControlPage';
import { SongsPage } from './pages/SongsPage';
import { UsersPage } from './pages/UsersPage';
import { AlertsPage } from './pages/AlertsPage';

import { ClipsPage } from './pages/ClipsPage';

export type OperationalMode = 'guardian' | 'companion';

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/mode" element={<ModePage />} />
        <Route path="/video" element={<VideoPage />} />
        <Route path="/clips" element={<ClipsPage />} />
        <Route path="/control" element={<ControlPage />} />
        <Route path="/songs" element={<SongsPage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppLayout>
  );
}

