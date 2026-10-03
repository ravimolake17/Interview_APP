import { motion } from 'framer-motion';
import { cn, getScoreColor, statusConfig, recommendationConfig, getInitials, getAvatarGradient } from '@/utils/helpers';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

// ─── StatsCard ──────────────────────────────────────────────────────────────
export function StatsCard({ label, value, icon: Icon, trend, trendValue, color = 'blue', delay = 0 }) {
  const colors = {
    blue: 'from-blue-500 to-primary-600',
    green: 'from-emerald-500 to-teal-600',
    amber: 'from-amber-500 to-orange-600',
    red: 'from-red-500 to-rose-600',
    violet: 'from-violet-500 to-purple-600',
    indigo: 'from-indigo-500 to-blue-700',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
      className="card p-5 hover:shadow-card-hover transition-shadow duration-200"
    >
      <div className="flex items-start justify-between mb-4">
        <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${colors[color]} flex items-center justify-center shadow-sm`}>
          <Icon size={18} className="text-white" />
        </div>
        {trend !== undefined && (
          <div className={cn('flex items-center gap-0.5 text-xs font-medium',
            trend > 0 ? 'text-green-600 dark:text-green-400' :
            trend < 0 ? 'text-red-600 dark:text-red-400' :
            'text-slate-400'
          )}>
            {trend > 0 ? <TrendingUp size={13} /> : trend < 0 ? <TrendingDown size={13} /> : <Minus size={13} />}
            {trendValue || `${Math.abs(trend)}%`}
          </div>
        )}
      </div>
      <p className="text-2xl font-bold text-slate-900 dark:text-white tabular-nums">{value}</p>
      <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">{label}</p>
    </motion.div>
  );
}

// ─── PageHeader ─────────────────────────────────────────────────────────────
export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">{title}</h2>
        {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </div>
  );
}

// ─── SkillBadge ─────────────────────────────────────────────────────────────
export function SkillBadge({ skill, variant = 'default', size = 'sm' }) {
  const cls = {
    default: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300',
    primary: 'bg-primary-50 dark:bg-primary-950/30 text-primary-700 dark:text-primary-400',
    missing: 'bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 border border-red-100 dark:border-red-900/50',
    success: 'bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-400',
  };

  return (
    <span className={cn('badge', cls[variant], size === 'xs' ? 'text-[10px] px-2 py-0' : '')}>
      {skill}
    </span>
  );
}

// ─── StatusBadge ────────────────────────────────────────────────────────────
export function StatusBadge({ status }) {
  const config = statusConfig[status] || statusConfig.pending;
  return <span className={config.classes}>{config.label}</span>;
}

// ─── RecommendationBadge ────────────────────────────────────────────────────
export function RecommendationBadge({ recommendation }) {
  const config = recommendationConfig[recommendation] || recommendationConfig['Not Recommended'];
  return (
    <span className={cn('badge text-xs font-medium px-2.5 py-1 rounded-lg', config.classes)}>
      {recommendation}
    </span>
  );
}

// ─── MatchScoreRing ─────────────────────────────────────────────────────────
export function MatchScoreRing({ score, size = 80 }) {
  const colors = getScoreColor(score);
  const radius = (size - 10) / 2;
  const circ = 2 * Math.PI * radius;
  const offset = circ - (score / 100) * circ;

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="currentColor" strokeWidth={5} className="text-slate-100 dark:text-slate-800" />
        <motion.circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={colors.ring} strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, delay: 0.3, ease: 'easeOut' }}
        />
      </svg>
      <span className={cn('absolute text-sm font-bold tabular-nums', colors.text)}>{score}%</span>
    </div>
  );
}

// ─── MatchScoreBar ──────────────────────────────────────────────────────────
export function MatchScoreBar({ score, label, showValue = true }) {
  const colors = getScoreColor(score);
  return (
    <div className="space-y-1.5">
      {label && (
        <div className="flex justify-between items-center">
          <span className="text-xs text-slate-600 dark:text-slate-400">{label}</span>
          {showValue && <span className={cn('text-xs font-semibold', colors.text)}>{score}%</span>}
        </div>
      )}
      <div className="h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: colors.ring }}
          initial={{ width: 0 }}
          animate={{ width: `${score}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </div>
    </div>
  );
}

// ─── CandidateAvatar ────────────────────────────────────────────────────────
export function CandidateAvatar({ name, size = 'md' }) {
  const sizes = { sm: 'w-7 h-7 text-xs', md: 'w-9 h-9 text-sm', lg: 'w-12 h-12 text-base', xl: 'w-16 h-16 text-xl' };
  const gradient = getAvatarGradient(name);
  return (
    <div className={cn('rounded-full bg-gradient-to-br flex items-center justify-center text-white font-semibold shrink-0', gradient, sizes[size])}>
      {getInitials(name)}
    </div>
  );
}

// ─── ProgressBar ────────────────────────────────────────────────────────────
export function ProgressBar({ progress, label, color = 'primary' }) {
  const colors = {
    primary: 'bg-primary-600',
    green: 'bg-green-500',
    amber: 'bg-amber-500',
  };
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-500">
        {label && <span>{label}</span>}
        <span className="font-medium">{progress}%</span>
      </div>
      <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
        <motion.div
          className={cn('h-full rounded-full', colors[color])}
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
    </div>
  );
}

// ─── EmptyState ─────────────────────────────────────────────────────────────
export function EmptyState({ icon: Icon, title, message, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-14 h-14 bg-slate-100 dark:bg-slate-800 rounded-2xl flex items-center justify-center mb-4">
        <Icon size={24} className="text-slate-400" />
      </div>
      <h3 className="font-semibold text-slate-700 dark:text-slate-300 mb-1">{title}</h3>
      <p className="text-sm text-slate-500 dark:text-slate-500 max-w-xs">{message}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

// ─── LoadingOverlay ─────────────────────────────────────────────────────────
export function LoadingOverlay({ message = 'Processing…' }) {
  return (
    <div className="fixed inset-0 bg-black/20 dark:bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="card p-8 flex flex-col items-center gap-4 shadow-dropdown">
        <div className="relative w-12 h-12">
          <div className="absolute inset-0 rounded-full border-2 border-primary-200 dark:border-primary-900" />
          <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-primary-600 animate-spin" />
        </div>
        <p className="text-sm font-medium text-slate-700 dark:text-slate-300">{message}</p>
      </div>
    </div>
  );
}

// ─── SkeletonCard ────────────────────────────────────────────────────────────
export function SkeletonCard({ lines = 3 }) {
  return (
    <div className="card p-5 space-y-3">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl shimmer" />
        <div className="flex-1 space-y-2">
          <div className="h-3.5 rounded-full shimmer w-2/3" />
          <div className="h-3 rounded-full shimmer w-1/3" />
        </div>
      </div>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className={`h-3 rounded-full shimmer ${i === lines - 1 ? 'w-1/2' : 'w-full'}`} />
      ))}
    </div>
  );
}

// ─── SectionTitle ────────────────────────────────────────────────────────────
export function SectionTitle({ children, action }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h3 className="font-semibold text-slate-800 dark:text-slate-200 text-sm">{children}</h3>
      {action}
    </div>
  );
}

// ─── Divider ────────────────────────────────────────────────────────────────
export function Divider() {
  return <div className="h-px bg-slate-100 dark:bg-slate-800 my-4" />;
}

// ─── Tooltip (simple) ───────────────────────────────────────────────────────
export function Tooltip({ children, text }) {
  return (
    <div className="relative group inline-flex">
      {children}
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1 bg-slate-900 dark:bg-slate-700 text-white text-[10px] rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
        {text}
      </div>
    </div>
  );
}
