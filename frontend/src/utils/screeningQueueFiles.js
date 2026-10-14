/** In-memory File blobs for queue jobs (cannot go in localStorage). */

const store = new Map();

export function setJobFiles(jobId, { resumeFiles = [], jdFile = null } = {}) {
  store.set(String(jobId), {
    resumeFiles: Array.isArray(resumeFiles) ? resumeFiles : [],
    jdFile: jdFile || null,
  });
}

export function getJobFiles(jobId) {
  return store.get(String(jobId)) || { resumeFiles: [], jdFile: null };
}

export function clearJobFiles(jobId) {
  store.delete(String(jobId));
}

export function hasJobFiles(jobId) {
  const entry = getJobFiles(jobId);
  return Boolean(entry.resumeFiles?.length);
}
