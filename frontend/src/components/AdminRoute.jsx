import { Navigate, useLocation } from 'react-router-dom';
import SessionSplash from './SessionSplash';
import { useAuth } from '../context/AuthContext';
import { isStaffAdmin } from '../utils/roles';

export default function AdminRoute({ children }) {
  const { user, isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <SessionSplash message="Loading…" />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (!isStaffAdmin(user?.role)) {
    return <Navigate to="/" replace />;
  }

  return children;
}
