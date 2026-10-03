import { CalendarClock } from 'lucide-react';

function formatTime(timeStr) {
  const [hours, minutes] = String(timeStr).split(':').map(Number);
  const period = hours >= 12 ? 'PM' : 'AM';
  const displayHours = hours % 12 || 12;
  return `${displayHours}:${String(minutes).padStart(2, '0')} ${period}`;
}

function formatDate(dateStr) {
  const date = new Date(`${dateStr}T00:00:00`);
  return date.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
}

export default function ConfirmationDialog({ slot, onConfirm, onCancel, loading }) {
  if (!slot) return null;

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden border border-col">
        <div
          className="px-6 py-5 border-b border-col"
          style={{
            background:
              'linear-gradient(135deg, color-mix(in srgb, var(--color-primary) 14%, white), white)',
          }}
        >
          <div className="w-11 h-11 rounded-xl bg-orange-100 text-orange-700 flex items-center justify-center mb-3">
            <CalendarClock size={20} />
          </div>
          <h2 className="text-xl font-bold text-col">Confirm interview?</h2>
          <p className="text-sm text-muted mt-1">Please confirm this slot before we lock it in.</p>
        </div>

        <div className="px-6 py-5">
          <div className="rounded-xl border border-orange-100 bg-orange-50/70 px-4 py-3">
            <p className="font-semibold text-col">{formatDate(slot.date)}</p>
            <p className="text-primary-accent font-medium mt-0.5">
              {formatTime(slot.start_time)} — {formatTime(slot.end_time)}
            </p>
          </div>
        </div>

        <div className="px-6 pb-6 flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="btn-secondary flex-1"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="btn-primary flex-1"
          >
            {loading ? 'Booking…' : 'Confirm slot'}
          </button>
        </div>
      </div>
    </div>
  );
}
