/** Clock for slot/join UI that follows the server, not the laptop date/time. */

export function companyOffsetFromServerNow(iso) {
  const match = String(iso || '').match(/([+-]\d{2}:\d{2}|Z)$/i);
  return match ? match[1].toUpperCase() : '+05:30';
}

export function createServerClock(serverNowIso, serverToday) {
  const parsed = serverNowIso ? Date.parse(serverNowIso) : NaN;
  const origin = typeof performance !== 'undefined' ? performance.now() : 0;
  const hasServer = Number.isFinite(parsed);
  const offset = companyOffsetFromServerNow(serverNowIso);
  return {
    offset,
    nowMs() {
      if (!hasServer) return null;
      const elapsed = typeof performance !== 'undefined' ? performance.now() - origin : 0;
      return parsed + elapsed;
    },
    todayKey() {
      if (serverToday) return String(serverToday).slice(0, 10);
      return '';
    },
  };
}

export function isSlotOpenAt(slot, nowMs, offset = '+05:30') {
  if (nowMs == null) return !slot?.is_booked;
  const datePart = String(slot?.date || '').slice(0, 10);
  const timePart = String(slot?.start_time || '00:00:00').slice(0, 8);
  if (!datePart) return false;
  const start = Date.parse(`${datePart}T${timePart}${offset === 'Z' ? 'Z' : offset}`);
  if (!Number.isFinite(start)) return !slot?.is_booked;
  return start > nowMs;
}
