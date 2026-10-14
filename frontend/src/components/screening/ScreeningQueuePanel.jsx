import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Eye,
  Loader2,
  Mail,
  MailX,
  RotateCcw,
  Trash2,
  X,
  XCircle,
} from 'lucide-react';
import { useScreeningQueue } from '../../context/ScreeningQueueContext';
import { CandidateResultCard } from './CandidateResultCard';
import EmptyState from '../ui/EmptyState';

function statusIcon(status) {
  if (status === 'processing') {
    return <Loader2 size={14} className="animate-spin text-orange-500" />;
  }
  if (status === 'completed') {
    return <CheckCircle2 size={14} className="text-emerald-500" />;
  }
  if (status === 'failed') {
    return <XCircle size={14} className="text-red-500" />;
  }
  return <Loader2 size={14} className="text-slate-400" />;
}

function statusLabel(status) {
  if (status === 'queued') return 'Queued';
  if (status === 'processing') return 'Running';
  if (status === 'completed') return 'Done';
  if (status === 'failed') return 'Failed';
  return status;
}

function ResultsPreviewModal({ job, onClose, onRetry, canRetry }) {
  if (!job) return null;
  const results = Array.isArray(job.results) ? job.results : [];
  const avg = results.length
    ? Math.round(results.reduce((sum, row) => sum + (row.matchScore || 0), 0) / results.length)
    : 0;
  const highlyRecommended = results.filter((row) => (row.matchScore || 0) >= 80).length;

  return (
    <div className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm flex items-stretch justify-center p-3 sm:p-6">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 12 }}
        className="w-full max-w-6xl max-h-full overflow-hidden rounded-2xl border border-col bg-[var(--color-bg)] shadow-2xl flex flex-col"
      >
        <div className="flex items-start justify-between gap-3 border-b border-col px-5 py-4 bg-white/90 dark:bg-slate-900/90">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              {job.status === 'failed' ? 'Failed screening job' : 'Screening results'}
            </p>
            <h2 className="text-lg font-bold text-col truncate mt-0.5">{job.label}</h2>
            <p className="text-sm text-muted mt-1">
              {results.length} candidate{results.length === 1 ? '' : 's'} analysed
              {results.length > 0 ? ` · Avg score: ${avg}% · ${highlyRecommended} highly recommended` : ''}
              {job.status === 'failed' && job.error ? ` · ${job.error}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {canRetry && (
              <button
                type="button"
                onClick={() => {
                  onRetry?.(job.id);
                  onClose();
                }}
                className="inline-flex items-center gap-1.5 rounded-xl bg-orange-500 px-3 py-2 text-sm font-semibold text-white hover:bg-orange-600"
                title="Retry this screening job"
              >
                <RotateCcw size={15} />
                Retry
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-col p-2 text-muted hover:text-col hover:bg-slate-50 dark:hover:bg-slate-800"
              title="Close preview"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {job.status === 'completed' && results.length > 0 ? (
            <>
              <div className="card p-5 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/10 dark:to-emerald-900/10 border-green-100 dark:border-green-800">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                    <CheckCircle2 size={20} className="text-green-500" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-col">Screening Complete</h3>
                    <p className="text-sm text-muted">
                      {results.length} candidates analysed · Avg score: {avg}% · {highlyRecommended} highly recommended
                    </p>
                  </div>
                </div>
              </div>
              {results.map((candidate, index) => (
                <CandidateResultCard key={candidate.id || index} candidate={candidate} delay={index * 0.05} />
              ))}
            </>
          ) : (
            <div className="space-y-4">
              <EmptyState
                icon={XCircle}
                title={job.status === 'failed' ? 'Screening failed' : 'No results'}
                description={job.error || 'This queue job has no screening results to preview.'}
              />
              {job.status === 'failed' && (
                <div className="card p-4 border-col">
                  <p className="text-sm text-muted">
                    {canRetry
                      ? 'Files are still available in this browser session. Click Retry to put this job back at the front of the queue (JD parse/store runs again when it processes).'
                      : 'Uploaded files are no longer in memory (usually after a full page refresh). This failed entry stays in the queue for reference — add the screening again with the same files to re-run it.'}
                  </p>
                  {canRetry && (
                    <button
                      type="button"
                      onClick={() => {
                        onRetry?.(job.id);
                        onClose();
                      }}
                      className="mt-3 inline-flex items-center gap-1.5 rounded-xl bg-orange-500 px-3 py-2 text-sm font-semibold text-white hover:bg-orange-600"
                    >
                      <RotateCcw size={15} />
                      Retry screening
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
          {job.failures?.length > 0 && (
            <div className="card p-4 border-amber-200 dark:border-amber-900/40 bg-amber-50/70 dark:bg-amber-900/10">
              <p className="text-sm font-semibold text-col mb-2">Partial failures</p>
              <ul className="space-y-1 text-sm text-muted">
                {job.failures.map((item) => (
                  <li key={`${item.name}-${item.message}`}>
                    <span className="font-medium text-col">{item.name}</span>: {item.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}

export default function ScreeningQueuePanel() {
  const {
    jobs,
    panelOpen,
    setPanelOpen,
    activeCount,
    totalCount,
    dismissJob,
    clearFinished,
    retryJob,
    canRetryJob,
  } = useScreeningQueue();
  const [previewJobId, setPreviewJobId] = useState(null);

  if (!totalCount) return null;

  const previewJob = jobs.find((job) => job.id === previewJobId) || null;
  const canClearDone = activeCount === 0;

  const openPreview = (job) => {
    if (job.status !== 'completed' && job.status !== 'failed') return;
    setPreviewJobId(job.id);
  };

  return (
    <>
      <div className="fixed right-0 top-1/2 -translate-y-1/2 z-40 flex items-stretch">
        <button
          type="button"
          onClick={() => setPanelOpen((open) => !open)}
          className="flex flex-col items-center justify-center gap-2 self-center rounded-l-xl border border-r-0 border-col bg-white dark:bg-slate-900 px-2 py-3 shadow-lg hover:bg-slate-50 dark:hover:bg-slate-800"
          title={panelOpen ? 'Hide screening queue' : 'Show screening queue'}
          aria-expanded={panelOpen}
        >
          {panelOpen ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          <span
            className="text-[10px] font-bold uppercase tracking-wide text-muted"
            style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
          >
            Queue
          </span>
          <span className="min-w-[1.5rem] rounded-full bg-orange-500 px-1.5 py-0.5 text-center text-[11px] font-bold text-white">
            {activeCount || totalCount}
          </span>
        </button>

        <AnimatePresence initial={false}>
          {panelOpen && (
            <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 320, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden border border-col bg-white dark:bg-slate-900 shadow-xl"
            >
              <div className="w-80 h-[min(70vh,520px)] flex flex-col">
                <div className="flex items-start justify-between gap-2 border-b border-col px-4 py-3">
                  <div>
                    <p className="text-sm font-semibold text-col">Screening queue</p>
                    <p className="text-xs text-muted mt-0.5">
                      {activeCount} active · {totalCount} total
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={clearFinished}
                    disabled={!canClearDone}
                    title={
                      canClearDone
                        ? 'Remove completed jobs (failed jobs stay for preview / retry)'
                        : 'Wait until all queue jobs finish before clearing'
                    }
                    className={`text-xs font-medium ${
                      canClearDone
                        ? 'text-muted hover:text-col'
                        : 'text-slate-300 dark:text-slate-600 cursor-not-allowed'
                    }`}
                  >
                    Clear done
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto p-3 space-y-2">
                  {jobs.map((job) => {
                    const canPreview = job.status === 'completed' || job.status === 'failed';
                    return (
                      <div
                        key={job.id}
                        role={canPreview ? 'button' : undefined}
                        tabIndex={canPreview ? 0 : undefined}
                        onClick={() => openPreview(job)}
                        onKeyDown={(event) => {
                          if (!canPreview) return;
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            openPreview(job);
                          }
                        }}
                        className={`rounded-xl border border-col bg-slate-50/80 dark:bg-slate-800/40 px-3 py-2.5 text-left w-full ${
                          canPreview
                            ? 'cursor-pointer hover:border-orange-300 hover:bg-orange-50/40 dark:hover:bg-orange-950/20'
                            : ''
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          <div className="mt-0.5">{statusIcon(job.status)}</div>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-col truncate">{job.label}</p>
                            <p className="text-[11px] text-muted mt-0.5">
                              {statusLabel(job.status)} · {job.resumeCount} resume
                              {job.resumeCount === 1 ? '' : 's'}
                            </p>
                            <div className="mt-1.5 flex flex-wrap gap-1.5">
                              <span className="inline-flex items-center gap-1 rounded-full bg-white dark:bg-slate-900 border border-col px-2 py-0.5 text-[10px] text-muted">
                                {job.sendInviteEmail ? <Mail size={10} /> : <MailX size={10} />}
                                {job.sendInviteEmail ? 'Email on' : 'Email off'}
                              </span>
                              <span className="inline-flex items-center rounded-full bg-white dark:bg-slate-900 border border-col px-2 py-0.5 text-[10px] text-muted capitalize">
                                {job.jdMode === 'saved'
                                  ? 'Saved JD'
                                  : job.jdMode === 'upload'
                                    ? 'Uploaded JD'
                                    : 'Pasted JD'}
                              </span>
                              {(job.status === 'completed' || job.status === 'failed') && (
                                <span className="inline-flex items-center gap-1 rounded-full bg-white dark:bg-slate-900 border border-col px-2 py-0.5 text-[10px] text-orange-600">
                                  <Eye size={10} /> Preview
                                </span>
                              )}
                            </div>
                            {job.progress && (
                              <p className="text-[11px] text-muted mt-1.5 leading-snug">{job.progress}</p>
                            )}
                            {job.error && (
                              <p className="text-[11px] text-red-600 mt-1 leading-snug">{job.error}</p>
                            )}
                          </div>
                          <div className="flex flex-col items-center gap-1">
                            {canRetryJob(job) && (
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  retryJob(job.id);
                                }}
                                className="text-orange-600 hover:text-orange-700 p-0.5"
                                title="Retry this job"
                              >
                                <RotateCcw size={13} />
                              </button>
                            )}
                            {(job.status === 'completed' || job.status === 'failed') && (
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  dismissJob(job.id);
                                }}
                                className="text-muted hover:text-red-500 p-0.5"
                                title="Remove from list"
                              >
                                <Trash2 size={13} />
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {previewJob && (
          <ResultsPreviewModal
            job={previewJob}
            onClose={() => setPreviewJobId(null)}
            onRetry={retryJob}
            canRetry={canRetryJob(previewJob)}
          />
        )}
      </AnimatePresence>
    </>
  );
}
