import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Users, Briefcase, Bot, Clock, Star, XCircle, CalendarDays, CheckCircle2,
  Upload, X, Activity
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import StatsCard from '../../components/ui/StatsCard';
import { MatchScore, StatusBadge } from '../../components/ui/Badges';
import LoadingSpinner from '../../components/LoadingSpinner';
import { useApp } from '../../context/AppContext';

const ACTIVITY_ICONS = {
  upload: Upload,
  bot: Bot,
  check: CheckCircle2,
  briefcase: Briefcase,
  x: X,
};
const ACTIVITY_COLORS = {
  upload: 'text-blue-500 bg-blue-50 dark:bg-blue-900/20',
  bot: 'text-violet-500 bg-violet-50 dark:bg-violet-900/20',
  check: 'text-green-500 bg-green-50 dark:bg-green-900/20',
  briefcase: 'text-amber-500 bg-amber-50 dark:bg-amber-900/20',
  x: 'text-red-500 bg-red-50 dark:bg-red-900/20',
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-sm">
      <p className="font-medium text-col">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: {p.value}</p>
      ))}
    </div>
  );
};

export default function Dashboard() {
  const { stats, candidates, activity, loadingData, dataError } = useApp();
  const navigate = useNavigate();

  if (loadingData && !candidates.length) {
    return <LoadingSpinner message="Loading dashboard from database..." />;
  }

  const statCards = [
    { title: 'Total Candidates', value: stats.total_candidates, icon: Users, color: 'blue' },
    { title: 'Active Jobs', value: stats.active_jobs, icon: Briefcase, color: 'green' },
    { title: 'AI Screened', value: stats.ai_screened, icon: Bot, color: 'violet' },
    { title: 'Pending Reviews', value: stats.pending_reviews, icon: Clock, color: 'amber' },
    { title: 'Shortlisted', value: stats.shortlisted, icon: Star, color: 'green' },
    { title: 'Rejected', value: stats.rejected, icon: XCircle, color: 'red' },
    { title: 'Interview Scheduled', value: stats.interview_scheduled, icon: CalendarDays, color: 'cyan' },
    { title: 'Interview Completed', value: stats.interview_completed, icon: CheckCircle2, color: 'teal' },
  ];

  const recentCandidates = candidates.slice(0, 4);
  const statusPie = stats.status_distribution?.length
    ? stats.status_distribution
    : [{ name: 'No data', value: 1, color: '#94A3B8' }];
  const applicationsPerJob = stats.applications_per_job?.length
    ? stats.applications_per_job
    : [{ name: 'No jobs yet', applicants: 0 }];
  const matchTrend = stats.match_trend?.length
    ? stats.match_trend
    : [{ month: 'Current', avgScore: stats.average_match_score || 0 }];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {dataError && (
        <div className="card bg-red-50 border border-red-200 text-red-700 text-sm">{dataError}</div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-4 gap-4">
        {statCards.map((s, i) => (
          <StatsCard key={s.title} {...s} delay={i * 0.05} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="card p-5 lg:col-span-2"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-col">Average Match Score</h3>
              <p className="text-xs text-muted">Monthly AI screening quality</p>
            </div>
            <span className="text-xs font-medium text-green-500 bg-green-50 dark:bg-green-900/20 px-2.5 py-1 rounded-full">
              Avg {stats.average_match_score || 0}%
            </span>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={matchTrend}>
              <defs>
                <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563EB" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="month" tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="avgScore" name="Avg Score" stroke="#2563EB" strokeWidth={2.5} fill="url(#scoreGrad)" dot={{ fill: '#2563EB', r: 4 }} activeDot={{ r: 6 }} />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}
          className="card p-5"
        >
          <div className="mb-4">
            <h3 className="font-semibold text-col">Candidate Status</h3>
            <p className="text-xs text-muted">Live database distribution</p>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={statusPie} cx="50%" cy="50%" innerRadius={62} outerRadius={92} paddingAngle={4} dataKey="value">
                {statusPie.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-2 mt-2">
            {statusPie.map((s) => (
              <div key={s.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: s.color }} />
                  <span className="text-muted">{s.name}</span>
                </div>
                <span className="font-semibold text-col">{s.value}</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
        className="card p-5"
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-semibold text-col">Applications per Job</h3>
            <p className="text-xs text-muted">Applicants on saved job postings</p>
          </div>
          <button type="button" onClick={() => navigate('/jobs')} className="text-xs text-blue-500 hover:text-blue-600 font-medium">View all jobs →</button>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={applicationsPerJob} barSize={40}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="applicants" name="Applicants" fill="#2563EB" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.45 }}
          className="card p-5"
        >
          <div className="flex items-center gap-2 mb-4">
            <Activity size={16} className="text-blue-500" />
            <h3 className="font-semibold text-col">Recent Activity</h3>
          </div>
          <div className="space-y-4">
            {activity.length === 0 ? (
              <p className="text-sm text-muted">No audit activity recorded yet.</p>
            ) : activity.slice(0, 6).map((a, i) => {
              const Icon = ACTIVITY_ICONS[a.icon] || Activity;
              const cls = ACTIVITY_COLORS[a.icon] || ACTIVITY_COLORS.bot;
              return (
                <motion.div
                  key={a.id}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 + i * 0.05 }}
                  className="flex items-start gap-3"
                >
                  <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 ${cls}`}>
                    <Icon size={14} />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-col">{a.text}</p>
                    <p className="text-xs text-muted mt-0.5">{a.time}</p>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}
          className="card p-5"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-col">Latest AI Screenings</h3>
            <button type="button" onClick={() => navigate('/candidates')} className="text-xs text-blue-500 hover:text-blue-600 font-medium">View all →</button>
          </div>
          <div className="space-y-3">
            {recentCandidates.length === 0 ? (
              <p className="text-sm text-muted">No candidates in the database yet. Run AI Screening to add records.</p>
            ) : recentCandidates.map((c, i) => (
              <motion.div
                key={c.id}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.55 + i * 0.05 }}
                className="flex items-center gap-3 p-2 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                onClick={() => navigate('/candidates')}
              >
                <div
                  className="w-9 h-9 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                  style={{ background: c.avatarColor }}
                >
                  {c.avatar}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-col truncate">{c.name}</p>
                  <p className="text-xs text-muted truncate">{c.appliedJob}</p>
                </div>
                <MatchScore score={c.matchScore} />
                <StatusBadge status={c.status} />
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
