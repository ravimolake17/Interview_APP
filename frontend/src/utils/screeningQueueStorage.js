const STORAGE_KEY = 'rr-parkon-screening-queue';
const MAX_JOBS = 30;

function storageKey(userId) {
  return userId ? `${STORAGE_KEY}-${userId}` : `${STORAGE_KEY}-guest`;
}

/** Persistable snapshot — never store File blobs. */
export function serializeQueueJobs(jobs) {
  return (jobs || [])
    .slice(-MAX_JOBS)
    .map((job) => ({
      id: job.id,
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

export function normalizeRestoredJobs(jobs) {
  return (Array.isArray(jobs) ? jobs : []).map((job) => {
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

export function loadScreeningQueue(userId) {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) return { jobs: [], panelOpen: false };
    const parsed = JSON.parse(raw);
    const jobs = normalizeRestoredJobs(parsed.jobs || parsed || []);
    return {
      jobs,
      panelOpen: Boolean(parsed.panelOpen) && jobs.length > 0,
    };
  } catch {
    return { jobs: [], panelOpen: false };
  }
}

export function saveScreeningQueue(userId, { jobs, panelOpen }) {
  try {
    localStorage.setItem(
      storageKey(userId),
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
