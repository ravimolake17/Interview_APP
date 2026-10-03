import DualCompanyLogos from './DualCompanyLogos';

export default function SessionSplash({ message = 'Loading…' }) {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center gap-5 p-6"
      style={{ background: 'var(--color-bg)' }}
    >
      <DualCompanyLogos height={48} />
      <div className="relative w-10 h-10">
        <div className="absolute inset-0 border-[3px] border-slate-200 dark:border-slate-700 rounded-full" />
        <div className="absolute inset-0 border-[3px] border-blue-600 rounded-full border-t-transparent animate-spin" />
      </div>
      <p className="text-sm text-muted">{message}</p>
    </div>
  );
}
