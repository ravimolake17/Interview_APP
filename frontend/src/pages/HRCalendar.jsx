import { useCallback, useEffect, useMemo, useState } from 'react';
import { getHRCandidateDetail, getInterviewAvailability, getInterviewCalendar, getScreeningFileUrl, updateInterviewAvailability } from '../services/api';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import LoadingSpinner from '../components/LoadingSpinner';
import InterviewHoursForm, { HolidayEditor, normalizeAvailability, normalizeHolidays } from '../components/InterviewHoursForm';
import { useAuth } from '../context/AuthContext';
import { isStaffAdmin } from '../utils/roles';
import { createServerClock } from '../utils/serverClock';

function parseDateKey(key) {
  const [year, month, day] = String(key || '').split('-').map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day);
}

function toDateStr(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function startOfWeekSunday(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - d.getDay());
  return d;
}

function addDays(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function parseTimeToMinutes(timeStr) {
  const [h, m] = timeStr.split(':').map(Number);
  return h * 60 + m;
}

function hourBounds(availability) {
  const start = Number(String(availability?.start_time || '09:00').slice(0, 2));
  const [endHour, endMinute] = String(availability?.end_time || '19:00').split(':').map(Number);
  const end = endMinute > 0 ? endHour + 1 : endHour;
  return {
    start: Number.isFinite(start) ? start : 9,
    end: Number.isFinite(end) && end > start ? end : 19,
  };
}

function formatHour(h) {
  return `${String(h).padStart(2, '0')}:00`;
}

function formatDateLabel(dateStr) {
  if (!dateStr) return 'Not scheduled';
  return new Date(dateStr).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function formatTimeLabel(timeStr) {
  if (!timeStr) return 'Not scheduled';
  const [hours, minutes] = String(timeStr).split(':');
  const date = new Date();
  date.setHours(Number(hours), Number(minutes), 0, 0);
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

function normalizeDateKey(value) {
  if (!value) return '';
  return String(value).slice(0, 10);
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function StatusBadge({ status }) {
  const styles = {
    SHORTLISTED: 'bg-green-100 text-green-800',
    NEEDS_REVIEW: 'bg-amber-100 text-amber-800',
    REJECTED: 'bg-red-100 text-red-800',
    INTERVIEW_SCHEDULED: 'bg-blue-100 text-blue-800',
    INTERVIEW_COMPLETED: 'bg-teal-100 text-teal-800',
    PENDING: 'bg-gray-100 text-gray-700',
  };
  const label = status?.replace(/_/g, ' ') || 'Unknown';
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${styles[status] || styles.PENDING}`}>
      {label}
    </span>
  );
}

function CandidateProfileDrawer({ detail, onClose }) {
  if (!detail) return null;

  return (
    <div className="fixed inset-0 z-40 bg-black/35" onClick={onClose}>
      <div
        className="absolute top-0 right-0 h-full w-full max-w-2xl bg-white shadow-2xl border-l border-gray-200 overflow-y-auto"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 z-10 bg-white border-b border-gray-100 px-6 py-4 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-hr-600 font-semibold mb-2">Candidate Profile</p>
            <h3 className="text-2xl font-semibold text-hr-800">{detail.full_name}</h3>
            <p className="text-sm text-gray-500">{detail.email}</p>
            <p className="text-sm text-gray-500">{detail.candidate_id}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 text-2xl leading-none"
            aria-label="Close profile"
          >
            ×
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-4 items-start">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={detail.status} />
                <span className="text-sm text-gray-600">{detail.job_position || 'Open Position'}</span>
              </div>
              <div className="grid sm:grid-cols-2 gap-3">
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-3">
                  <p className="text-xs text-gray-500">Scheduled date</p>
                  <p className="text-sm font-semibold text-gray-800">{formatDateLabel(detail.scheduled_date)}</p>
                </div>
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-3">
                  <p className="text-xs text-gray-500">Scheduled time</p>
                  <p className="text-sm font-semibold text-gray-800">{formatTimeLabel(detail.scheduled_time)}</p>
                </div>
              </div>
              {detail.meeting_link && (
                <a
                  href={detail.meeting_link}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex text-sm text-hr-700 hover:text-hr-800 underline underline-offset-2"
                >
                  Open interview room
                </a>
              )}
              <div className="flex flex-wrap gap-2">
                {detail.resume_file_url && (
                  <a
                    href={getScreeningFileUrl(detail.resume_file_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex text-sm text-hr-700 hover:text-hr-800 underline underline-offset-2"
                  >
                    Open Resume File
                  </a>
                )}
                {detail.jd_file_url && (
                  <a
                    href={getScreeningFileUrl(detail.jd_file_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex text-sm text-hr-700 hover:text-hr-800 underline underline-offset-2"
                  >
                    Open JD File
                  </a>
                )}
              </div>
            </div>
            <div className="text-right">
              <p className="text-4xl font-bold text-hr-700">{detail.resume_score.toFixed(0)}%</p>
              <p className="text-xs text-gray-500">Resume score</p>
            </div>
          </div>

          {detail.final_recommendation && (
            <div className="bg-hr-50 border border-hr-100 rounded-xl p-4 text-sm text-gray-700">
              {detail.final_recommendation}
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-3">Matched skills</h4>
              {detail.matched_skills?.length ? (
                <div className="flex flex-wrap gap-1.5">
                  {detail.matched_skills.map((skill) => (
                    <span key={skill} className="text-xs px-2 py-0.5 rounded bg-hr-50 text-hr-800 border border-hr-100">
                      {skill}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">No matched skills saved for this profile.</p>
              )}
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-3">Missing skills</h4>
              {detail.missing_skills?.length ? (
                <div className="flex flex-wrap gap-1.5">
                  {detail.missing_skills.map((skill) => (
                    <span key={skill} className="text-xs px-2 py-0.5 rounded bg-red-50 text-red-700 border border-red-100">
                      {skill}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">No missing skills saved for this profile.</p>
              )}
            </div>
          </div>

          {(detail.strengths?.length > 0 || detail.concerns?.length > 0) && (
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-white border border-gray-200 rounded-xl p-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-3">Strengths</h4>
                {detail.strengths?.length ? (
                  <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                    {detail.strengths.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-gray-500">No strengths saved.</p>
                )}
              </div>
              <div className="bg-white border border-gray-200 rounded-xl p-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-3">Concerns</h4>
                {detail.concerns?.length ? (
                  <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                    {detail.concerns.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-gray-500">No concerns saved.</p>
                )}
              </div>
            </div>
          )}

          {(detail.jd_text || detail.jd_file_url) && (
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex items-center justify-between gap-3 mb-3">
                <h4 className="text-sm font-semibold text-gray-700">Job Description</h4>
                {detail.jd_file_url && (
                  <a
                    href={getScreeningFileUrl(detail.jd_file_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-hr-700 hover:text-hr-800 underline underline-offset-2"
                  >
                    Open original {detail.jd_original_filename || 'JD file'}
                  </a>
                )}
              </div>
              <pre className="text-xs bg-gray-50 border border-gray-200 rounded-lg p-3 whitespace-pre-wrap max-h-52 overflow-y-auto text-gray-700">
                {detail.jd_text}
              </pre>
            </div>
          )}

          {detail.resume_sections?.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-3">Structured Resume Profile</h4>
              <div className="space-y-3">
                {detail.resume_sections.map((section) => (
                  <div key={section.section_id} className="border border-gray-100 rounded-lg p-3">
                    <h5 className="text-sm font-semibold text-gray-800">{section.heading}</h5>
                    {section.raw_text ? (
                      <pre className="mt-2 text-xs whitespace-pre-wrap text-gray-600">
                        {section.raw_text}
                      </pre>
                    ) : section.items?.length ? (
                      <ul className="mt-2 list-disc list-inside text-sm text-gray-600 space-y-1">
                        {section.items.map((item, index) => (
                          <li key={`${section.section_id}-${index}`}>
                            {typeof item === 'string' ? item : JSON.stringify(item)}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-gray-500">No section details available.</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {detail.resume_text && (
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex items-center justify-between gap-3 mb-3">
                <h4 className="text-sm font-semibold text-gray-700">Raw Resume Content</h4>
                {detail.resume_file_url ? (
                  <a
                    href={getScreeningFileUrl(detail.resume_file_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-hr-700 hover:text-hr-800 underline underline-offset-2"
                  >
                    Open original {detail.resume_original_filename || 'resume file'}
                  </a>
                ) : (
                  <span className="text-xs text-gray-400">Original file not available</span>
                )}
              </div>
              <pre className="text-xs bg-gray-50 border border-gray-200 rounded-lg p-3 whitespace-pre-wrap max-h-72 overflow-y-auto text-gray-700">
                {detail.resume_text}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function HoverCard({ hoveredInterview }) {
  if (!hoveredInterview) return null;

  const { interview, detail, loading, position } = hoveredInterview;
  const left = clamp(position.x + 18, 12, window.innerWidth - 340);
  const top = clamp(position.y + 18, 12, window.innerHeight - 240);

  return (
    <div
      className="fixed z-30 w-80 bg-white border border-hr-100 rounded-xl shadow-xl p-4 pointer-events-none"
      style={{ left, top }}
    >
      <p className="text-xs uppercase tracking-wide text-hr-700 font-semibold mb-2">Candidate details</p>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-gray-900">{interview.candidate_name}</h3>
          <p className="text-xs text-gray-500">{interview.candidate_id}</p>
          <p className="text-xs text-gray-500">{interview.candidate_email}</p>
        </div>
        {detail?.status && <StatusBadge status={detail.status} />}
      </div>
      <div className="mt-3 text-sm text-gray-600 space-y-1">
        <p><span className="font-medium text-gray-800">Role:</span> {interview.job_position || 'Open Position'}</p>
        <p>
          <span className="font-medium text-gray-800">Schedule:</span>{' '}
          {formatDateLabel(interview.scheduled_date)} · {formatTimeLabel(interview.start_time)} - {formatTimeLabel(interview.end_time)}
        </p>
        {loading ? (
          <p className="text-hr-700 text-xs">Loading profile preview...</p>
        ) : detail ? (
          <>
            <p><span className="font-medium text-gray-800">Score:</span> {detail.resume_score.toFixed(0)}%</p>
            {detail.matched_skills?.length > 0 && (
              <p className="text-xs text-gray-500">
                <span className="font-medium text-gray-700">Matched:</span> {detail.matched_skills.slice(0, 4).join(', ')}
              </p>
            )}
          </>
        ) : (
          <p className="text-xs text-gray-500">Preview unavailable.</p>
        )}
      </div>
      <p className="mt-3 text-xs text-gray-400">Click to open the full profile with JD and resume.</p>
    </div>
  );
}

function startOfMonth(date) {
  const d = new Date(date);
  d.setDate(1);
  d.setHours(0, 0, 0, 0);
  return d;
}

function endOfMonth(date) {
  const d = new Date(date.getFullYear(), date.getMonth() + 1, 0);
  d.setHours(0, 0, 0, 0);
  return d;
}

function formatMonthLabel(date) {
  return date.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
}

function formatRangeLabel(days) {
  if (!days.length) return '';
  if (days.length === 1) {
    return days[0].toLocaleDateString('en-GB', {
      weekday: 'long',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  }
  const start = days[0];
  const end = days[days.length - 1];
  return `${start.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} – ${end.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}`;
}

function startOfWorkWeekMonday(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  return d;
}

const VIEW_OPTIONS = [
  { id: 'day', label: 'Day', days: 1 },
  { id: 'work_week', label: 'Mon–Sat', days: 6 },
  { id: 'week', label: 'Week', days: 7 },
  { id: 'month', label: 'Month', days: null },
];

export default function HRCalendar() {
  const { user } = useAuth();
  const canManageHours = isStaffAdmin(user?.role);
  const [view, setView] = useState('work_week');
  const [dayCount, setDayCount] = useState(1);
  const [dayMenuOpen, setDayMenuOpen] = useState(false);
  const [focusDate, setFocusDate] = useState(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  });
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [detailCache, setDetailCache] = useState({});
  const [hoveredInterview, setHoveredInterview] = useState(null);
  const [activeProfile, setActiveProfile] = useState(null);
  const [availability, setAvailability] = useState(normalizeAvailability());
  const [hoursOpen, setHoursOpen] = useState(false);
  const [holidaysOpen, setHolidaysOpen] = useState(false);
  const [holidayDraft, setHolidayDraft] = useState([]);
  const [savingHours, setSavingHours] = useState(false);
  const [savingHolidays, setSavingHolidays] = useState(false);
  const [serverNow, setServerNow] = useState(null);
  const [serverToday, setServerToday] = useState('');
  const [serverTimezone, setServerTimezone] = useState('Asia/Kolkata');
  const [clockTick, setClockTick] = useState(0);

  const todayStr = serverToday;

  const visibleDays = useMemo(() => {
    if (view === 'day') {
      return Array.from({ length: dayCount }, (_, i) => addDays(focusDate, i));
    }
    if (view === 'work_week') {
      const monday = startOfWorkWeekMonday(focusDate);
      return Array.from({ length: 6 }, (_, i) => addDays(monday, i));
    }
    if (view === 'week') {
      const sunday = startOfWeekSunday(focusDate);
      return Array.from({ length: 7 }, (_, i) => addDays(sunday, i));
    }
    return [];
  }, [view, dayCount, focusDate]);

  const monthCells = useMemo(() => {
    if (view !== 'month') return [];
    const monthStart = startOfMonth(focusDate);
    const gridStart = startOfWeekSunday(monthStart);
    return Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
  }, [view, focusDate]);

  const rangeLabel = view === 'month'
    ? formatMonthLabel(focusDate)
    : formatRangeLabel(visibleDays);

  const loadCalendar = useCallback(async (options = {}) => {
    const silent = Boolean(options.silent);
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      if (view === 'month') {
        const monthStart = startOfMonth(focusDate);
        const monthEnd = endOfMonth(focusDate);
        const weekStarts = [];
        let cursor = startOfWeekSunday(monthStart);
        while (cursor <= monthEnd) {
          weekStarts.push(toDateStr(cursor));
          cursor = addDays(cursor, 7);
        }
        const responses = await Promise.all(
          weekStarts.map((ws) => getInterviewCalendar(ws)),
        );
        const merged = [];
        const seen = new Set();
        responses.forEach(({ data: res }) => {
          if (res?.server_today) setServerToday(String(res.server_today).slice(0, 10));
          if (res?.server_now) setServerNow(res.server_now);
          if (res?.timezone) setServerTimezone(res.timezone);
          (res.interviews || []).forEach((iv) => {
            const key = `${iv.interview_id}-${iv.scheduled_date}-${iv.start_time}`;
            if (!seen.has(key)) {
              seen.add(key);
              merged.push(iv);
            }
          });
        });
        setInterviews(merged);
      } else {
        const weekStarts = new Set(
          visibleDays.map((d) => toDateStr(startOfWeekSunday(d))),
        );
        const responses = await Promise.all(
          [...weekStarts].map((ws) => getInterviewCalendar(ws)),
        );
        const merged = [];
        const seen = new Set();
        responses.forEach(({ data: res }) => {
          if (res?.server_today) setServerToday(String(res.server_today).slice(0, 10));
          if (res?.server_now) setServerNow(res.server_now);
          if (res?.timezone) setServerTimezone(res.timezone);
          (res.interviews || []).forEach((iv) => {
            const key = `${iv.interview_id}-${iv.scheduled_date}-${iv.start_time}`;
            if (!seen.has(key)) {
              seen.add(key);
              merged.push(iv);
            }
          });
        });
        const dayKeys = new Set(visibleDays.map(toDateStr));
        setInterviews(
          merged.filter((iv) => dayKeys.has(normalizeDateKey(iv.scheduled_date))),
        );
      }
      setDetailCache({});
    } catch (err) {
      if (!silent) {
        setError(err.response?.data?.detail || 'Failed to load calendar.');
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [view, focusDate, visibleDays]);

  useEffect(() => {
    loadCalendar();
  }, [loadCalendar]);

  useAutoRefresh(() => loadCalendar({ silent: true }));

  useEffect(() => {
    getInterviewAvailability()
      .then(({ data }) => {
        const next = normalizeAvailability(data);
        setAvailability(next);
        setHolidayDraft(next.holidays);
      })
      .catch(() => {
        const next = normalizeAvailability();
        setAvailability(next);
        setHolidayDraft(next.holidays);
      });
  }, []);

  const saveAvailability = async (payload, { closeHours = false, closeHolidays = false } = {}) => {
    const { data } = await updateInterviewAvailability(payload);
    const next = normalizeAvailability(data.availability || payload);
    setAvailability(next);
    setHolidayDraft(next.holidays);
    if (closeHours) setHoursOpen(false);
    if (closeHolidays) setHolidaysOpen(false);
    return data;
  };

  const saveHours = async (payload) => {
    setSavingHours(true);
    try {
      await saveAvailability(
        { ...payload, holidays: normalizeHolidays(payload.holidays ?? availability.holidays) },
        { closeHours: true },
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save interview hours.');
    } finally {
      setSavingHours(false);
    }
  };

  const saveHolidays = async () => {
    setSavingHolidays(true);
    try {
      await saveAvailability(
        { ...availability, holidays: normalizeHolidays(holidayDraft) },
        { closeHolidays: true },
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save holidays.');
    } finally {
      setSavingHolidays(false);
    }
  };

  const loadCandidateDetail = async (candidateId) => {
    if (detailCache[candidateId]) {
      return detailCache[candidateId];
    }
    const { data: detail } = await getHRCandidateDetail(candidateId);
    setDetailCache((current) => ({ ...current, [candidateId]: detail }));
    return detail;
  };

  const handleHover = async (interview, event) => {
    setHoveredInterview({
      interview,
      loading: true,
      detail: detailCache[interview.candidate_id] || null,
      position: { x: event.clientX, y: event.clientY },
    });
    try {
      const detail = await loadCandidateDetail(interview.candidate_id);
      setHoveredInterview((current) =>
        current?.interview?.candidate_id === interview.candidate_id
          ? { ...current, loading: false, detail }
          : current
      );
    } catch (_error) {
      setHoveredInterview((current) =>
        current?.interview?.candidate_id === interview.candidate_id
          ? { ...current, loading: false, detail: null }
          : current
      );
    }
  };

  const handleHoverMove = (interview, event) => {
    setHoveredInterview((current) =>
      current?.interview?.candidate_id === interview.candidate_id
        ? { ...current, position: { x: event.clientX, y: event.clientY } }
        : current
    );
  };

  const handleOpenProfile = async (interview) => {
    try {
      const detail = await loadCandidateDetail(interview.candidate_id);
      setActiveProfile(detail);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load candidate profile.');
    }
  };

  useEffect(() => {
    const id = window.setInterval(() => setClockTick((value) => value + 1), 30000);
    return () => window.clearInterval(id);
  }, []);

  const goToday = () => {
    const parsed = parseDateKey(serverToday);
    if (!parsed) return;
    parsed.setHours(0, 0, 0, 0);
    setFocusDate(parsed);
  };

  const goPrev = () => {
    if (view === 'month') {
      setFocusDate(new Date(focusDate.getFullYear(), focusDate.getMonth() - 1, 1));
    } else if (view === 'day') {
      setFocusDate(addDays(focusDate, -dayCount));
    } else if (view === 'work_week') {
      setFocusDate(addDays(focusDate, -7));
    } else {
      setFocusDate(addDays(focusDate, -7));
    }
  };

  const goNext = () => {
    if (view === 'month') {
      setFocusDate(new Date(focusDate.getFullYear(), focusDate.getMonth() + 1, 1));
    } else if (view === 'day') {
      setFocusDate(addDays(focusDate, dayCount));
    } else {
      setFocusDate(addDays(focusDate, 7));
    }
  };

  const interviewsByDay = useMemo(() => {
    const map = {};
    (view === 'month' ? monthCells : visibleDays).forEach((d) => {
      map[toDateStr(d)] = [];
    });
    interviews.forEach((iv) => {
      const key = normalizeDateKey(iv.scheduled_date);
      if (map[key]) map[key].push(iv);
    });
    return map;
  }, [interviews, visibleDays, monthCells, view]);

  const holidayByDate = useMemo(() => {
    const map = {};
    (availability.holidays || []).forEach((item) => {
      map[item.date] = item.name;
    });
    return map;
  }, [availability.holidays]);

  const { start: hourStart, end: hourEnd } = hourBounds(availability);
  const hours = Array.from({ length: hourEnd - hourStart + 1 }, (_, i) => hourStart + i);
  const totalHeight = (hourEnd - hourStart) * 56;
  const gridStart = hourStart * 60;
  const gridEnd = hourEnd * 60;
  const colCount = visibleDays.length || 7;

  const clock = createServerClock(serverNow, serverToday);
  void clockTick;
  const nowMs = clock.nowMs();
  let nowMinutes = 0;
  if (nowMs != null) {
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: serverTimezone || 'Asia/Kolkata',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).formatToParts(new Date(nowMs));
    const hour = Number(parts.find((part) => part.type === 'hour')?.value || 0);
    const minute = Number(parts.find((part) => part.type === 'minute')?.value || 0);
    nowMinutes = hour * 60 + minute;
  }
  const showNowLine =
    Boolean(todayStr)
    && view !== 'month'
    && visibleDays.some((d) => toDateStr(d) === todayStr);

  const renderTimeGrid = () => (
    <div className="overflow-x-auto">
      <div
        className="min-w-[640px] grid"
        style={{ gridTemplateColumns: `56px repeat(${colCount}, 1fr)` }}
      >
        <div className="border-b border-r border-gray-200 bg-gray-50" />
        {visibleDays.map((day) => {
          const ds = toDateStr(day);
          const isToday = ds === todayStr;
          const holidayName = holidayByDate[ds];
          return (
            <div
              key={ds}
              className={`border-b border-r border-gray-200 px-2 py-2 text-center text-sm ${
                holidayName
                  ? 'bg-rose-50 border-t-2 border-t-rose-400'
                  : isToday
                    ? 'bg-hr-50 border-t-2 border-t-hr-600'
                    : 'bg-gray-50'
              }`}
            >
              <div className="text-gray-500 text-xs">
                {day.toLocaleDateString('en-GB', { weekday: 'short' })}
              </div>
              <div className={`font-semibold ${holidayName ? 'text-rose-700' : isToday ? 'text-hr-700' : 'text-gray-800'}`}>
                {day.getDate()}
              </div>
              {holidayName && (
                <div className="mt-0.5 text-[10px] font-medium text-rose-600 truncate" title={holidayName}>
                  {holidayName}
                </div>
              )}
            </div>
          );
        })}

        <div
          className="relative grid"
          style={{
            gridColumn: `1 / span ${colCount + 1}`,
            gridTemplateColumns: `56px repeat(${colCount}, 1fr)`,
            minHeight: `${(hours.length - 1) * 56}px`,
          }}
        >
          {hours.slice(0, -1).map((hour) => (
            <div key={hour} className="contents">
              <div className="border-r border-b border-gray-100 text-xs text-gray-400 pr-2 text-right h-14 flex items-start justify-end pt-1">
                {formatHour(hour)}
              </div>
              {visibleDays.map((day) => {
                const ds = toDateStr(day);
                const isToday = ds === todayStr;
                const isHoliday = Boolean(holidayByDate[ds]);
                return (
                  <div
                    key={`${ds}-${hour}`}
                    className={`relative border-r border-b border-gray-100 h-14 ${
                      isHoliday ? 'bg-rose-50/70' : isToday ? 'bg-hr-50/40' : ''
                    }`}
                  />
                );
              })}
            </div>
          ))}

          {visibleDays.map((day, dayIndex) => {
            const ds = toDateStr(day);
            const dayInterviews = interviewsByDay[ds] || [];
            return (
              <div
                key={`events-${ds}`}
                className="absolute top-0 pointer-events-none"
                style={{
                  left: `calc(56px + (100% - 56px) * ${dayIndex} / ${colCount})`,
                  width: `calc((100% - 56px) / ${colCount})`,
                  height: `${totalHeight}px`,
                }}
              >
                {dayInterviews.map((iv) => {
                  const startMin = parseTimeToMinutes(iv.start_time);
                  const endMin = parseTimeToMinutes(iv.end_time);
                  const top = ((startMin - gridStart) / (gridEnd - gridStart)) * totalHeight;
                  const height = Math.max(
                    ((endMin - startMin) / (gridEnd - gridStart)) * totalHeight,
                    28,
                  );

                  return (
                    <div
                      key={`${iv.interview_id}-${iv.start_time}`}
                      className="absolute left-1 right-1 rounded-md bg-gradient-to-r from-hr-600 to-hr-700 text-white text-xs px-2 py-1 shadow-md overflow-hidden cursor-pointer border border-hr-700/20 hover:from-hr-700 hover:to-hr-800 z-10 pointer-events-auto"
                      style={{ top: `${top}px`, height: `${height}px` }}
                      title={`${iv.candidate_name} (${iv.candidate_id})\n${iv.job_position || 'Role TBD'}`}
                      onMouseEnter={(event) => handleHover(iv, event)}
                      onMouseMove={(event) => handleHoverMove(iv, event)}
                      onMouseLeave={() =>
                        setHoveredInterview((current) =>
                          current?.interview?.candidate_id === iv.candidate_id ? null : current
                        )
                      }
                      onClick={() => handleOpenProfile(iv)}
                    >
                      <div className="font-semibold truncate">{iv.candidate_name}</div>
                      <div className="opacity-90 truncate">{iv.candidate_id}</div>
                      {height > 40 && (
                        <div className="opacity-80 truncate text-[10px] mt-0.5">
                          {iv.job_position || 'Interview'}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}

          {showNowLine && nowMinutes >= hourStart * 60 && nowMinutes <= hourEnd * 60 && (
            <div
              className="absolute left-0 right-0 border-t-2 border-hr-500 z-20 pointer-events-none"
              style={{
                top: `${((nowMinutes - gridStart) / (gridEnd - gridStart)) * totalHeight}px`,
              }}
            >
              <span className="absolute -left-1 -top-1.5 w-2.5 h-2.5 rounded-full bg-hr-500" />
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderMonthGrid = () => {
    const focusMonth = focusDate.getMonth();
    return (
      <div className="p-3">
        <div className="grid grid-cols-7 border border-gray-200 rounded-lg overflow-hidden">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((label) => (
            <div
              key={label}
              className="bg-gray-50 border-b border-r border-gray-200 last:border-r-0 px-2 py-2 text-center text-xs font-semibold text-gray-500"
            >
              {label}
            </div>
          ))}
          {monthCells.map((day) => {
            const ds = toDateStr(day);
            const isToday = ds === todayStr;
            const inMonth = day.getMonth() === focusMonth;
            const dayInterviews = interviewsByDay[ds] || [];
            const holidayName = holidayByDate[ds];
            return (
              <button
                key={ds}
                type="button"
                onClick={() => {
                  setFocusDate(day);
                  setView('day');
                  setDayCount(1);
                }}
                className={`min-h-28 border-b border-r border-gray-100 p-2 text-left align-top hover:bg-slate-50 transition-colors ${
                  holidayName ? 'bg-rose-50' : isToday ? 'bg-hr-50/60' : 'bg-white'
                }`}
              >
                <div
                  className={`text-xs font-semibold mb-1 ${
                    inMonth ? (holidayName ? 'text-rose-700' : isToday ? 'text-hr-700' : 'text-gray-800') : 'text-gray-300'
                  }`}
                >
                  {day.getDate()}
                </div>
                {holidayName && (
                  <div className="mb-1 text-[10px] font-medium text-rose-600 truncate" title={holidayName}>
                    {holidayName}
                  </div>
                )}
                <div className="space-y-1">
                  {dayInterviews.slice(0, 3).map((iv) => (
                    <div
                      key={`${iv.interview_id}-${iv.start_time}`}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-hr-600 text-white truncate"
                      title={iv.candidate_name}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenProfile(iv);
                      }}
                    >
                      {formatTimeLabel(iv.start_time)} {iv.candidate_name}
                    </div>
                  ))}
                  {dayInterviews.length > 3 && (
                    <div className="text-[10px] text-gray-500">+{dayInterviews.length - 3} more</div>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  if (loading) return <LoadingSpinner message="Loading interview calendar..." />;

  return (
    <div className="relative bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={goToday}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white hover:bg-gray-50"
          >
            Today
          </button>
          <button
            type="button"
            onClick={goPrev}
            className="p-1.5 border border-gray-300 rounded-md bg-white hover:bg-gray-50"
            aria-label="Previous"
          >
            ‹
          </button>
          <button
            type="button"
            onClick={goNext}
            className="p-1.5 border border-gray-300 rounded-md bg-white hover:bg-gray-50"
            aria-label="Next"
          >
            ›
          </button>

          <div className="w-px h-6 bg-gray-300 mx-1" />

          {VIEW_OPTIONS.map((option) => (
            <div key={option.id} className="relative">
              <button
                type="button"
                onClick={() => {
                  if (option.id === 'day') {
                    setDayMenuOpen((open) => !open);
                    setView('day');
                  } else {
                    setDayMenuOpen(false);
                    setView(option.id);
                  }
                }}
                className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                  view === option.id
                    ? 'bg-white border-gray-400 text-gray-900 shadow-sm'
                    : 'bg-transparent border-transparent text-gray-600 hover:bg-white hover:border-gray-300'
                }`}
              >
                {option.label}
                {option.id === 'day' && view === 'day' ? ` · ${dayCount}` : ''}
              </button>
              {option.id === 'day' && dayMenuOpen && (
                <div className="absolute left-0 top-10 z-30 w-36 bg-white border border-gray-200 rounded-lg shadow-lg py-1">
                  {[1, 2, 3, 4, 5, 6, 7].map((count) => (
                    <button
                      key={count}
                      type="button"
                      onClick={() => {
                        setDayCount(count);
                        setView('day');
                        setDayMenuOpen(false);
                      }}
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 ${
                        dayCount === count && view === 'day' ? 'bg-gray-100 font-medium' : 'text-gray-700'
                      }`}
                    >
                      {count} day{count !== 1 ? 's' : ''}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}

          <span className="text-sm font-medium text-gray-700 ml-1">{rangeLabel}</span>
        </div>

        <span className="text-xs text-gray-500 capitalize">
          {view === 'day' ? `${dayCount}-day` : view.replace('_', ' ')} view · {availability.start_time?.slice(0, 5)}–{availability.end_time?.slice(0, 5)}
        </span>
        {canManageHours && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setHoursOpen((open) => !open);
                setHolidaysOpen(false);
              }}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white hover:bg-gray-50"
            >
              {hoursOpen ? 'Close hours' : 'Manage hours'}
            </button>
            <button
              type="button"
              onClick={() => {
                setHolidaysOpen((open) => {
                  const next = !open;
                  if (next) setHolidayDraft(availability.holidays || []);
                  return next;
                });
                setHoursOpen(false);
              }}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white hover:bg-gray-50"
            >
              {holidaysOpen ? 'Close holidays' : 'Manage holidays'}
            </button>
          </div>
        )}
      </div>

      {canManageHours && hoursOpen && (
        <div className="px-4 py-4 border-b border-gray-200 bg-white">
          <InterviewHoursForm
            value={availability}
            onSave={saveHours}
            saving={savingHours}
            compact
            showHolidays={false}
          />
        </div>
      )}

      {canManageHours && holidaysOpen && (
        <div className="px-4 py-4 border-b border-gray-200 bg-white space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-800">Company holidays</h3>
            <p className="text-xs text-gray-500 mt-1">
              These dates appear on the calendar and are removed from candidate booking slots.
            </p>
          </div>
          <HolidayEditor holidays={holidayDraft} onChange={setHolidayDraft} compact />
          <button type="button" onClick={saveHolidays} disabled={savingHolidays} className="btn-primary">
            {savingHolidays ? 'Saving…' : 'Save holidays'}
          </button>
        </div>
      )}

      {error && (
        <div className="m-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {view === 'month' ? renderMonthGrid() : renderTimeGrid()}

      <HoverCard hoveredInterview={hoveredInterview} />

      {!loading && interviews.length === 0 && (
        <p className="text-center text-gray-500 text-sm py-8">
          No scheduled interviews in this range. Shortlist a candidate to get started.
        </p>
      )}

      <CandidateProfileDrawer detail={activeProfile} onClose={() => setActiveProfile(null)} />
    </div>
  );
}

