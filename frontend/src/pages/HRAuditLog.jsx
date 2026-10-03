import { useCallback, useEffect, useMemo, useState, Fragment } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  Search,
  LogIn,
  LogOut,
  Bot,
  UserCheck,
  UserX,
  Mail,
  UserPlus,
  UserCog,
  Clock,
  Briefcase,
  CalendarCheck,
  Send,
  ListFilter,
  ChevronDown,
  ChevronRight,
  Settings,
} from 'lucide-react';
import { getAuditLogs } from '../services/api';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/ui/EmptyState';
import CompanyTableFilter from '../components/CompanyTableFilter';
import { useApp } from '../context/AppContext';
import { isSuperAdmin } from '../utils/roles';
import { useAuth } from '../context/AuthContext';

const ACTION_CONFIG = {
  USER_LOGIN: {
    label: 'Signed in',
    icon: LogIn,
    badge: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  },
  USER_LOGOUT: {
    label: 'Signed out',
    icon: LogOut,
    badge: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
  },
  RESUME_EVALUATED: {
    label: 'Evaluated resume',
    icon: Bot,
    badge: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300',
  },
  CANDIDATE_SHORTLISTED: {
    label: 'Shortlisted',
    icon: UserCheck,
    badge: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  },
  CANDIDATE_REJECTED: {
    label: 'Rejected',
    icon: UserX,
    badge: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  },
  CANDIDATE_EMAIL_UPDATED: {
    label: 'Email updated',
    icon: Mail,
    badge: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300',
  },
  INVITE_RESENT: {
    label: 'Invite resent',
    icon: Mail,
    badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  },
  INTERVIEW_INVITE_SENT: {
    label: 'Invite sent',
    icon: Send,
    badge: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300',
  },
  INTERVIEW_SCHEDULED: {
    label: 'Interview booked',
    icon: CalendarCheck,
    badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  },
  INTERVIEW_QUESTION_ADDED: {
    label: 'Interview question added',
    icon: FileText,
    badge: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  },
  INTERVIEW_QUESTION_UPDATED: {
    label: 'Interview question updated',
    icon: FileText,
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  },
  INTERVIEW_QUESTION_DELETED: {
    label: 'Interview question removed',
    icon: FileText,
    badge: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
  },
  JOB_CREATED: {
    label: 'Job created',
    icon: Briefcase,
    badge: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  },
  JOB_UPDATED: {
    label: 'Job updated',
    icon: Briefcase,
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  },
  JOB_DELETED: {
    label: 'Job deleted',
    icon: Briefcase,
    badge: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
  },
  USER_CREATED: {
    label: 'User created',
    icon: UserPlus,
    badge: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300',
  },
  USER_UPDATED: {
    label: 'User updated',
    icon: UserCog,
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  },
  PROFILE_UPDATED: {
    label: 'Profile updated',
    icon: UserCog,
    badge: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300',
  },
  COMPANY_SETTINGS_UPDATED: {
    label: 'Company settings',
    icon: Settings,
    badge: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  },
  USER_PREFERENCES_UPDATED: {
    label: 'Preferences',
    icon: Settings,
    badge: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  },
  AI_SETTINGS_UPDATED: {
    label: 'AI settings',
    icon: Bot,
    badge: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300',
  },
};

const FILTER_TABS = [
  { key: 'all', label: 'All' },
  { key: 'jobs', label: 'Jobs' },
  { key: 'USER_LOGIN', label: 'Sign-ins' },
  { key: 'RESUME_EVALUATED', label: 'Screening' },
  { key: 'CANDIDATE_SHORTLISTED', label: 'Shortlist' },
  { key: 'CANDIDATE_REJECTED', label: 'Reject' },
  { key: 'invites', label: 'Invites' },
  { key: 'INTERVIEW_SCHEDULED', label: 'Booked' },
  { key: 'settings', label: 'Settings' },
];

const JOB_ACTIONS = new Set(['JOB_CREATED', 'JOB_UPDATED', 'JOB_DELETED']);
const INVITE_ACTIONS = new Set(['INVITE_RESENT', 'INTERVIEW_INVITE_SENT']);
const SETTINGS_ACTIONS = new Set([
  'PROFILE_UPDATED',
  'COMPANY_SETTINGS_UPDATED',
  'USER_PREFERENCES_UPDATED',
  'AI_SETTINGS_UPDATED',
]);

const AVATAR_COLORS = ['#7C3AED', '#0891B2', '#059669', '#D97706', '#DB2777', '#2563EB'];

function avatarColor(email = '') {
  let hash = 0;
  for (let i = 0; i < email.length; i += 1) {
    hash = email.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function getInitials(nameOrEmail = '') {
  const value = String(nameOrEmail || '').trim();
  if (!value) return 'SY';
  if (value.includes('@')) {
    return value.split('@')[0].slice(0, 2).toUpperCase();
  }
  const parts = value.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return value.slice(0, 2).toUpperCase();
}

function formatAction(action, status) {
  if (action === 'JOB_DELETED' && status && status !== 'SUCCESS') {
    return 'Delete blocked';
  }
  return ACTION_CONFIG[action]?.label || action.replace(/_/g, ' ').toLowerCase();
}

function formatWhen(value) {
  const date = new Date(value);
  return {
    date: date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
    time: date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
  };
}

function formatJson(value) {
  if (!value || (typeof value === 'object' && Object.keys(value).length === 0)) return '—';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function formatChanges(entry) {
  if (entry.old_value || entry.new_value) {
    const keys = new Set([
      ...Object.keys(entry.old_value || {}),
      ...Object.keys(entry.new_value || {}),
    ]);
    const parts = [...keys]
      .map((key) => {
        const from = entry.old_value?.[key];
        const to = entry.new_value?.[key];
        if (from === to) return null;
        return `${key}: ${from ?? '—'} → ${to ?? '—'}`;
      })
      .filter(Boolean);
    if (parts.length) return parts.join('; ');
  }

  const changes = entry.details?.changes;
  if (Array.isArray(changes) && changes.length) {
    return changes
      .map((c) => (typeof c === 'string' ? c : `${c.field} ${c.from} → ${c.to}`))
      .join('; ');
  }
  return '—';
}

function formatDetail(entry) {
  if (entry.message) return entry.message;
  return formatChanges(entry);
}

function matchesFilter(entry, actionFilter) {
  if (actionFilter === 'all') return true;
  if (actionFilter === 'jobs') return JOB_ACTIONS.has(entry.action);
  if (actionFilter === 'invites') return INVITE_ACTIONS.has(entry.action);
  if (actionFilter === 'settings') return SETTINGS_ACTIONS.has(entry.action);
  return entry.action === actionFilter;
}

function StatusBadge({ status }) {
  const ok = (status || 'SUCCESS') === 'SUCCESS';
  return (
    <span
      className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-semibold ${
        ok
          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
          : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
      }`}
    >
      {status || 'SUCCESS'}
    </span>
  );
}

function ActionBadge({ action, status }) {
  const failed = status && status !== 'SUCCESS';
  const config = ACTION_CONFIG[action] || {
    label: formatAction(action, status),
    icon: FileText,
    badge: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  };
  const Icon = config.icon;
  const label = formatAction(action, status);
  const badge = failed
    ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
    : config.badge;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${badge}`}>
      <Icon size={12} />
      {label}
    </span>
  );
}

function DetailRow({ label, value }) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-1">{label}</p>
      <p className="text-xs text-col break-all whitespace-pre-wrap font-mono bg-slate-50 dark:bg-slate-900/40 rounded-lg px-2.5 py-2">
        {value || '—'}
      </p>
    </div>
  );
}

export default function HRAuditLog() {
  const { user } = useAuth();
  const { companies, workingCompanyId } = useApp();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [actionFilter, setActionFilter] = useState('all');
  const [companyFilter, setCompanyFilter] = useState('all');
  const [expandedId, setExpandedId] = useState(null);

  const loadEntries = useCallback(async (options = {}) => {
    const silent = Boolean(options.silent);
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const { data } = await getAuditLogs(200, companyFilter === 'all' ? undefined : companyFilter);
      setEntries(data.entries || []);
      setError(null);
    } catch (err) {
      if (!silent) {
        setError(err.response?.data?.detail || 'Failed to load audit log.');
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [companyFilter]);

  useEffect(() => {
    loadEntries();
  }, [loadEntries]);

  useEffect(() => {
    if (!isSuperAdmin(user?.role) || !workingCompanyId) return;
    setCompanyFilter(String(workingCompanyId));
  }, [user?.role, workingCompanyId]);

  useAutoRefresh(() => loadEntries({ silent: true }));

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return entries.filter((entry) => {
      if (!matchesFilter(entry, actionFilter)) return false;
      if (!q) return true;
      return (
        entry.user_email?.toLowerCase().includes(q) ||
        entry.user_name?.toLowerCase().includes(q) ||
        entry.user_role?.toLowerCase().includes(q) ||
        entry.message?.toLowerCase().includes(q) ||
        entry.entity_id?.toLowerCase().includes(q) ||
        entry.ip_address?.toLowerCase().includes(q) ||
        entry.request_id?.toLowerCase().includes(q) ||
        entry.session_id?.toLowerCase().includes(q) ||
        entry.status?.toLowerCase().includes(q) ||
        entry.company_name?.toLowerCase().includes(q) ||
        formatAction(entry.action, entry.status).toLowerCase().includes(q)
      );
    });
  }, [entries, search, actionFilter]);

  return (
    <div className="max-w-[1400px] mx-auto space-y-5">
      <div>
        <h2 className="text-xl font-bold text-col">Activity Audit Log</h2>
        <p className="text-sm text-muted mt-1 max-w-3xl">
          Full audit trail with actor role, IP, user agent, session/request IDs, status, and before/after values.
        </p>
      </div>

      <div className="card p-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search user, IP, request ID, action…"
            className="pl-9 pr-4 py-2 text-sm rounded-xl border border-col bg-transparent w-full text-col placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all"
          />
        </div>
        <div className="relative min-w-[180px]">
          <ListFilter size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            aria-label="Filter by action"
            className="appearance-none w-full pl-9 pr-9 py-2 text-sm rounded-xl border border-col bg-transparent text-col focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all cursor-pointer"
          >
            {FILTER_TABS.map((tab) => (
              <option key={tab.key} value={tab.key}>
                {tab.label}
              </option>
            ))}
          </select>
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted text-xs">▾</span>
        </div>
        {isSuperAdmin(user?.role) && (
          <CompanyTableFilter
            value={companyFilter}
            onChange={setCompanyFilter}
            companies={companies}
          />
        )}
      </div>

      {error && (
        <div className="card bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm px-4 py-3">
          {error}
        </div>
      )}

      <div className="card p-0 overflow-hidden">
        <div className="px-5 py-4 border-b border-col flex items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-col">Recent activity</h3>
            <p className="text-xs text-muted mt-0.5">
              {filtered.length} event{filtered.length !== 1 ? 's' : ''}
              {actionFilter !== 'all' ? ` · ${FILTER_TABS.find((t) => t.key === actionFilter)?.label}` : ''}
            </p>
          </div>
          <span className="inline-flex items-center gap-1.5 text-xs text-muted">
            <Clock size={12} />
            Last {entries.length} records
          </span>
        </div>

        {loading ? (
          <LoadingSpinner message="Loading audit log..." />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No activity found"
            description={
              search || actionFilter !== 'all'
                ? 'Try a different search or filter.'
                : 'Actions will appear here when users sign in or perform HR tasks.'
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[1100px]">
              <thead>
                <tr className="border-b border-col bg-slate-50/80 dark:bg-slate-800/40">
                  <th className="text-left px-3 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider w-8" />
                  <th className="text-left px-4 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">When</th>
                  <th className="text-left px-4 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">User</th>
                  <th className="text-left px-4 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">Company</th>
                  <th className="text-left px-4 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">Role</th>
                  <th className="text-left px-4 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">Action</th>
                  <th className="text-left px-4 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">Entity</th>
                  <th className="text-left px-4 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">Status</th>
                  <th className="text-left px-4 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">IP</th>
                  <th className="text-left px-4 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">Location</th>
                  <th className="text-left px-4 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">Changes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-col">
                {filtered.map((entry, index) => {
                  const when = formatWhen(entry.created_at);
                  const email = entry.user_email || 'System';
                  const displayName = entry.user_name || email;
                  const open = expandedId === entry.id;
                  return (
                    <Fragment key={entry.id}>
                      <motion.tr
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(index * 0.01, 0.2) }}
                        className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
                      >
                        <td className="px-3 py-4">
                          <button
                            type="button"
                            onClick={() => setExpandedId(open ? null : entry.id)}
                            className="text-muted hover:text-col"
                            aria-label={open ? 'Collapse audit details' : 'Expand audit details'}
                          >
                            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </button>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <p className="text-col font-medium">{when.date}</p>
                          <p className="text-xs text-muted">{when.time}</p>
                        </td>
                        <td className="px-4 py-4">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div
                              className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0"
                              style={{ background: avatarColor(displayName) }}
                            >
                              {getInitials(displayName)}
                            </div>
                            <div className="min-w-0">
                              <p className="text-col font-medium truncate max-w-[200px]">{displayName}</p>
                              <p className="text-[11px] text-muted truncate max-w-[200px]">
                                {entry.user_name
                                  ? `${email}${entry.user_id != null ? ` · ID ${entry.user_id}` : ''}`
                                  : entry.user_id != null
                                    ? `ID ${entry.user_id}`
                                    : email !== 'System'
                                      ? email
                                      : '—'}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-4">
                          <span className="text-xs font-medium text-col">{entry.company_name || '—'}</span>
                        </td>
                        <td className="px-4 py-4">
                          <span className="text-xs font-medium text-col">{entry.user_role || '—'}</span>
                        </td>
                        <td className="px-4 py-4">
                          <ActionBadge action={entry.action} status={entry.status} />
                        </td>
                        <td className="px-4 py-4">
                          <p className="text-col text-xs font-medium">{entry.entity_type || '—'}</p>
                          <p className="text-[11px] text-muted font-mono truncate max-w-[140px]">
                            {entry.entity_id || '—'}
                          </p>
                        </td>
                        <td className="px-4 py-4">
                          <StatusBadge status={entry.status} />
                        </td>
                        <td className="px-4 py-4">
                          <span className="font-mono text-xs text-col">{entry.ip_address || '—'}</span>
                        </td>
                        <td className="px-4 py-4">
                          <span className="text-xs text-muted">{entry.location || '—'}</span>
                        </td>
                        <td className="px-4 py-4 text-muted max-w-xs">
                          <p className="line-clamp-2 leading-relaxed text-xs">{formatDetail(entry)}</p>
                          <p className="text-[11px] text-muted mt-1 line-clamp-1">{formatChanges(entry)}</p>
                        </td>
                      </motion.tr>
                      <AnimatePresence>
                        {open && (
                          <tr className="bg-slate-50/70 dark:bg-slate-900/30">
                            <td colSpan={11} className="px-5 py-4">
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3"
                              >
                                <DetailRow label="User Agent" value={entry.user_agent} />
                                <DetailRow label="Session ID" value={entry.session_id} />
                                <DetailRow label="Request ID" value={entry.request_id} />
                                <DetailRow label="Entity ID" value={entry.entity_id} />
                                <DetailRow label="Old Value" value={formatJson(entry.old_value)} />
                                <DetailRow label="New Value" value={formatJson(entry.new_value)} />
                                <DetailRow label="Message" value={entry.message} />
                                <DetailRow label="Details JSON" value={formatJson(entry.details)} />
                              </motion.div>
                            </td>
                          </tr>
                        )}
                      </AnimatePresence>
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
