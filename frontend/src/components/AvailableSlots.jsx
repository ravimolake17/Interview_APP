import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { createServerClock, isSlotOpenAt } from '../utils/serverClock';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

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

function toDateKey(value) {
  if (!value) return '';
  if (typeof value === 'string') return value.slice(0, 10);
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    const y = value.getFullYear();
    const m = String(value.getMonth() + 1).padStart(2, '0');
    const d = String(value.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }
  return String(value).slice(0, 10);
}

function monthKey(year, month) {
  return `${year}-${String(month + 1).padStart(2, '0')}`;
}

function parseMonthKey(key) {
  const [year, month] = String(key).split('-').map(Number);
  return { year, month: month - 1 };
}

function buildMonthCells(year, month) {
  const first = new Date(year, month, 1);
  const days = new Date(year, month + 1, 0).getDate();
  const lead = first.getDay();
  const cells = [];
  for (let i = 0; i < lead; i += 1) cells.push(null);
  for (let day = 1; day <= days; day += 1) {
    const date = new Date(year, month, day);
    cells.push(toDateKey(date));
  }
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

export default function AvailableSlots({
  slots,
  onSelect,
  selectedSlotId,
  disabled,
  serverNow,
  serverToday,
}) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setTick((value) => value + 1), 15000);
    return () => window.clearInterval(id);
  }, []);

  const clock = useMemo(
    () => createServerClock(serverNow, serverToday),
    [serverNow, serverToday],
  );
  const openSlots = useMemo(() => {
    const nowMs = clock.nowMs();
    return (slots || []).filter(
      (slot) => !slot.is_booked && isSlotOpenAt(slot, nowMs, clock.offset),
    );
  }, [slots, clock, tick]);

  const grouped = useMemo(() => {
    const acc = {};
    openSlots.forEach((slot) => {
      const key = toDateKey(slot.date);
      if (!key) return;
      if (!acc[key]) acc[key] = [];
      acc[key].push(slot);
    });
    Object.values(acc).forEach((daySlots) => {
      daySlots.sort((a, b) => String(a.start_time).localeCompare(String(b.start_time)));
    });
    return acc;
  }, [openSlots]);

  const availableDates = useMemo(() => Object.keys(grouped).sort(), [grouped]);
  const todayKey = clock.todayKey() || (availableDates[0] || '');

  const monthBounds = useMemo(() => {
    if (!availableDates.length) {
      const key = (todayKey || '1970-01-01').slice(0, 7);
      return { min: key, max: key };
    }
    return {
      min: availableDates[0].slice(0, 7),
      max: availableDates[availableDates.length - 1].slice(0, 7),
    };
  }, [availableDates, todayKey]);

  const [viewMonth, setViewMonth] = useState(monthBounds.min);
  const [selectedDate, setSelectedDate] = useState(availableDates[0] || '');

  useEffect(() => {
    if (!availableDates.length) {
      setSelectedDate('');
      return;
    }
    setSelectedDate((current) => (
      current && grouped[current] ? current : availableDates[0]
    ));
    setViewMonth((current) => {
      if (current >= monthBounds.min && current <= monthBounds.max) return current;
      return monthBounds.min;
    });
  }, [availableDates, grouped, monthBounds.max, monthBounds.min]);

  const { year, month } = parseMonthKey(viewMonth);
  const cells = buildMonthCells(year, month);
  const monthLabel = new Date(year, month, 1).toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
  });
  const canPrev = viewMonth > monthBounds.min;
  const canNext = viewMonth < monthBounds.max;
  const daySlots = selectedDate ? grouped[selectedDate] || [] : [];

  if (!openSlots.length) {
    return (
      <div className="rounded-2xl border border-dashed border-col text-center text-muted py-12 px-4">
        No available interview slots at this time. Please contact HR.
      </div>
    );
  }

  const shiftMonth = (delta) => {
    const next = new Date(year, month + delta, 1);
    const key = monthKey(next.getFullYear(), next.getMonth());
    if (key < monthBounds.min || key > monthBounds.max) return;
    setViewMonth(key);
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-col">{monthLabel}</h3>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => shiftMonth(-1)}
              disabled={!canPrev}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-muted hover:bg-slate-100 disabled:opacity-30 disabled:pointer-events-none"
              aria-label="Previous month"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              type="button"
              onClick={() => shiftMonth(1)}
              disabled={!canNext}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-muted hover:bg-slate-100 disabled:opacity-30 disabled:pointer-events-none"
              aria-label="Next month"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-7 gap-1 mb-1">
          {WEEKDAYS.map((day) => (
            <div key={day} className="text-[11px] font-semibold uppercase tracking-wide text-muted text-center py-1">
              {day}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-1">
          {cells.map((dateKey, index) => {
            if (!dateKey) {
              return <div key={`empty-${index}`} className="h-11" />;
            }
            const count = grouped[dateKey]?.length || 0;
            const hasSlots = count > 0;
            const isSelected = selectedDate === dateKey;
            const isToday = todayKey === dateKey;
            return (
              <button
                key={dateKey}
                type="button"
                disabled={!hasSlots || disabled}
                onClick={() => hasSlots && setSelectedDate(dateKey)}
                className={`h-11 rounded-xl text-sm font-medium transition-all relative ${
                  isSelected
                    ? 'bg-primary-accent text-white shadow-md shadow-orange-500/20'
                    : hasSlots
                      ? 'bg-orange-50 text-col hover:bg-orange-100 border border-orange-200'
                      : 'text-slate-300 cursor-not-allowed'
                } ${isToday && !isSelected ? 'ring-1 ring-orange-300' : ''}`}
                title={hasSlots ? `${count} slot${count === 1 ? '' : 's'} available` : 'No slots'}
              >
                {Number(dateKey.slice(-2))}
                {hasSlots && !isSelected && (
                  <span className="absolute bottom-1 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-primary-accent" />
                )}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-muted mt-3">
          Highlighted dates have open slots. Click a date to see its times.
        </p>
      </div>

      <div>
        {selectedDate ? (
          <>
            <h3 className="text-sm font-semibold text-col mb-3 flex items-center gap-2">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary-accent" />
              {formatDate(selectedDate)}
              <span className="text-xs font-normal text-muted">
                · {daySlots.length} slot{daySlots.length === 1 ? '' : 's'}
              </span>
            </h3>
            {daySlots.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-col text-center text-muted py-10 px-4 text-sm">
                No open slots on this date. Pick another highlighted day.
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {daySlots.map((slot) => {
                  const isSelected = selectedSlotId === slot.id;
                  const isDisabled = disabled || slot.is_booked || isSelected;
                  return (
                    <button
                      key={slot.id}
                      type="button"
                      onClick={() => !isDisabled && onSelect(slot)}
                      disabled={isDisabled}
                      className={`group relative p-4 rounded-2xl border text-center transition-all ${
                        isSelected
                          ? 'bg-primary-accent text-white border-transparent shadow-lg shadow-orange-500/25'
                          : slot.is_booked
                            ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                            : 'bg-white border-col hover:border-primary-accent hover:shadow-md hover:-translate-y-0.5'
                      }`}
                    >
                      <span className={`block font-semibold tracking-tight ${isSelected ? 'text-white' : 'text-col'}`}>
                        {formatTime(slot.start_time)}
                      </span>
                      {!slot.is_booked && !isSelected && (
                        <span className="block text-xs text-primary-accent font-medium mt-1.5 group-hover:underline">
                          Select
                        </span>
                      )}
                      {slot.is_booked && !isSelected && (
                        <span className="block text-xs mt-1.5">Booked</span>
                      )}
                      {isSelected && <span className="block text-xs mt-1.5 text-white/85">Selected</span>}
                    </button>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          <div className="rounded-2xl border border-dashed border-col text-center text-muted py-10 px-4 text-sm">
            Select a date on the calendar to see available times.
          </div>
        )}
      </div>
    </div>
  );
}
