import { useEffect, useMemo, useState } from 'react';

const DAYS = [
  { id: 0, label: 'Monday' },
  { id: 1, label: 'Tuesday' },
  { id: 2, label: 'Wednesday' },
  { id: 3, label: 'Thursday' },
  { id: 4, label: 'Friday' },
  { id: 5, label: 'Saturday' },
  { id: 6, label: 'Sunday' },
];

const DEFAULT_FORM = {
  weekdays: [0, 1, 2, 3, 4, 5],
  start_time: '09:00',
  end_time: '19:00',
  slot_minutes: 30,
  weeks_ahead: 4,
  holidays: [],
};

function toTimeInput(value) {
  if (!value) return '09:00';
  return String(value).slice(0, 5);
}

export function normalizeHolidays(list) {
  if (!Array.isArray(list)) return [];
  const byDate = {};
  list.forEach((item) => {
    const date = String(item?.date || '').slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return;
    byDate[date] = {
      date,
      name: String(item?.name || 'Holiday').trim() || 'Holiday',
    };
  });
  return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));
}

export function normalizeAvailability(data) {
  if (!data) return { ...DEFAULT_FORM, holidays: [] };
  return {
    weekdays: Array.isArray(data.weekdays) && data.weekdays.length ? data.weekdays : DEFAULT_FORM.weekdays,
    start_time: toTimeInput(data.start_time),
    end_time: toTimeInput(data.end_time),
    slot_minutes: Number(data.slot_minutes) || 30,
    weeks_ahead: Number(data.weeks_ahead) || 4,
    holidays: normalizeHolidays(data.holidays),
  };
}

function formatHolidayDate(dateStr) {
  if (!dateStr) return '';
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function HolidayEditor({
  holidays = [],
  onChange,
  compact = false,
}) {
  const [date, setDate] = useState('');
  const [name, setName] = useState('');

  const addHoliday = () => {
    if (!date) return;
    onChange?.(normalizeHolidays([...(holidays || []), { date, name: name || 'Holiday' }]));
    setDate('');
    setName('');
  };

  const removeHoliday = (targetDate) => {
    onChange?.((holidays || []).filter((item) => item.date !== targetDate));
  };

  return (
    <div className={compact ? 'space-y-3' : 'space-y-4'}>
      <p className="text-sm text-muted">
        Closed days have no booking slots. Existing interviews already booked on a holiday stay on the calendar.
      </p>
      <div className={`grid gap-3 ${compact ? 'sm:grid-cols-[1fr_1fr_auto]' : 'sm:grid-cols-[160px_1fr_auto]'}`}>
        <label className="text-xs font-semibold text-muted uppercase tracking-wider">
          Date
          <input
            type="date"
            className="input-field mt-1.5"
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        </label>
        <label className="text-xs font-semibold text-muted uppercase tracking-wider">
          Holiday name
          <input
            type="text"
            className="input-field mt-1.5"
            maxLength={120}
            placeholder="e.g. Diwali"
            value={name}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                addHoliday();
              }
            }}
          />
        </label>
        <div className="flex items-end">
          <button type="button" onClick={addHoliday} disabled={!date} className="btn-secondary w-full sm:w-auto">
            Add holiday
          </button>
        </div>
      </div>
      {holidays.length === 0 ? (
        <p className="text-xs text-muted">No holidays yet. Add closed days so candidates cannot book them.</p>
      ) : (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800 border border-col rounded-xl overflow-hidden">
          {holidays.map((item) => (
            <li key={item.date} className="flex items-center justify-between gap-3 px-3 py-2 bg-white dark:bg-slate-900">
              <div>
                <p className="text-sm font-medium text-col">{item.name}</p>
                <p className="text-xs text-muted">{formatHolidayDate(item.date)}</p>
              </div>
              <button
                type="button"
                onClick={() => removeHoliday(item.date)}
                className="text-xs font-medium text-red-600 hover:text-red-700"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function InterviewHoursForm({
  value,
  onSave,
  saving = false,
  compact = false,
  showHolidays = true,
}) {
  const [form, setForm] = useState(() => normalizeAvailability(value));

  useEffect(() => {
    setForm(normalizeAvailability(value));
  }, [value]);

  const summary = useMemo(() => {
    const labels = DAYS.filter((day) => form.weekdays.includes(day.id)).map((day) => day.label.slice(0, 3));
    const start = toTimeInput(form.start_time);
    const end = toTimeInput(form.end_time);
    const holidayCount = form.holidays.length;
    const holidayLabel = holidayCount === 1 ? '1 holiday' : `${holidayCount} holidays`;
    return `${labels.join(', ') || 'No days'} · ${start}–${end} · ${form.slot_minutes} min default duration · ${holidayLabel}`;
  }, [form]);

  const toggleDay = (id) => {
    setForm((current) => {
      const selected = current.weekdays.includes(id)
        ? current.weekdays.filter((day) => day !== id)
        : [...current.weekdays, id].sort((a, b) => a - b);
      if (!selected.length) return current;
      return { ...current, weekdays: selected };
    });
  };

  const submit = (event) => {
    event.preventDefault();
    onSave?.({
      weekdays: form.weekdays,
      start_time: toTimeInput(form.start_time),
      end_time: toTimeInput(form.end_time),
      slot_minutes: Number(form.slot_minutes),
      weeks_ahead: Number(form.weeks_ahead),
      holidays: normalizeHolidays(form.holidays),
    });
  };

  return (
    <form onSubmit={submit} className={compact ? 'space-y-3' : 'space-y-5'}>
      <p className="text-sm text-muted">
        Candidates book on these days. Slot length is also the default interview duration for Agent 3, Agent 4, and the calendar. HR can still change duration for one candidate on that candidate’s Agent 3 plan.
      </p>
      <div>
        <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Working days</p>
        <div className="flex flex-wrap gap-2">
          {DAYS.map((day) => {
            const active = form.weekdays.includes(day.id);
            return (
              <button
                key={day.id}
                type="button"
                onClick={() => toggleDay(day.id)}
                className={`px-3 py-2 rounded-xl text-sm font-medium border ${
                  active
                    ? 'nav-active border-transparent'
                    : 'border-col text-muted hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                {day.label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="text-xs font-semibold text-muted uppercase tracking-wider">
          Start
          <input
            type="time"
            className="input-field mt-1.5"
            value={form.start_time}
            onChange={(event) => setForm((current) => ({ ...current, start_time: event.target.value }))}
            required
          />
        </label>
        <label className="text-xs font-semibold text-muted uppercase tracking-wider">
          End
          <input
            type="time"
            className="input-field mt-1.5"
            value={form.end_time}
            onChange={(event) => setForm((current) => ({ ...current, end_time: event.target.value }))}
            required
          />
        </label>
        <label className="text-xs font-semibold text-muted uppercase tracking-wider">
          Slot length / default duration
          <select
            className="input-field mt-1.5"
            value={form.slot_minutes}
            onChange={(event) => setForm((current) => ({ ...current, slot_minutes: Number(event.target.value) }))}
          >
            <option value={15}>15 minutes</option>
            <option value={30}>30 minutes</option>
            <option value={45}>45 minutes</option>
            <option value={60}>60 minutes</option>
          </select>
        </label>
        <label className="text-xs font-semibold text-muted uppercase tracking-wider">
          Weeks ahead
          <select
            className="input-field mt-1.5"
            value={form.weeks_ahead}
            onChange={(event) => setForm((current) => ({ ...current, weeks_ahead: Number(event.target.value) }))}
          >
            {[2, 3, 4, 6, 8].map((weeks) => (
              <option key={weeks} value={weeks}>{weeks} weeks</option>
            ))}
          </select>
        </label>
      </div>
      {showHolidays && (
        <div>
          <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Holidays</p>
          <HolidayEditor
            holidays={form.holidays}
            compact={compact}
            onChange={(holidays) => setForm((current) => ({ ...current, holidays }))}
          />
        </div>
      )}
      <p className="text-xs text-muted">{summary}</p>
      <button type="submit" disabled={saving} className="btn-primary">
        {saving ? 'Saving…' : 'Save interview hours'}
      </button>
    </form>
  );
}
