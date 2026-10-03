export function nextAvailableJobTitle(base, jobs = []) {
  const stem = String(base || 'Open Position').trim() || 'Open Position';
  const taken = new Set(
    (jobs || []).map((job) => String(job.title || '').trim().toLowerCase()).filter(Boolean),
  );
  if (!taken.has(stem.toLowerCase())) return stem;
  let index = 2;
  while (taken.has(`${stem} (${index})`.toLowerCase())) {
    index += 1;
  }
  return `${stem} (${index})`;
}

export function duplicateJobDetail(error) {
  const detail = error?.response?.data?.detail;
  if (detail && typeof detail === 'object' && detail.code === 'JOB_DUPLICATE') {
    return detail;
  }
  return null;
}
