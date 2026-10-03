export function normalizeQuery(query) {
  return String(query || '').trim().toLowerCase();
}

export function matchesCandidate(candidate, query) {
  const q = normalizeQuery(query);
  if (!q) return true;
  return (
    candidate.name?.toLowerCase().includes(q) ||
    candidate.email?.toLowerCase().includes(q) ||
    candidate.appliedJob?.toLowerCase().includes(q) ||
    candidate.candidateId?.toLowerCase().includes(q) ||
    candidate.phone?.toLowerCase().includes(q) ||
    candidate.skills?.some((skill) => skill.toLowerCase().includes(q))
  );
}

export function matchesJob(job, query) {
  const q = normalizeQuery(query);
  if (!q) return true;
  return (
    job.title?.toLowerCase().includes(q) ||
    job.department?.toLowerCase().includes(q) ||
    job.location?.toLowerCase().includes(q) ||
    job.skills?.some((skill) => skill.toLowerCase().includes(q))
  );
}

export function filterCandidates(candidates, query) {
  return candidates.filter((candidate) => matchesCandidate(candidate, query));
}

export function filterJobs(jobs, query) {
  return jobs.filter((job) => matchesJob(job, query));
}
