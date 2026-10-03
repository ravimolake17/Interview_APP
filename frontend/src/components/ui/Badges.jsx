// ── Reusable Badge Components ───────────────────────────────────────────────

export function StatusBadge({ status }) {
  const map = {
    Active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    Draft: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
    Closed: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
    Shortlisted: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    Pending: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    'Needs Review': 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    Rejected: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
    'Interview Scheduled': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    'Interview Completed': 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${map[status] || map.Draft}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5 opacity-70" />
      {status}
    </span>
  );
}

export function ResultBadge({ result }) {
  if (!result) {
    return <span className="text-xs text-muted">—</span>;
  }
  const map = {
    Hire: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    Consider: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    Reject: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
    Hold: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${map[result] || map.Hold}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5 opacity-70" />
      {result}
    </span>
  );
}

export function SkillBadge({ skill, missing = false }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${
      missing
        ? 'bg-red-50 text-red-600 border border-red-200 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800'
        : 'bg-blue-50 text-blue-700 border border-blue-100 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-800'
    }`}>
      {missing && <span className="mr-1">✗</span>}
      {skill}
    </span>
  );
}

export function RecommendationBadge({ recommendation }) {
  const map = {
    'Highly Recommended': { cls: 'bg-green-500 text-white', dot: '★★★' },
    'Recommended': { cls: 'bg-blue-500 text-white', dot: '★★' },
    'Consider': { cls: 'bg-amber-500 text-white', dot: '★' },
    'Not Recommended': { cls: 'bg-red-500 text-white', dot: '✗' },
  };
  const r = map[recommendation] || map['Consider'];
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${r.cls}`}>
      <span className="text-xs">{r.dot}</span>
      {recommendation}
    </span>
  );
}

export function MatchScore({ score, size = 'md' }) {
  const color = score >= 85 ? '#22C55E' : score >= 70 ? '#F59E0B' : '#EF4444';
  const radius = size === 'lg' ? 26 : 18;
  const stroke = size === 'lg' ? 4 : 3;
  const dim = (radius + stroke) * 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: dim, height: dim }}>
      <svg width={dim} height={dim} className="-rotate-90">
        <circle cx={dim / 2} cy={dim / 2} r={radius} fill="none" stroke="#E2E8F0" strokeWidth={stroke} />
        <circle
          cx={dim / 2} cy={dim / 2} r={radius} fill="none"
          stroke={color} strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      <span className={`absolute font-bold ${size === 'lg' ? 'text-sm' : 'text-xs'}`} style={{ color }}>
        {score}%
      </span>
    </div>
  );
}
