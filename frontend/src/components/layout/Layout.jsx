import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import Navbar from './Navbar';
import ToastContainer from '../ui/ToastContainer';
import LoadingSpinner from '../LoadingSpinner';
import { useApp } from '../../context/AppContext';

export default function Layout() {
  const { sidebarCollapsed, refreshData, workingCompanyId, workingCompany, loadingData } = useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const refreshDataRef = useRef(refreshData);
  const previousCompanyRef = useRef(workingCompanyId);
  refreshDataRef.current = refreshData;

  useEffect(() => {
    refreshDataRef.current({ silent: true });
  }, [location.pathname]);

  useEffect(() => {
    const previous = previousCompanyRef.current;
    previousCompanyRef.current = workingCompanyId;
    if (!previous || !workingCompanyId || previous === workingCompanyId) return;
    if (/^\/candidates\/[^/]+/.test(location.pathname)) {
      navigate('/candidates', { replace: true });
    }
  }, [workingCompanyId, location.pathname, navigate]);

  return (
    <div className="min-h-screen" style={{ background: 'var(--color-bg)' }}>
      <Sidebar />
      <div
        style={{
          marginLeft: sidebarCollapsed ? 72 : 240,
          transition: 'margin-left 0.3s cubic-bezier(0.4,0,0.2,1)',
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Navbar />
        <AnimatePresence mode="wait">
          <motion.main
            key={`${location.pathname}:${workingCompanyId || 'none'}`}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="flex-1 p-6"
          >
            {loadingData ? (
              <LoadingSpinner message={`Loading ${workingCompany?.name || 'company'}...`} />
            ) : (
              <Outlet />
            )}
          </motion.main>
        </AnimatePresence>
      </div>
      <ToastContainer />
    </div>
  );
}
