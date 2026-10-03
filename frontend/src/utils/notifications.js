const DISMISSED_KEY = 'rr-parkon-dismissed-notifications';

const AUDIT_ACTIONS = new Set([
  'RESUME_EVALUATED',
  'CANDIDATE_SHORTLISTED',
  'CANDIDATE_REJECTED',
  'INVITE_RESENT',
  'INTERVIEW_INVITE_SENT',
  'INTERVIEW_SCHEDULED',
  'JOB_CREATED',
  'JOB_UPDATED',
  'JOB_DELETED',
]);

function storageKey(userId) {
  return userId ? `${DISMISSED_KEY}-${userId}` : `${DISMISSED_KEY}-guest`;
}

export function loadDismissedIds(userId) {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    return new Set(JSON.parse(raw || '[]'));
  } catch {
    return new Set();
  }
}

export function saveDismissedIds(userId, ids) {
  localStorage.setItem(storageKey(userId), JSON.stringify([...ids]));
}

export function formatRelativeTime(dateInput) {
  if (!dateInput) return 'Recently';
  const date = new Date(dateInput);
  if (Number.isNaN(date.getTime())) return 'Recently';

  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return date.toLocaleDateString();
}

function routeForAuditEntry(entry) {
  const candidateId = entry.entity_id;

  switch (entry.action) {
    case 'JOB_CREATED':
    case 'JOB_UPDATED':
    case 'JOB_DELETED':
      return '/jobs';
    case 'RESUME_EVALUATED':
      return candidateId ? `/candidates/${encodeURIComponent(candidateId)}` : '/candidates';
    case 'CANDIDATE_SHORTLISTED':
    case 'INVITE_RESENT':
    case 'INTERVIEW_INVITE_SENT':
      return candidateId
        ? `/candidates/${encodeURIComponent(candidateId)}`
        : '/hr-review';
    case 'CANDIDATE_REJECTED':
      return candidateId
        ? `/candidates/${encodeURIComponent(candidateId)}`
        : '/hr-review';
    case 'INTERVIEW_SCHEDULED':
      return candidateId
        ? `/candidates/${encodeURIComponent(candidateId)}`
        : '/calendar';
    case 'INTERVIEW_BLUEPRINT_GENERATED':
      return candidateId ? `/candidates/${encodeURIComponent(candidateId)}` : '/candidates';
    default:
      return null;
  }
}

function textForAuditEntry(entry) {
  if (entry.message) return entry.message;

  const name = entry.details?.candidate_name || entry.entity_id;
  const jobTitle = entry.details?.title;
  switch (entry.action) {
    case 'RESUME_EVALUATED':
      return `AI screening completed for ${name}`;
    case 'CANDIDATE_SHORTLISTED':
      return `${name} was shortlisted`;
    case 'CANDIDATE_REJECTED':
      return `${name} was rejected`;
    case 'INVITE_RESENT':
      return `Interview invite resent to ${name}`;
    case 'INTERVIEW_INVITE_SENT':
      return `Interview invite sent to ${name}`;
    case 'INTERVIEW_SCHEDULED':
      return `${name} booked an interview`;
    case 'JOB_CREATED':
      return `Job created: ${jobTitle || entry.entity_id}`;
    case 'JOB_UPDATED':
      return `Job updated: ${jobTitle || entry.entity_id}`;
    case 'JOB_DELETED':
      return `Job deleted: ${jobTitle || entry.entity_id}`;
    default:
      return entry.action.replace(/_/g, ' ').toLowerCase();
  }
}

function preferenceKeyForAction(action) {
  if (action === 'RESUME_EVALUATED') return 'ai_screening_complete';
  if (['CANDIDATE_SHORTLISTED', 'INVITE_RESENT', 'INTERVIEW_INVITE_SENT'].includes(action)) {
    return 'candidate_shortlisted';
  }
  if (action === 'INTERVIEW_SCHEDULED') return 'job_application_received';
  return 'new_candidate_uploaded';
}

function notificationFromCandidate(candidate) {
  const id = candidate.candidateId;
  const createdAt = candidate.createdAt || new Date().toISOString();
  const job = candidate.appliedJob && candidate.appliedJob !== 'Open Role'
    ? ` (${candidate.appliedJob})`
    : '';

  if (candidate.status === 'Interview Scheduled') {
    return {
      id: `candidate-${id}-interview`,
      text: `Interview scheduled for ${candidate.name}${job}`,
      createdAt,
      route: `/candidates?candidate=${encodeURIComponent(id)}`,
      preferenceKey: 'job_application_received',
    };
  }

  if (candidate.status === 'Shortlisted') {
    return {
      id: `candidate-${id}-shortlisted`,
      text: `${candidate.name} was shortlisted${job}`,
      createdAt,
      route: `/hr-review?candidate=${encodeURIComponent(id)}&tab=shortlisted`,
      preferenceKey: 'candidate_shortlisted',
    };
  }

  if (candidate.status === 'Rejected') {
    return {
      id: `candidate-${id}-rejected`,
      text: `${candidate.name} was rejected${job}`,
      createdAt,
      route: `/hr-review?candidate=${encodeURIComponent(id)}&tab=rejected`,
      preferenceKey: 'ai_screening_complete',
    };
  }

  if (candidate.matchScore > 0) {
    return {
      id: `candidate-${id}-screened`,
      text: `AI screening completed for ${candidate.name}${job}`,
      createdAt,
      route: `/candidates?candidate=${encodeURIComponent(id)}`,
      preferenceKey: 'ai_screening_complete',
    };
  }

  return {
    id: `candidate-${id}-uploaded`,
    text: `New resume uploaded for ${candidate.name}${job}`,
    createdAt,
    route: `/candidates?candidate=${encodeURIComponent(id)}`,
    preferenceKey: 'new_candidate_uploaded',
  };
}

export function buildNotifications({ auditEntries = [], candidates = [], isAdmin = false }) {
  const items = [];
  const seenCandidateKeys = new Set();

  if (isAdmin) {
    auditEntries.forEach((entry) => {
      if (!AUDIT_ACTIONS.has(entry.action)) return;
      const route = routeForAuditEntry(entry);
      if (!route) return;

      const preferenceKey = preferenceKeyForAction(entry.action);
      if (entry.entity_id) {
        seenCandidateKeys.add(`${entry.entity_id}:${preferenceKey}`);
      }

      items.push({
        id: `audit-${entry.id}`,
        text: textForAuditEntry(entry),
        createdAt: entry.created_at,
        time: formatRelativeTime(entry.created_at),
        route,
        preferenceKey,
        unread: true,
      });
    });
  }

  candidates.forEach((candidate) => {
    const notification = notificationFromCandidate(candidate);
    const key = `${candidate.candidateId}:${notification.preferenceKey}`;
    if (isAdmin && seenCandidateKeys.has(key)) return;

    items.push({
      ...notification,
      time: formatRelativeTime(notification.createdAt),
      unread: true,
    });
  });

  return items
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .slice(0, 15);
}

export function filterDismissedNotifications(notifications, dismissedIds) {
  return notifications.filter((notification) => !dismissedIds.has(notification.id));
}

export function filterNotificationPreferences(notifications, preferences = {}) {
  return notifications.filter(
    (notification) => preferences[notification.preferenceKey] !== false,
  );
}
