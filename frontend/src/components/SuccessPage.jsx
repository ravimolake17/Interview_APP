import { CheckCircle2, CalendarDays, Clock } from 'lucide-react';

function formatTime(timeStr) {
  if (!timeStr) return '—';
  const [hours, minutes] = String(timeStr).split(':').map(Number);
  const period = hours >= 12 ? 'PM' : 'AM';
  const displayHours = hours % 12 || 12;
  return `${displayHours}:${String(minutes).padStart(2, '0')} ${period}`;
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const date = new Date(`${String(dateStr).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return String(dateStr);
  return date.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

export default function SuccessPage({ booking, candidate }) {
  return (
    <div className="card overflow-hidden max-w-xl mx-auto text-center">
      <div
        className="px-6 py-8 border-b border-col"
        style={{
          background:
            'linear-gradient(160deg, color-mix(in srgb, #22c55e 16%, white), color-mix(in srgb, var(--color-primary) 8%, white))',
        }}
      >
        <div className="w-16 h-16 rounded-full bg-green-100 text-green-600 flex items-center justify-center mx-auto mb-4 shadow-sm">
          <CheckCircle2 size={32} />
        </div>
        <h2 className="text-2xl font-bold text-col">Interview scheduled</h2>
        <p className="text-sm text-muted mt-2 max-w-md mx-auto">
          {candidate?.full_name ? `Thank you, ${candidate.full_name}. ` : ''}
          Your interview is confirmed. Please join from the email we sent — the room opens
          5 minutes before your scheduled time.
        </p>
      </div>

      <div className="p-6 space-y-3 text-left">
        <div className="rounded-xl border border-col px-4 py-3 flex items-start gap-3">
          <CalendarDays size={18} className="text-primary-accent mt-0.5" />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted">Date</p>
            <p className="font-semibold text-col">{formatDate(booking.interview_date)}</p>
          </div>
        </div>
        <div className="rounded-xl border border-col px-4 py-3 flex items-start gap-3">
          <Clock size={18} className="text-primary-accent mt-0.5" />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted">Time</p>
            <p className="font-semibold text-col">{formatTime(booking.interview_time)}</p>
          </div>
        </div>
        <p className="text-xs text-muted px-1 pt-1">
          Identity verification begins when you enter the room. After that, your interview starts automatically.
          Early access is not available.
        </p>
      </div>
    </div>
  );
}
