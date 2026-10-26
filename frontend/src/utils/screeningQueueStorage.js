const STORAGE_KEY = 'rr-parkon-screening-queue';
const MAX_JOBS = 30;

function storageKey(userId, companyId) {
  const userPart = userId ? String(userId) : 'guest';
  const companyPart = companyId ? `c${companyId}` : 'c0';
  return `${STORAGE_KEY}-${userPart}-${companyPart}`;
}

/** Persistable snapshot — never store File blobs. */
export function serializeQueueJobs(jobs) {
  return (jobs || [])
    .slice(-MAX_JOBS)
    .map((job) => ({
      id: job.id,
      companyId: job.companyId ?? null,
      createdAt: job.createdAt,
      label: job.label,
      resumeCount: job.resumeCount,
      sendInviteEmail: Boolean(job.sendInviteEmail),
      storeJd: Boolean(job.storeJd),
      jdMode: job.jdMode || 'saved',
      status: job.status,
      progress: job.progress || '',
      results: Array.isArray(job.results) ? job.results : [],
      failures: Array.isArray(job.failures) ? job.failures : [],
      error: job.error || null,
      // Keep JD metadata for preview after refresh (File blobs cannot be restored).
      selectedJob: job.selectedJob || null,
      jdText: job.jdText || '',
      hasLocalFiles: false,
    }));
}

export function normalizeRestoredJobs(jobs, companyId = null) {
  const wanted = companyId != null ? Number(companyId) : null;
  return (Array.isArray(jobs) ? jobs : [])
    .filter((job) => {
      if (wanted == null || !Number.isFinite(wanted)) return true;
      const jobCompany = job.companyId != null ? Number(job.companyId) : null;
      // Legacy rows without companyId stay only in the unscoped bucket (c0).
      if (jobCompany == null) return wanted === 0;
      return jobCompany === wanted;
    })
    .map((job) => {
      const wasInFlight = job.status === 'queued' || job.status === 'processing';
      const base = {
        ...job,
        preparedJd: null,
        hasLocalFiles: false,
      };
      if (!wasInFlight) {
        return base;
      }
      // Files cannot survive a refresh — keep the entry as failed for audit / preview.
      return {
        ...base,
        status: 'failed',
        progress: 'Interrupted — kept in queue',
        error:
          job.error
          || 'This screening was interrupted (page refresh). Entry kept in queue for reference — re-add the files to run again.',
      };
    });
}

export function loadScreeningQueue(userId, companyId = null) {
  try {
    const raw = localStorage.getItem(storageKey(userId, companyId));
    if (!raw) return { jobs: [], panelOpen: false };
    const parsed = JSON.parse(raw);
    const jobs = normalizeRestoredJobs(parsed.jobs || parsed || [], companyId);
    return {
      jobs,
      panelOpen: Boolean(parsed.panelOpen) && jobs.length > 0,
    };
  } catch {
    return { jobs: [], panelOpen: false };
  }
}

export function saveScreeningQueue(userId, companyId, { jobs, panelOpen }) {
  try {
    localStorage.setItem(
      storageKey(userId, companyId),
      JSON.stringify({
        jobs: serializeQueueJobs(jobs),
        panelOpen: Boolean(panelOpen),
        updatedAt: Date.now(),
      }),
    );
  } catch {
    // Quota / private mode — ignore; in-memory queue still works for the session.
  }
}
