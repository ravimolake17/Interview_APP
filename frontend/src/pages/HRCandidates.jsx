import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import { motion } from 'framer-motion';
import {
  ClipboardList,
  Search,
  Mail,
  FileText,
  ExternalLink,
  CheckCircle,
  XCircle,
  Send,
  User,
  Save,
} from 'lucide-react';
import {
  getHRCandidateDetail,
  getHRCandidates,
  getScreeningFileUrl,
  rejectCandidate,
  resendCandidateInvite,
  shortlistCandidate,
  updateCandidateEmail,
} from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/ui/EmptyState';
import EvaluationDetailPanels from '../components/ui/EvaluationDetailPanels';
import { MatchScore, SkillBadge, StatusBadge } from '../components/ui/Badges';
import ListFiltersMenu, { FilterChips } from '../components/ui/ListFiltersMenu';
import { buildEvaluationDetailFromSnapshot } from '../utils/hrMappers';

const TABS = [
  { key: 'shortlisted', label: 'Shortlisted', color: 'green' },
  { key: 'needs_review', label: 'Needs Review', color: 'amber' },
  { key: 'rejected', label: 'Rejected', color: 'red' },
];

const AVATAR_COLORS = ['#7C3AED', '#0891B2', '#059669', '#D97706', '#DB2777', '#2563EB'];

function avatarColor(name = '') {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function getInitials(name = '') {
  return name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

function mapBackendStatus(status) {
  const labels = {
    NEEDS_REVIEW: 'Needs Review',
    SHORTLISTED: 'Shortlisted',
    REJECTED: 'Rejected',
    INTERVIEW_SCHEDULED: 'Interview Scheduled',
    INTERVIEW_COMPLETED: 'Interview Completed',
    PENDING: 'Pending',
  };
  return labels[status] || status;
}

function displayContactEmail(candidate) {
  if (!candidate) return '';
  if (candidate.email_missing) return 'No email extracted';
  return candidate.email || '';
}

function matchesHRCandidate(candidate, query) {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    candidate.full_name?.toLowerCase().includes(q) ||
    candidate.email?.toLowerCase().includes(q) ||
    candidate.job_position?.toLowerCase().includes(q) ||
    candidate.candidate_id?.toLowerCase().includes(q)
  );
}

function SectionCard({ title, children, action }) {
  return (
    <div className="rounded-xl border border-col bg-slate-50/50 dark:bg-slate-800/30 overflow-hidden">
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-col bg-white/80 dark:bg-slate-900/40">
        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider">{title}</h4>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

export default function HRCandidates() {
  const { refreshData } = useApp();
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(() => {
    const tab = searchParams.get('tab') || 'shortlisted';
    return TABS.some((item) => item.key === tab) ? tab : 'shortlisted';
  });
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState(null);
  const [emailDraft, setEmailDraft] = useState('');
  const [emailSaving, setEmailSaving] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [jobFilter, setJobFilter] = useState('All');
  const [minScore, setMinScore] = useState(0);
  const [inviteFilter, setInviteFilter] = useState('All');

  const loadCandidates = useCallback(async (statusOverride, options = {}) => {
    const silent = Boolean(options.silent);
    const statusKey = statusOverride ?? activeTab;
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const { data } = await getHRCandidates(statusKey);
      const list = data.candidates || [];
      setCandidates(list);
      if (!silent) {
        setSelectedId(null);
        setDetail(null);
      } else {
        setSelectedId((current) => (
          current && !list.some((item) => item.candidate_id === current) ? null : current
        ));
        setDetail((current) => (
          current && !list.some((item) => item.candidate_id === current.candidate_id)
            ? null
            : current
        ));
      }
    } catch (err) {
      if (!silent) {
        setError(err.response?.data?.detail || 'Failed to load candidates.');
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  useAutoRefresh(() => loadCandidates(undefined, { silent: true }));

  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab && TABS.some((item) => item.key === tab) && tab !== activeTab) {
      setActiveTab(tab);
    }
  }, [searchParams, activeTab]);

  const jobOptions = useMemo(() => {
    const jobs = [...new Set(candidates.map((c) => c.job_position).filter(Boolean))];
    return jobs.sort((a, b) => a.localeCompare(b));
  }, [candidates]);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (jobFilter !== 'All') count += 1;
    if (minScore > 0) count += 1;
    if (inviteFilter !== 'All') count += 1;
    return count;
  }, [jobFilter, minScore, inviteFilter]);

  const clearAdvancedFilters = () => {
    setJobFilter('All');
    setMinScore(0);
    setInviteFilter('All');
  };

  const filteredCandidates = useMemo(
    () => candidates.filter((candidate) => {
      if (!matchesHRCandidate(candidate, search)) return false;
      if (jobFilter !== 'All' && candidate.job_position !== jobFilter) return false;
      if (Math.round(candidate.resume_score || 0) < minScore) return false;
      if (inviteFilter === 'Email sent' && !candidate.invite_sent) return false;
      if (inviteFilter === 'Not sent' && candidate.invite_sent) return false;
      return true;
    }),
    [candidates, search, jobFilter, minScore, inviteFilter],
  );

  const loadDetail = useCallback(async (candidateId) => {
    setSelectedId(candidateId);
    setDetailLoading(true);
    setActionMessage(null);
    try {
      const { data } = await getHRCandidateDetail(candidateId);
      setDetail(data);
      setEmailDraft(data.email_missing ? '' : (data.email || ''));
    } catch (err) {
      setDetail(null);
      setError(err.response?.data?.detail || 'Failed to load candidate details.');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    const candidateId = searchParams.get('candidate');
    if (!candidateId || loading) return;
    loadDetail(candidateId);
  }, [searchParams, loading, loadDetail]);

  const handleShortlist = async () => {
    if (!selectedId) return;
    setActionLoading(true);
    setActionMessage(null);
    try {
      const { data } = await shortlistCandidate(selectedId);
      setActionMessage({ type: 'success', text: data.message });
      await Promise.all([loadCandidates(), refreshData({ silent: true, force: true })]);
      await loadDetail(selectedId);
    } catch (err) {
      setActionMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to shortlist candidate.',
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleResend = async () => {
    if (!selectedId) return;
    setActionLoading(true);
    setActionMessage(null);
    try {
      const { data } = await resendCandidateInvite(selectedId);
      setActionMessage({ type: 'success', text: `${data.message} Link sent again.` });
      await Promise.all([loadCandidates(), refreshData({ silent: true, force: true })]);
      await loadDetail(selectedId);
    } catch (err) {
      setActionMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Cannot resend invite.',
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveEmail = async (event) => {
    event.preventDefault();
    if (!selectedId || !detail?.can_edit_email) return;
    const email = emailDraft.trim();
    if (!email) {
      setActionMessage({ type: 'error', text: 'Enter an email address.' });
      return;
    }
    setEmailSaving(true);
    setActionMessage(null);
    try {
      const { data } = await updateCandidateEmail(selectedId, email);
      setActionMessage({ type: 'success', text: data.message });
      setEmailDraft('');
      await Promise.all([
        loadCandidates(undefined, { silent: true }),
        refreshData({ silent: true, force: true }),
      ]);
      await loadDetail(selectedId);
    } catch (err) {
      const detailErr = err.response?.data?.detail;
      const text = Array.isArray(detailErr)
        ? detailErr.map((item) => item.msg || item).join('; ')
        : (detailErr || 'Could not save email.');
      setActionMessage({ type: 'error', text });
    } finally {
      setEmailSaving(false);
    }
  };

  const handleReject = async () => {
    if (!selectedId) return;
    if (!window.confirm('Reject this candidate? They will move to the Rejected tab.')) return;
    setActionLoading(true);
    setActionMessage(null);
    try {
      const { data } = await rejectCandidate(selectedId);
      setActionMessage({ type: 'success', text: data.message });
      setActiveTab('rejected');
      await Promise.all([loadCandidates('rejected'), refreshData({ silent: true, force: true })]);
    } catch (err) {
      setActionMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to reject candidate.',
      });
    } finally {
      setActionLoading(false);
    }
  };

  const canReject =
    detail &&
    (detail.status === 'NEEDS_REVIEW' ||
      (detail.status === 'SHORTLISTED' && !detail.interview_scheduled && !detail.invite_used));

  const resumeText =
    detail?.evaluation_snapshot?.resume_text ||
    detail?.evaluation_snapshot?.parsed_resume?.source_text ||
    detail?.resume_text ||
    '';

  const evaluationDetail = useMemo(() => {
    if (!detail) return null;
    return buildEvaluationDetailFromSnapshot(detail.evaluation_snapshot || {}, {
      matched_skills: detail.matched_skills,
      missing_skills: detail.missing_skills,
      strengths: detail.strengths,
      concerns: detail.concerns,
      final_recommendation: detail.final_recommendation,
      education: detail.education_summary,
      experience: detail.experience_summary,
      job_position: detail.job_position,
    });
  }, [detail]);

  const activeTabLabel = TABS.find((tab) => tab.key === activeTab)?.label || activeTab;

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div>
        <h2 className="text-xl font-bold text-col">HR Candidate Review</h2>
        <p className="text-sm text-muted mt-1 max-w-3xl">
          Review screened candidates, promote needs-review profiles to shortlisted, and resend
          scheduling emails before a candidate books a slot.
        </p>
      </div>

      <div className="card p-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, email, or ID…"
            className="pl-9 pr-4 py-2 text-sm rounded-xl border border-col bg-transparent w-full text-col placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => {
                setActiveTab(tab.key);
                setSearch('');
                clearAdvancedFilters();
              }}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === tab.key
                  ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/25'
                  : 'text-muted hover:bg-slate-100 dark:hover:bg-slate-800 border border-col'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <ListFiltersMenu
          open={filtersOpen}
          onOpenChange={setFiltersOpen}
          activeCount={activeFilterCount}
          jobFilter={jobFilter}
          onJobFilter={setJobFilter}
          jobOptions={jobOptions}
          minScore={minScore}
          onMinScore={setMinScore}
          extra={(
            <FilterChips
              label="Invite email"
              value={inviteFilter}
              options={['All', 'Email sent', 'Not sent']}
              onChange={setInviteFilter}
            />
          )}
          onClear={clearAdvancedFilters}
        />
      </div>

      {error && (
        <div className="card bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm px-4 py-3">
          {error}
        </div>
      )}

      <div className="grid lg:grid-cols-5 gap-5">
        <div className="lg:col-span-2 card p-0 overflow-hidden flex flex-col min-h-[28rem]">
            <div className="px-5 py-4 border-b border-col flex items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-col">{activeTabLabel}</h3>
              <p className="text-xs text-muted mt-0.5">
                {filteredCandidates.length} candidate{filteredCandidates.length !== 1 ? 's' : ''}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                {candidates.length} total
              </span>
            </div>
          </div>

          {loading ? (
            <LoadingSpinner message="Loading candidates..." />
          ) : filteredCandidates.length === 0 ? (
            <EmptyState
              icon={ClipboardList}
              title="No candidates found"
              description={
                search || activeFilterCount > 0
                  ? 'Try a different search term, clear filters, or switch tabs.'
                  : 'No candidates in this category yet.'
              }
            />
          ) : (
            <ul className="divide-y divide-col overflow-y-auto flex-1">
              {filteredCandidates.map((candidate, index) => {
                const selected = selectedId === candidate.candidate_id;
                const score = Math.round(candidate.resume_score || 0);
                return (
                  <motion.li
                    key={candidate.candidate_id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.03 }}
                  >
                    <button
                      type="button"
                      onClick={() => loadDetail(candidate.candidate_id)}
                      className={`w-full text-left px-4 py-3.5 transition-all ${
                        selected
                          ? 'bg-blue-50/80 dark:bg-blue-900/20 border-l-4 border-l-blue-600'
                          : 'hover:bg-slate-50 dark:hover:bg-slate-800/50 border-l-4 border-l-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className="w-10 h-10 rounded-xl flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                          style={{ background: avatarColor(candidate.full_name) }}
                        >
                          {getInitials(candidate.full_name)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-col truncate">{candidate.full_name}</p>
                          <p className="text-xs text-muted truncate flex items-center gap-1 mt-0.5">
                            <Mail size={11} className="flex-shrink-0" />
                            {displayContactEmail(candidate)}
                          </p>
                          <p className="text-xs text-muted truncate mt-0.5">
                            {candidate.job_position || 'Open role'}
                          </p>
                        </div>
                        <div className="flex flex-col items-end gap-1 flex-shrink-0">
                          <MatchScore score={score} size="md" />
                          {candidate.interview_scheduled && (
                            <span className="text-[10px] font-medium text-blue-600 bg-blue-50 dark:bg-blue-900/30 px-1.5 py-0.5 rounded-full">
                              Booked
                            </span>
                          )}
                          {activeTab === 'shortlisted' && !candidate.interview_scheduled ? (
                            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                              candidate.invite_sent
                                ? 'text-green-700 bg-green-50 dark:bg-green-900/30 dark:text-green-300'
                                : 'text-amber-700 bg-amber-50 dark:bg-amber-900/30 dark:text-amber-300'
                            }`}>
                              {candidate.invite_sent ? 'Email sent' : 'Not sent'}
                            </span>
                          ) : null}
                        </div>
                      </div>
                    </button>
                  </motion.li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="lg:col-span-3 card p-0 overflow-hidden min-h-[28rem] flex flex-col">
          {!selectedId ? (
            <EmptyState
              icon={User}
              title="Select a candidate"
              description="Choose someone from the list to review their resume, job description, and take action."
            />
          ) : detailLoading ? (
            <LoadingSpinner message="Loading candidate details..." />
          ) : detail ? (
            <>
              <div className="px-6 py-5 border-b border-col bg-gradient-to-br from-blue-50 to-slate-50 dark:from-blue-900/10 dark:to-slate-800/20">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="flex items-center gap-4 min-w-0">
                    <div
                      className="w-14 h-14 rounded-2xl flex items-center justify-center text-white font-bold text-lg flex-shrink-0"
                      style={{ background: avatarColor(detail.full_name) }}
                    >
                      {getInitials(detail.full_name)}
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-lg font-bold text-col truncate">{detail.full_name}</h3>
                      <p className="text-sm text-muted truncate">{displayContactEmail(detail)}</p>
                      <p className="text-xs text-muted mt-0.5">{detail.candidate_id}</p>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <div className="flex items-center gap-4">
                      <StatusBadge status={mapBackendStatus(detail.status)} />
                      <MatchScore score={Math.round(detail.resume_score || 0)} size="lg" />
                    </div>
                    {detail.can_edit_email ? (
                      <form
                        onSubmit={handleSaveEmail}
                        className="flex items-center gap-1.5"
                      >
                        <input
                          type="email"
                          value={emailDraft}
                          onChange={(e) => setEmailDraft(e.target.value)}
                          placeholder={detail.email_missing ? 'Add email' : 'Edit email'}
                          disabled={emailSaving}
                          className="w-40 h-7 px-2 text-[11px] rounded-md border border-col bg-white/90 dark:bg-slate-900/70 text-col placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
                        />
                        <button
                          type="submit"
                          title="Save email"
                          disabled={emailSaving || !emailDraft.trim()}
                          className="h-7 w-7 inline-flex items-center justify-center rounded-md border border-col text-muted hover:text-col hover:bg-white dark:hover:bg-slate-800 disabled:opacity-40"
                        >
                          <Save size={13} />
                        </button>
                      </form>
                    ) : null}
                  </div>
                </div>
                <p className="text-sm text-muted mt-3">{detail.job_position || 'Open position'}</p>
              </div>

              <div className="p-6 space-y-5 overflow-y-auto flex-1">
                {detail.final_recommendation && (
                  <div className="rounded-xl border border-blue-100 dark:border-blue-900/40 bg-blue-50/60 dark:bg-blue-900/10 px-4 py-3 text-sm text-col leading-relaxed">
                    {detail.final_recommendation}
                  </div>
                )}

                {evaluationDetail && <EvaluationDetailPanels data={evaluationDetail} />}

                {(detail.jd_text || detail.jd_file_url) && (
                  <SectionCard
                    title="Job description"
                    action={
                      detail.jd_file_url ? (
                        <a
                          href={getScreeningFileUrl(detail.jd_file_url)}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700"
                        >
                          <ExternalLink size={12} />
                          Open file
                        </a>
                      ) : null
                    }
                  >
                    <pre className="text-xs whitespace-pre-wrap max-h-36 overflow-y-auto text-muted leading-relaxed">
                      {detail.jd_text}
                    </pre>
                  </SectionCard>
                )}

                {resumeText && (
                  <SectionCard
                    title="Resume"
                    action={
                      detail.resume_file_url ? (
                        <a
                          href={getScreeningFileUrl(detail.resume_file_url)}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700"
                        >
                          <FileText size={12} />
                          Open file
                        </a>
                      ) : null
                    }
                  >
                    <pre className="text-xs whitespace-pre-wrap max-h-44 overflow-y-auto text-muted leading-relaxed">
                      {resumeText}
                    </pre>
                  </SectionCard>
                )}

                {actionMessage && (
                  <div
                    className={`text-sm rounded-xl px-4 py-3 ${
                      actionMessage.type === 'success'
                        ? 'bg-green-50 text-green-800 border border-green-200 dark:bg-green-900/20 dark:text-green-300 dark:border-green-800'
                        : 'bg-red-50 text-red-800 border border-red-200 dark:bg-red-900/20 dark:text-red-300 dark:border-red-800'
                    }`}
                  >
                    {actionMessage.text}
                  </div>
                )}
              </div>

              <div className="px-6 py-4 border-t border-col bg-slate-50/50 dark:bg-slate-800/30 flex flex-wrap gap-3">
                {detail.status === 'NEEDS_REVIEW' && (
                  <>
                    <button
                      type="button"
                      onClick={handleShortlist}
                      disabled={actionLoading || detail.email_missing}
                      className="btn-primary inline-flex items-center gap-2 px-4 py-2.5 text-sm"
                    >
                      <Send size={15} />
                      {actionLoading ? 'Processing…' : 'Shortlist & Send Invite'}
                    </button>
                    {detail.email_missing ? (
                      <p className="text-sm text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl px-4 py-2.5">
                        Add a contact email above before sending the invite.
                      </p>
                    ) : null}
                    <button
                      type="button"
                      onClick={handleReject}
                      disabled={actionLoading}
                      className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl border border-red-200 text-red-600 hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-900/20 disabled:opacity-50"
                    >
                      <XCircle size={15} />
                      {actionLoading ? 'Processing…' : 'Reject'}
                    </button>
                  </>
                )}

                {detail.status === 'SHORTLISTED' && (
                  <>
                    {detail.can_resend_invite ? (
                      <button
                        type="button"
                        onClick={handleResend}
                        disabled={actionLoading}
                        className="btn-primary inline-flex items-center gap-2 px-4 py-2.5 text-sm"
                      >
                        <Mail size={15} />
                        {actionLoading ? 'Sending…' : 'Resend Scheduling Email'}
                      </button>
                    ) : (
                      <p className="text-sm text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl px-4 py-2.5">
                        {detail.email_missing
                          ? 'Add a contact email above to send the scheduling invite.'
                          : detail.interview_scheduled || detail.invite_used
                            ? 'This candidate already booked a slot — a new scheduling email cannot be sent.'
                            : 'Scheduling email cannot be resent for this candidate.'}
                      </p>
                    )}
                    {canReject && (
                      <button
                        type="button"
                        onClick={handleReject}
                        disabled={actionLoading}
                        className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl border border-red-200 text-red-600 hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-900/20 disabled:opacity-50"
                      >
                        <XCircle size={15} />
                        {actionLoading ? 'Processing…' : 'Reject'}
                      </button>
                    )}
                  </>
                )}

                {detail.status === 'REJECTED' && (
                  <p className="text-sm text-muted">Rejected candidates are kept for reference only.</p>
                )}

                {detail.status === 'INTERVIEW_SCHEDULED' && (
                  <p className="text-sm text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl px-4 py-2.5">
                    Interview already scheduled. Check the Calendar page for date and time.
                  </p>
                )}

                {detail.status === 'INTERVIEW_COMPLETED' && (
                  <p className="text-sm text-teal-700 dark:text-teal-300 bg-teal-50 dark:bg-teal-900/20 border border-teal-200 dark:border-teal-800 rounded-xl px-4 py-2.5">
                    This candidate has completed the interview.
                  </p>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
