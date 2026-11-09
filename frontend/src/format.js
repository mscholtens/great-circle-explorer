// Small formatting / DOM helpers. No geodesy here.

/** Create an element: el('div', {class: 'x', onclick}, child, ...) */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
    else if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else node.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}

export const COORD_MODES = [
  { id: 'dd', label: 'DD', title: 'Decimal degrees' },
  { id: 'dms', label: 'DMS', title: 'Degrees, minutes, seconds' },
  { id: 'ddm', label: 'DDM', title: 'Degrees, decimal minutes' },
];

/**
 * Split a coordinate into display components for the given mode:
 *   { deg, min, sec, hemi } as strings ('' for parts the mode does not use), hemi = N/S or E/W.
 * Rounding is done on integers (hundredths of a second / thousandths of a minute) so 59.999″ carries correctly.
 */
export function splitCoord(value, axis, mode) {
  const hemi = axis === 'lat' ? (value >= 0 ? 'N' : 'S') : (value >= 0 ? 'E' : 'W');
  const abs = Math.abs(value);
  if (mode === 'dms') {
    const cs = Math.round(abs * 360000);              // hundredths of an arc-second
    return {
      deg: String(Math.floor(cs / 360000)),
      min: String(Math.floor((cs % 360000) / 6000)),
      sec: ((cs % 6000) / 100).toFixed(2),
      hemi,
    };
  }
  if (mode === 'ddm') {
    const m = Math.round(abs * 60000);                // thousandths of an arc-minute
    return { deg: String(Math.floor(m / 60000)), min: ((m % 60000) / 1000).toFixed(3), sec: '', hemi };
  }
  return { deg: String(Number(abs.toFixed(4))), min: '', sec: '', hemi };
}

/** Format one coordinate with its hemisphere letter:  50.8659° N | 50° 51′ 57.24″ N | 50° 51.954′ N */
export function formatCoord(value, axis, mode) {
  const s = splitCoord(value, axis, mode);
  if (mode === 'dms') return `${s.deg}° ${s.min}′ ${s.sec}″ ${s.hemi}`;
  if (mode === 'ddm') return `${s.deg}° ${s.min}′ ${s.hemi}`;
  return `${s.deg}° ${s.hemi}`;
}

/** Inverse of splitCoord: parts {deg, min, sec, hemi} -> signed degrees (NaN if a part is missing/invalid). */
export function composeCoord({ deg, min = '', sec = '', hemi }) {
  const num = (s) => (String(s).trim() === '' ? 0 : Number(String(s).trim().replace(',', '.')));
  const d = num(deg), m = num(min), s = num(sec);
  if (![d, m, s].every(Number.isFinite) || String(deg).trim() === '') return NaN;
  const value = d + m / 60 + s / 3600;
  return hemi === 'S' || hemi === 'W' ? -value : value;
}

const SAMPLES = {
  dd: ['50.8659° N', '7.1427° E'],
  dms: ['50° 51′ 57.24″ N', '7° 8′ 33.72″ E'],
  ddm: ['50° 51.954′ N', '7° 8.562′ E'],
};

/** Grayed-out example text showing the expected format. */
export function coordPlaceholder(axis, mode) {
  return SAMPLES[mode][axis === 'lat' ? 0 : 1];
}

/**
 * Parse a latitude (axis 'lat') or longitude (axis 'lon') typed by a person; returns degrees or NaN.
 * Accepts: 33.393 | -33.393 | 33.393 S | S 33.393 | 33.393°S | 33°23'34.8"S | 33 23 34.8 S | 33°23.58'S
 * A hemisphere letter must fit the axis (N/S for lat, E/W for lon); S and W mean negative.
 * Unit parsing only: this is input normalization, not geodesy.
 */
export function parseCoord(input, axis) {
  const t = String(input).trim().toUpperCase();
  if (t === '') return NaN;
  const allowed = axis === 'lat' ? 'NS' : 'EW';
  let rest = t;
  let letter = null;
  let m = t.match(/^([NSEW])[\s:]*(.+)$/);
  if (m) {
    [, letter, rest] = m;
  } else if ((m = t.match(/^(.+?)\s*([NSEW])$/))) {
    [, rest, letter] = m;
  }
  if (letter && !allowed.includes(letter)) return NaN;
  if (/[^0-9+\-.,\s°º'"′″]/.test(rest)) return NaN;
  const parts = rest.match(/[+-]?\d+(?:[.,]\d+)?|[+-]?[.,]\d+/g);
  if (!parts || parts.length > 3) return NaN;
  if (rest.replace(/[+-]?\d+(?:[.,]\d+)?|[+-]?[.,]\d+|[\s°º'"′″]/g, '') !== '') return NaN;
  const nums = parts.map((p) => Number(p.replace(',', '.')));
  if (nums.some((n) => !Number.isFinite(n))) return NaN;
  if (nums.slice(1).some((n, i) => n < 0 || parts[i + 1].startsWith('-'))) return NaN;
  const negativeSign = parts[0].startsWith('-');
  if (letter && negativeSign) return NaN;                       // "-33 S" is ambiguous
  const [deg, min = 0, sec = 0] = nums.map(Math.abs);
  if (nums.length > 1) {
    if (!Number.isInteger(deg) || min >= 60 || sec >= 60) return NaN;
    if (nums.length === 3 && !Number.isInteger(min)) return NaN;
  }
  const value = deg + min / 60 + sec / 3600;
  return negativeSign || letter === 'S' || letter === 'W' ? -value : value;
}

/** Wrap a longitude into [-180, 180] (input normalization for map clicks, not geodesy). */
export function wrapLon(lon) {
  return ((((lon + 180) % 360) + 360) % 360) - 180;
}

export function todayISO() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

/** Plain-text version of a metric's explanation (for "Copy as text"). */
export function explanationToText(metric) {
  const e = metric.explanation;
  const lines = [metric.label, `Result: ${metric.display}`, '', e.summary, ''];
  e.steps.forEach((s, i) => {
    lines.push(`${i + 1}. ${s.label}`);
    if (s.tex) lines.push(`   formula:      ${s.tex}`);
    if (s.substituted_tex) lines.push(`   substituted:  ${s.substituted_tex}`);
    if (s.result) lines.push(`   result:       ${s.result}`);
  });
  if (e.constants.length) {
    lines.push('', 'Constants:');
    e.constants.forEach((c) => lines.push(`  ${c.symbol} = ${c.value}  (${c.meaning})`));
  }
  if (e.notes.length) {
    lines.push('', 'Notes:');
    e.notes.forEach((n) => lines.push(`  - ${n}`));
  }
  return lines.join('\n');
}
