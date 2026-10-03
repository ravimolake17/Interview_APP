import { motion } from 'framer-motion';

export function LoadingOverlay({ message = 'Processing…' }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="card p-8 flex flex-col items-center gap-4 max-w-xs w-full text-center"
      >
        <div className="relative w-16 h-16">
          <div className="w-16 h-16 border-4 border-blue-100 dark:border-slate-700 rounded-full" />
          <div className="absolute inset-0 w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <div className="absolute inset-3 w-10 h-10 bg-blue-500/10 rounded-full animate-pulse" />
        </div>
        <div>
          <p className="font-semibold text-col">AI Screening in Progress</p>
          <p className="text-sm text-muted mt-1">{message}</p>
        </div>
        <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <motion.div
            className="h-full bg-blue-500 rounded-full"
            animate={{ width: ['0%', '90%'] }}
            transition={{ duration: 4, ease: 'easeInOut' }}
          />
        </div>
      </motion.div>
    </div>
  );
}

export function Skeleton({ className = '' }) {
  return <div className={`animate-pulse bg-slate-200 dark:bg-slate-700 rounded-xl ${className}`} />;
}

export function TableSkeleton({ rows = 5 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton className="w-9 h-9 rounded-full flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
          </div>
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
      ))}
    </div>
  );
}
