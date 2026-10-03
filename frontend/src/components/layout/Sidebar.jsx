import { NavLink, Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  Briefcase,
  Users,
  Bot,
  BarChart3,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Calendar,
  ClipboardList,
  Shield,
  FileText,
  Crown,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { isStaffAdmin, isSuperAdmin } from '../../utils/roles';
import { companyDisplayName, companyLogoSrc } from '../../utils/companyBranding';

const HR_NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/hr-review', label: 'HR Review', icon: ClipboardList },
  { to: '/jobs', label: 'Jobs', icon: Briefcase },
  { to: '/candidates', label: 'Candidates', icon: Users },
  { to: '/screening', label: 'AI Screening', icon: Bot },
  { to: '/calendar', label: 'Calendar', icon: Calendar },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
];

const ADMIN_NAV = [
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const { sidebarCollapsed, setSidebarCollapsed, workingCompany } = useApp();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const navItems = [
    ...HR_NAV,
    ...(isStaffAdmin(user?.role)
      ? [...ADMIN_NAV, { to: '/admin/users', label: 'Users', icon: Shield }]
      : []),
    ...(isSuperAdmin(user?.role)
      ? [
          { to: '/audit', label: 'Audit Log', icon: FileText },
          { to: '/superadmin', label: 'SuperAdmin', icon: Crown },
        ]
      : []),
  ];

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const companyName =
    companyDisplayName(workingCompany || user?.company) ||
    (isSuperAdmin(user?.role) ? 'Select company' : 'Recruitment');
  const companyLogo = companyLogoSrc(workingCompany || user?.company);

  return (
    <motion.aside
      animate={{ width: sidebarCollapsed ? 72 : 240 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="sidebar-bg h-screen flex flex-col fixed left-0 top-0 z-30 overflow-hidden border-r border-slate-800"
    >
      <Link
        to="/"
        title="Dashboard"
        className="flex items-center gap-3 px-4 h-16 bg-white border-b border-slate-200 flex-shrink-0 hover:bg-slate-50 transition-colors"
      >
        <img src={companyLogo} alt={companyName} className="h-8 w-auto flex-shrink-0 object-contain" />
        <AnimatePresence>
          {!sidebarCollapsed && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.15 }}
            >
              <p className="text-slate-900 font-semibold text-sm leading-tight">{companyName}</p>
              <p className="text-slate-500 text-xs">Recruitment System</p>
            </motion.div>
          )}
        </AnimatePresence>
      </Link>

      <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 group
              ${isActive
                ? 'nav-active'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'}`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={18} className={`flex-shrink-0 transition-transform group-hover:scale-110 ${isActive ? 'text-white' : ''}`} />
                <AnimatePresence>
                  {!sidebarCollapsed && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.1 }}
                      className="whitespace-nowrap"
                    >
                      {label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="px-2 pb-4 space-y-1 border-t border-slate-800 pt-3">
        <button
          type="button"
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:bg-red-900/30 hover:text-red-400 transition-all w-full"
        >
          <LogOut size={18} className="flex-shrink-0" />
          <AnimatePresence>
            {!sidebarCollapsed && (
              <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.1 }}>
                Logout
              </motion.span>
            )}
          </AnimatePresence>
        </button>

        <button
          type="button"
          onClick={() => setSidebarCollapsed((c) => !c)}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-500 hover:bg-slate-800 hover:text-slate-300 transition-all w-full"
        >
          {sidebarCollapsed ? <ChevronRight size={18} className="flex-shrink-0" /> : <ChevronLeft size={18} className="flex-shrink-0" />}
          <AnimatePresence>
            {!sidebarCollapsed && (
              <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.1 }}>
                Collapse
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>
    </motion.aside>
  );
}
