/**
 * Number and date formatting shared by the signed-in pages. Everything here is a pure function, so it
 * is unit-tested (lib/format.test.js) and can be imported from any page without pulling in another
 * page's code.
 */

/** "2m 5s" or "45s"; "—" when there is no duration yet (a session that was never finished). */
export function formatDuration(seconds) {
  if (seconds == null) return "—";
  const total = Math.round(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/** The running clock of a live session or recording: "3:07". */
export function formatClock(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Total practice time: "3h 40m", or "12m" under an hour. Works in whole minutes, so it never shows "1h 60m". */
export function formatHours(seconds) {
  const minutes = Math.round((seconds || 0) / 60);
  const h = Math.floor(minutes / 60);
  return h > 0 ? `${h}h ${minutes % 60}m` : `${minutes}m`;
}

/** A session's length in a list row: "5 min" (never less than one minute). */
export function formatMinutes(seconds) {
  return `${Math.max(1, Math.round((seconds || 0) / 60))} min`;
}

/** When a session started, in the reader's locale: "Oct 5, 09:41 AM". */
export function formatDate(iso) {
  return new Date(iso).toLocaleString([], {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

/** A day in the reader's locale: "Mon, Oct 5". */
export function formatDay(iso) {
  return new Date(iso).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
}

/** A plain calendar date ("2026-10-05") as "Oct 5". Read as a local date, not UTC, so it never slips a day. */
export function shortDate(isoDate) {
  return new Date(`${isoDate}T00:00:00`).toLocaleDateString([], { month: "short", day: "numeric" });
}
