// Date and time of day -> an instant in UTC, and back. Pure functions (no DOM), used by the Night picker.
// Input handling only (like coordinate parsing): the calculation itself happens in the backend, which takes UTC.

export const DATE_MIN = '1970-01-01';
export const DATE_MAX = '2049-12-31';
const MIN_MS = Date.UTC(1970, 0, 1, 0, 0);
const MAX_MS = Date.UTC(2049, 11, 31, 23, 59);
const pad = (n, w = 2) => String(n).padStart(w, '0');

function parse(date, time) {
  const d = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date || '');
  const t = /^(\d{2}):(\d{2})$/.exec(time || '');
  if (!d || !t) return null;
  return { y: +d[1], mo: +d[2], d: +d[3], h: +t[1], mi: +t[2] };
}

const fmt = (y, mo, d, h, mi) => ({ date: `${pad(y, 4)}-${pad(mo)}-${pad(d)}`, time: `${pad(h)}:${pad(mi)}` });

/** A date (YYYY-MM-DD) and time (HH:MM) written in `basis` ('local' = the computer's time zone, or 'utc')
 *  -> the same instant in UTC as { date, time }, kept inside 1970-01-01 … 2049-12-31. null if the text is invalid. */
export function toUtc(basis, date, time) {
  const p = parse(date, time);
  if (!p) return null;
  const ms = basis === 'utc' ? Date.UTC(p.y, p.mo - 1, p.d, p.h, p.mi) : new Date(p.y, p.mo - 1, p.d, p.h, p.mi).getTime();
  if (!Number.isFinite(ms)) return null;
  const u = new Date(Math.min(MAX_MS, Math.max(MIN_MS, ms)));
  return fmt(u.getUTCFullYear(), u.getUTCMonth() + 1, u.getUTCDate(), u.getUTCHours(), u.getUTCMinutes());
}

/** An instant given in UTC -> date and time as written in `basis`. */
export function fromUtc(basis, utcDate, utcTime) {
  const p = parse(utcDate, utcTime);
  if (!p) return null;
  const u = new Date(Date.UTC(p.y, p.mo - 1, p.d, p.h, p.mi));
  return basis === 'utc'
    ? fmt(u.getUTCFullYear(), u.getUTCMonth() + 1, u.getUTCDate(), u.getUTCHours(), u.getUTCMinutes())
    : fmt(u.getFullYear(), u.getMonth() + 1, u.getDate(), u.getHours(), u.getMinutes());
}

/** The computer's current date and time in `basis` (rounded down to the minute). */
export function nowIn(basis, now = new Date()) {
  return basis === 'utc'
    ? fmt(now.getUTCFullYear(), now.getUTCMonth() + 1, now.getUTCDate(), now.getUTCHours(), now.getUTCMinutes())
    : fmt(now.getFullYear(), now.getMonth() + 1, now.getDate(), now.getHours(), now.getMinutes());
}

/** 'HH:MM' <-> minutes since midnight (for the slider). */
export const toMinutes = (t) => { const [h, m] = (t || '00:00').split(':').map(Number); return h * 60 + m; };
export const fromMinutes = (n) => `${pad(Math.floor(n / 60))}:${pad(n % 60)}`;
