import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/layout/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';
import SuperAdminRoute from './components/SuperAdminRoute';
import JoinInterview from './pages/JoinInterview';
import Login from './pages/Login';
import ScheduleInterview from './pages/ScheduleInterview';
import HRCandidates from './pages/HRCandidates';
import HRCalendar from './pages/HRCalendar';
import HRAuditLog from './pages/HRAuditLog';
import AdminUsers from './pages/AdminUsers';
import Dashboard from './pages/dashboard/Dashboard';
import Jobs from './pages/dashboard/Jobs';
import Candidates from './pages/dashboard/Candidates';
import CandidateAgentsDashboard from './pages/dashboard/CandidateAgentsDashboard';
import Screening from './pages/dashboard/Screening';
import Reports from './pages/dashboard/Reports';
import Settings from './pages/dashboard/Settings';
import SuperAdmin from './pages/SuperAdmin';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/interview/hr/:token" element={<JoinInterview role="hr" />} />
      <Route path="/interview/:token" element={<JoinInterview />} />
      <Route path="/join/hr/:token" element={<JoinInterview role="hr" />} />
      <Route path="/join/:token" element={<JoinInterview />} />
      <Route path="/schedule/:token" element={<ScheduleInterview />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/jobs" element={<Jobs />} />
        <Route path="/candidates" element={<Candidates />} />
        <Route path="/candidates/:candidateId" element={<CandidateAgentsDashboard />} />
        <Route path="/screening" element={<Screening />} />
        <Route path="/reports" element={<Reports />} />
        <Route
          path="/settings"
          element={
            <AdminRoute>
              <Settings />
            </AdminRoute>
          }
        />
        <Route path="/hr-review" element={<HRCandidates />} />
        <Route path="/calendar" element={<HRCalendar />} />
        <Route
          path="/audit"
          element={
            <SuperAdminRoute>
              <HRAuditLog />
            </SuperAdminRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <AdminRoute>
              <AdminUsers />
            </AdminRoute>
          }
        />
        <Route
          path="/superadmin"
          element={
            <SuperAdminRoute>
              <SuperAdmin />
            </SuperAdminRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
