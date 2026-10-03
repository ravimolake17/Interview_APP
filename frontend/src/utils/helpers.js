import { format, formatDistanceToNow, parseISO } from 'date-fns';
import { clsx } from 'clsx';

// Class name combiner
export function cn(...inputs) {
  return clsx(inputs);
}

// Format dates
export function formatDate(dateStr) {
  try {
    return format(parseISO(dateStr), 'MMM d, yyyy');
  } catch {
    return format(new Date(dateStr), 'MMM d, yyyy');
  }
}

export function formatRelative(dateStr) {
  try {
    return formatDistanceToNow(parseISO(dateStr), { addSuffix: true });
  } catch {
    return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
  }
}

// Match score color
export function getScoreColor(score) {
  if (score >= 85) return { text: 'text-green-600 dark:text-green-400', bg: 'bg-green-50 dark:bg-green-950/30', ring: '#22c55e' };
  if (score >= 70) return { text: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-950/30', ring: '#3b82f6' };
  if (score >= 55) return { text: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-950/30', ring: '#f59e0b' };
  return { text: 'text-red-600 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-950/30', ring: '#ef4444' };
}

// Status config
export const statusConfig = {
  active: { label: 'Active', classes: 'badge bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-400' },
  closed: { label: 'Closed', classes: 'badge bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400' },
  draft: { label: 'Draft', classes: 'badge bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400' },
  shortlisted: { label: 'Shortlisted', classes: 'badge bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-400' },
  rejected: { label: 'Rejected', classes: 'badge bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400' },
  under_review: { label: 'Under Review', classes: 'badge bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-400' },
  pending: { label: 'Pending', classes: 'badge bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400' },
};

// Recommendation badge
export const recommendationConfig = {
  'Strongly Recommended': { classes: 'bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-400 border border-green-100 dark:border-green-900/50' },
  'Recommended': { classes: 'bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-400 border border-blue-100 dark:border-blue-900/50' },
  'Recommended with Reservations': { classes: 'bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 border border-amber-100 dark:border-amber-900/50' },
  'Not Recommended': { classes: 'bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 border border-red-100 dark:border-red-900/50' },
};

// Initials from name
export function getInitials(name) {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
}

// Gradient for avatar
const GRADIENTS = [
  'from-violet-500 to-purple-600',
  'from-blue-500 to-cyan-600',
  'from-emerald-500 to-teal-600',
  'from-orange-500 to-amber-600',
  'from-pink-500 to-rose-600',
  'from-indigo-500 to-blue-600',
];

export function getAvatarGradient(name) {
  const idx = name.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % GRADIENTS.length;
  return GRADIENTS[idx];
}

// Share of a total as whole percents that always sum to 100.
export function wholePercentShares(items, { getCount = (item) => item.count, total } = {}) {
  const counts = items.map((item) => Number(getCount(item)) || 0);
  const denom = Number(total);
  const base = Number.isFinite(denom) && denom > 0
    ? denom
    : counts.reduce((sum, count) => sum + count, 0);
  if (!base) {
    return items.map((item) => ({ ...item, percent: 0 }));
  }

  const parts = counts.map((count, index) => {
    const raw = (count / base) * 100;
    const floor = Math.floor(raw);
    return { index, count, floor, remainder: raw - floor };
  });
  let leftover = 100 - parts.reduce((sum, part) => sum + part.floor, 0);
  [...parts]
    .filter((part) => part.count > 0)
    .sort((a, b) => b.remainder - a.remainder || b.count - a.count)
    .forEach((part) => {
      if (leftover <= 0) return;
      part.floor += 1;
      leftover -= 1;
    });

  const percentByIndex = new Map(parts.map((part) => [part.index, part.floor]));
  return items.map((item, index) => ({ ...item, percent: percentByIndex.get(index) ?? 0 }));
}

export function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Truncate text
export function truncate(str, length = 60) {
  if (!str) return '';
  return str.length <= length ? str : str.slice(0, length) + '…';
}

// Download a blob
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
