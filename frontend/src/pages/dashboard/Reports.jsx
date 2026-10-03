import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import { FileText, FileSpreadsheet, File } from 'lucide-react';
import { Link } from 'react-router-dom';
import LoadingSpinner from '../../components/LoadingSpinner';
import { useApp } from '../../context/AppContext';
import { exportReport } from '../../utils/reportExport';
import { wholePercentShares } from '../../utils/helpers';
import { listHrRecommendationReports } from '../../services/api';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-sm shadow-lg">
      <p className="font-medium text-col mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="text-xs" style={{ color: p.color || '#2563EB' }}>
          {p.name}: <span className="font-semibold">{p.value}</span>
        </p>
      ))}
    </div>
  );
};

function ChartCard({ title, subtitle, children, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="card p-5"
    >
      <div className="mb-4">
        <h3 className="font-semibold text-col">{title}</h3>
        {subtitle && <p className="text-xs text-muted mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </motion.div>
  );
}

export default function Reports() {
  const { stats, candidates, loadingData, addToast, workingCompany } = useApp();
  const [exporting, setExporting] = useState(null);
  const [hrReports, setHrReports] = useState([]);

  useEffect(() => {
    let cancelled = false;
    listHrRecommendationReports()
      .then(({ data }) => {
        if (!cancelled) setHrReports(data?.reports || []);
      })
      .catch(() => {
        if (!cancelled) setHrReports([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loadingData && !candidates.length) {
    return <LoadingSpinner message="Loading reports from database..." />;
  }

  const exportLabels = { pdf: 'PDF', csv: 'CSV', xlsx: 'Excel' };

  const handleExport = async (format) => {
    setExporting(format);
    try {
      await exportReport(format, stats, candidates, workingCompany);
      addToast(`Report downloaded as ${exportLabels[format] || format.toUpperCase()}.`, 'success');
    } catch (error) {
      addToast(error.message || `Failed to export ${format.toUpperCase()}.`, 'error');
    } finally {
      setExporting(null);
    }
  };

  const inviteDelivery = stats.invite_delivery || {
    issued: 0,
    not_issued: 0,
    awaiting_booking: 0,
    booked: 0,
    candidates: [],
  };

  const statusPie = stats.status_distribution?.length
    ? stats.status_distribution
    : [{ name: 'No data', value: 1, color: '#94A3B8' }];
  const applicationsPerJob = stats.applications_per_job?.length
    ? stats.applications_per_job
    : [{ name: 'No jobs yet', applicants: 0 }];
  const matchTrend = stats.match_trend?.length
    ? stats.match_trend
    : [{ month: 'Current', avgScore: stats.average_match_score || 0 }];
  const topSkills = stats.top_skills?.length
    ? stats.top_skills
    : [{ skill: 'No skills yet', count: 0 }];
  const hiringFunnel = stats.hiring_funnel?.length
    ? stats.hiring_funnel
    : [{ stage: 'Screened', count: 0 }];
  const funnelOutcomes = hiringFunnel.filter((stage) => stage.stage !== 'Screened');
  const screenedTotal = Number(
    hiringFunnel.find((stage) => stage.stage === 'Screened')?.count
    ?? funnelOutcomes.reduce((sum, stage) => sum + Number(stage.count || 0), 0),
  );
  const funnelWithPercents = wholePercentShares(funnelOutcomes, { total: screenedTotal });

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-col">Analytics & Reports</h2>
          <p className="text-sm text-muted mt-1 max-w-2xl">
            Live hiring metrics from your database — who applied, how they scored, and where they are in the pipeline.
          </p>
        </div>
        <div className="flex gap-2">
          {[
            { format: 'pdf', icon: FileText, label: 'PDF' },
            { format: 'csv', icon: FileSpreadsheet, label: 'CSV' },
            { format: 'xlsx', icon: File, label: 'Excel' },
          ].map(({ format, icon: Icon, label }) => (
            <button
              key={format}
              type="button"
              disabled={!!exporting}
              onClick={() => handleExport(format)}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl border border-col text-sm font-medium text-muted hover:text-col hover:bg-slate-50 dark:hover:bg-slate-800 transition-all disabled:opacity-50"
            >
              <Icon size={14} />
              {exporting === format ? 'Exporting…' : label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Candidates', value: stats.total_candidates, sub: 'All saved screenings', color: 'text-blue-600' },
          { label: 'Avg Match Score', value: `${stats.average_match_score || 0}%`, sub: 'AI score across all', color: 'text-violet-600' },
          { label: 'Invite emails issued', value: stats.invite_delivery?.issued ?? 0, sub: 'Scheduling email sent', color: 'text-green-600' },
          { label: 'No invite yet', value: stats.invite_delivery?.not_issued ?? 0, sub: 'Shortlisted, email not sent', color: 'text-amber-600' },
          { label: 'Needs Review', value: stats.pending_reviews, sub: 'Awaiting HR decision', color: 'text-amber-600' },
          { label: 'Shortlisted', value: stats.shortlisted, sub: 'Not booked yet', color: 'text-green-600' },
          { label: 'Interview Scheduled', value: stats.interview_scheduled, sub: 'Slot booked', color: 'text-cyan-600' },
          { label: 'Interview Completed', value: stats.interview_completed ?? 0, sub: 'Finished the interview', color: 'text-teal-600' },
          { label: 'Rejected', value: stats.rejected, sub: 'Archived in system', color: 'text-red-600' },
        ].map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            className="card p-4 text-center"
          >
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
            <p className="text-xs font-medium text-col mt-1">{s.label}</p>
            <p className="text-xs text-muted mt-0.5">{s.sub}</p>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Applications by Job" subtitle="Current open positions" delay={0.1}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={applicationsPerJob} barSize={28}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="applicants" name="Applicants" fill="#2563EB" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Candidate Status Distribution" subtitle="All candidates" delay={0.15}>
          <div className="flex items-center gap-6">
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={statusPie} cx="50%" cy="50%" innerRadius={52} outerRadius={76} paddingAngle={4} dataKey="value">
                  {statusPie.map((e, i) => <Cell key={i} fill={e.color} />)}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-3 flex-shrink-0">
              {statusPie.map((s) => (
                <div key={s.name} className="flex items-center gap-2 text-sm">
                  <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: s.color }} />
                  <div>
                    <p className="font-medium text-col">{s.value}</p>
                    <p className="text-xs text-muted">{s.name}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </ChartCard>

        <ChartCard title="Average Match Score Trend" subtitle="Monthly AI quality trend" delay={0.2}>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={matchTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="month" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Line type="monotone" dataKey="avgScore" name="Avg Score" stroke="#2563EB" strokeWidth={2.5} dot={{ fill: '#2563EB', r: 4 }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Top Skills in Market" subtitle="From matched resume skills" delay={0.25}>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={topSkills} layout="vertical" barSize={16}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
              <XAxis type="number" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="skill" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} width={80} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" name="Candidates" fill="#7C3AED" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <ChartCard
        title="Hiring Funnel"
        subtitle={`Current status as a share of ${screenedTotal} screened candidates. These percentages add up to 100%.`}
        delay={0.3}
      >
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="font-medium text-col">Screened</span>
            <span className="text-muted tabular-nums">{screenedTotal} candidates · 100%</span>
          </div>
          {funnelWithPercents.map((stage, i) => {
            const pct = stage.percent ?? 0;
            const stageColors = {
              Pending: '#94A3B8',
              'Needs Review': '#F59E0B',
              Shortlisted: '#22C55E',
              'Interview Scheduled': '#0891B2',
              Rejected: '#EF4444',
            };
            const barColor = stageColors[stage.stage] || '#2563EB';
            return (
              <div key={stage.stage} className="flex items-center gap-4">
                <span className="text-sm text-muted w-32 text-right flex-shrink-0">{stage.stage}</span>
                <div className="flex-1 bg-slate-100 dark:bg-slate-800 rounded-full h-7 overflow-hidden">
                  {pct > 0 ? (
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ delay: 0.4 + i * 0.08, duration: 0.6, ease: 'easeOut' }}
                      className="h-full rounded-full flex items-center justify-end pr-3"
                      style={{ background: barColor }}
                    >
                      <span className="text-xs font-semibold text-white">{stage.count}</span>
                    </motion.div>
                  ) : (
                    <span className="h-full flex items-center pl-3 text-xs font-semibold text-muted">0</span>
                  )}
                </div>
                <span className="text-xs text-muted w-10 flex-shrink-0 tabular-nums">{pct}%</span>
              </div>
            );
          })}
        </div>
      </ChartCard>

      <ChartCard
        title="Interview invite emails"
        subtitle="Whether each shortlisted candidate received a scheduling email. Export PDF/Excel/CSV includes this list."
        delay={0.32}
      >
        <div className="flex flex-wrap gap-4 text-sm mb-4">
          <p className="text-col"><span className="font-semibold text-green-600">{inviteDelivery.issued}</span> invite sent</p>
          <p className="text-col"><span className="font-semibold text-amber-600">{inviteDelivery.not_issued}</span> not sent yet</p>
        </div>
        {inviteDelivery.candidates?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                  <th className="pb-2 font-semibold">Candidate</th>
                  <th className="pb-2 font-semibold">Email</th>
                  <th className="pb-2 font-semibold">Job</th>
                  <th className="pb-2 font-semibold">Invite</th>
                </tr>
              </thead>
              <tbody>
                {inviteDelivery.candidates.map((row) => (
                  <tr key={row.candidate_id} className="border-t border-col">
                    <td className="py-2.5">
                      <Link
                        to={`/hr-review?candidate=${row.candidate_id}`}
                        className="font-medium text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        {row.full_name}
                      </Link>
                    </td>
                    <td className="py-2.5 text-muted">{row.email}</td>
                    <td className="py-2.5 text-muted">{row.job_position || '—'}</td>
                    <td className="py-2.5">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        row.invite_sent
                          ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                          : 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                      }`}>
                        {row.invite_sent ? 'Sent' : 'Not sent'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-muted">No shortlisted candidates are waiting for a scheduling email.</p>
        )}
      </ChartCard>

      <ChartCard title="Agent 7 HR recommendations" subtitle="Final hire / consider / reject reports" delay={0.35}>
        {hrReports.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                  <th className="pb-2 font-semibold">Candidate</th>
                  <th className="pb-2 font-semibold">Role</th>
                  <th className="pb-2 font-semibold">Decision</th>
                  <th className="pb-2 font-semibold">Overall</th>
                  <th className="pb-2 font-semibold">Stage</th>
                </tr>
              </thead>
              <tbody>
                {hrReports.slice(0, 12).map((row) => (
                  <tr key={row.report_id} className="border-t border-col">
                    <td className="py-2.5">
                      <Link
                        to={`/candidates/${row.candidate_id}`}
                        className="font-medium text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        {row.full_name || row.candidate_id}
                      </Link>
                    </td>
                    <td className="py-2.5 text-muted">{row.job_position || '—'}</td>
                    <td className="py-2.5 font-semibold text-col">{row.decision}</td>
                    <td className="py-2.5 text-col">{Number(row.overall_score || 0).toFixed(0)}</td>
                    <td className="py-2.5 text-muted capitalize">{row.stage}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-muted">
            No Agent 7 reports yet. Complete a live interview or open a candidate and generate the HR report.
          </p>
        )}
      </ChartCard>
    </div>
  );
}
