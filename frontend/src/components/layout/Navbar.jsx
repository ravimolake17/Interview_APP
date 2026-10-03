import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Bell, Sun, Moon, ChevronDown, Users, Briefcase, X } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { isStaffAdmin } from '../../utils/roles';
import { filterCandidates, filterJobs, normalizeQuery } from '../../utils/search';
import CompanySwitcher from './CompanySwitcher';

const PAGE_TITLES = {
  '/': 'Dashboard',
  '/jobs': 'Jobs',
  '/candidates': 'Candidates',
  '/screening': 'AI Screening',
  '/reports': 'Reports',
  '/settings': 'Settings',
  '/hr-review': 'HR Candidate Review',
  '/calendar': 'HR Calendar',
  '/audit': 'Audit Log',
  '/admin/users': 'User Management',
  '/superadmin': 'SuperAdmin',
};


export default function Navbar() {
  const { darkMode, toggleDark, candidates, jobs, notifications, dismissNotification, clearAllNotifications } = useApp();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const searchWrapRef = useRef(null);
  const notifWrapRef = useRef(null);
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);

  const title = PAGE_TITLES[location.pathname] || user?.company?.name || 'Recruitment';
  const unreadCount = notifications.length;
  const initials = (user?.full_name || 'HR')
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const q = params.get('q') || '';
    if (location.pathname === '/candidates' || location.pathname === '/jobs') {
      setSearch(q);
    }
  }, [location.pathname, location.search]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchWrapRef.current && !searchWrapRef.current.contains(event.target)) {
        setSearchOpen(false);
      }
      if (notifWrapRef.current && !notifWrapRef.current.contains(event.target)) {
        setNotifOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const searchResults = useMemo(() => {
    const q = normalizeQuery(search);
    if (!q) return { candidates: [], jobs: [] };
    return {
      candidates: filterCandidates(candidates, q).slice(0, 5),
      jobs: filterJobs(jobs, q).slice(0, 5),
    };
  }, [search, candidates, jobs]);

  const hasResults = searchResults.candidates.length > 0 || searchResults.jobs.length > 0;
  const showDropdown = searchOpen && normalizeQuery(search).length > 0;

  const goToSearch = (path, query) => {
    const q = normalizeQuery(query);
    navigate(q ? `${path}?q=${encodeURIComponent(q)}` : path);
    setSearchOpen(false);
    setNotifOpen(false);
    setProfileOpen(false);
  };

  const handleSearchSubmit = (event) => {
    event.preventDefault();
    const q = normalizeQuery(search);
    if (!q) return;
    if (searchResults.candidates.length > 0) {
      goToSearch('/candidates', q);
      return;
    }
    if (searchResults.jobs.length > 0) {
      goToSearch('/jobs', q);
      return;
    }
    goToSearch('/candidates', q);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const handleNotificationClick = (notification) => {
    dismissNotification(notification.id);
    setNotifOpen(false);
    setSearchOpen(false);
    setProfileOpen(false);
    navigate(notification.route);
  };

  const handleDismissNotification = (event, notificationId) => {
    event.preventDefault();
    event.stopPropagation();
    dismissNotification(notificationId);
  };

  const handleClearAllNotifications = () => {
    clearAllNotifications(notifications.map((n) => n.id));
  };

  return (
    <header className="h-16 surface-bg border-b border-col flex items-center justify-between px-6 sticky top-0 z-20">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-col">{title}</h1>
      </div>

      <div className="flex items-center gap-3">
        <div ref={searchWrapRef} className="relative hidden md:block">
          <form onSubmit={handleSearchSubmit}>
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
            <input
              type="text"
              placeholder="Search candidates, jobs…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setSearchOpen(true);
              }}
              onFocus={() => setSearchOpen(true)}
              className="pl-9 pr-4 py-2 text-sm rounded-xl border border-col bg-transparent text-col placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 w-56 transition-all focus:w-72"
              aria-label="Search candidates and jobs"
              aria-expanded={showDropdown}
              aria-controls="global-search-results"
            />
          </form>

          <AnimatePresence>
            {showDropdown && (
              <motion.div
                id="global-search-results"
                initial={{ opacity: 0, y: 8, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.98 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 top-12 w-80 card z-50 overflow-hidden max-h-96 overflow-y-auto"
              >
                {!hasResults ? (
                  <div className="px-4 py-6 text-center text-sm text-muted">
                    No matches for &ldquo;{search.trim()}&rdquo;
                    <p className="text-xs mt-1">Press Enter to search candidates</p>
                  </div>
                ) : (
                  <>
                    {searchResults.candidates.length > 0 && (
                      <div>
                        <p className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-muted border-b border-col">
                          Candidates
                        </p>
                        {searchResults.candidates.map((candidate) => (
                          <button
                            key={candidate.candidateId}
                            type="button"
                            onClick={() => goToSearch('/candidates', search)}
                            className="w-full text-left px-4 py-3 border-b border-col last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                          >
                            <div className="flex items-center gap-2">
                              <Users size={14} className="text-blue-500 flex-shrink-0" />
                              <div className="min-w-0">
                                <p className="text-sm font-medium text-col truncate">{candidate.name}</p>
                                <p className="text-xs text-muted truncate">
                                  {candidate.candidateId} · {candidate.appliedJob}
                                </p>
                              </div>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                    {searchResults.jobs.length > 0 && (
                      <div>
                        <p className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-muted border-b border-col">
                          Jobs
                        </p>
                        {searchResults.jobs.map((job) => (
                          <button
                            key={job.id}
                            type="button"
                            onClick={() => goToSearch('/jobs', search)}
                            className="w-full text-left px-4 py-3 border-b border-col last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                          >
                            <div className="flex items-center gap-2">
                              <Briefcase size={14} className="text-green-500 flex-shrink-0" />
                              <div className="min-w-0">
                                <p className="text-sm font-medium text-col truncate">{job.title}</p>
                                <p className="text-xs text-muted truncate">
                                  {job.department} · {job.applicants} applicant{job.applicants !== 1 ? 's' : ''}
                                </p>
                              </div>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => handleSearchSubmit({ preventDefault: () => {} })}
                      className="w-full px-4 py-2.5 text-xs font-medium text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                    >
                      View all results
                    </button>
                  </>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <button
          type="button"
          onClick={toggleDark}
          className="w-9 h-9 rounded-xl border border-col flex items-center justify-center text-muted hover:text-col hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
        >
          {darkMode ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        <div className="relative" ref={notifWrapRef}>
          <button
            type="button"
            onClick={() => {
              setNotifOpen((o) => !o);
              setProfileOpen(false);
              setSearchOpen(false);
            }}
            className="w-9 h-9 rounded-xl border border-col flex items-center justify-center text-muted hover:text-col hover:bg-slate-100 dark:hover:bg-slate-800 transition-all relative"
            aria-label="Notifications"
            aria-expanded={notifOpen}
          >
            <Bell size={16} />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-primary-accent rounded-full" />
            )}
          </button>
          <AnimatePresence>
            {notifOpen && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.96 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 top-12 w-80 card z-50 overflow-hidden"
              >
                <div className="px-4 py-3 border-b border-col flex items-center justify-between gap-2">
                  <span className="font-semibold text-sm text-col">Notifications</span>
                  <div className="flex items-center gap-2 shrink-0">
                    {unreadCount > 0 && (
                      <span className="text-xs text-primary-accent font-medium">{unreadCount} new</span>
                    )}
                    {notifications.length > 0 && (
                      <button
                        type="button"
                        onClick={handleClearAllNotifications}
                        className="text-xs font-medium text-muted hover:text-col transition-colors"
                      >
                        Clear all
                      </button>
                    )}
                  </div>
                </div>
                {notifications.length === 0 ? (
                  <div className="px-4 py-8 text-center text-sm text-muted">
                    No new notifications
                  </div>
                ) : (
                  <div className="max-h-80 overflow-y-auto overscroll-contain">
                    {notifications.map((n) => (
                      <div
                        key={n.id}
                        className="relative group border-b border-col last:border-0 bg-orange-50/40 dark:bg-orange-900/10"
                      >
                        <button
                          type="button"
                          onClick={() => handleNotificationClick(n)}
                          className="w-full text-left px-4 py-3 pr-10 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                        >
                          <p className="text-sm text-col leading-snug">{n.text}</p>
                          <p className="text-xs text-muted mt-1">{n.time}</p>
                        </button>
                        <button
                          type="button"
                          onClick={(event) => handleDismissNotification(event, n.id)}
                          className="absolute top-2.5 right-2 w-7 h-7 rounded-lg flex items-center justify-center text-muted hover:text-col hover:bg-slate-200/80 dark:hover:bg-slate-700/80 transition-colors opacity-70 group-hover:opacity-100"
                          aria-label="Dismiss notification"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <CompanySwitcher
          onOpen={() => {
            setProfileOpen(false);
            setNotifOpen(false);
            setSearchOpen(false);
          }}
        />

        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setProfileOpen((o) => !o);
              setNotifOpen(false);
              setSearchOpen(false);
            }}
            className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-xl border border-col hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
          >
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold">
              {initials}
            </div>
            <div className="hidden sm:block text-left">
              <p className="text-xs font-medium text-col leading-tight">{user?.full_name || 'HR User'}</p>
              <p className="text-xs text-muted leading-tight">{user?.role || 'HR'}</p>
            </div>
            <ChevronDown size={14} className="text-muted" />
          </button>
          <AnimatePresence>
            {profileOpen && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.96 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 top-12 w-48 card z-50 overflow-hidden py-1"
              >
                <button
                  type="button"
                  onClick={() => {
                    setProfileOpen(false);
                    if (isStaffAdmin(user?.role)) navigate('/settings');
                  }}
                  className={`w-full text-left px-4 py-2.5 text-sm text-col hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                    isStaffAdmin(user?.role) ? '' : 'hidden'
                  }`}
                >
                  Settings
                </button>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="w-full text-left px-4 py-2.5 text-sm text-col hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                >
                  Sign out
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
}
