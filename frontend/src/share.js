// Share link: the two points travel in the URL hash, e.g.  #a=50.8659,7.1427&b=-33.393,-70.7858  (latitude,longitude only).

const round6 = (x) => Number(x.toFixed(6));

function parsePoint(text) {
  if (typeof text !== 'string') return null;
  const parts = text.split(',');
  if (parts.length !== 2 || parts.some((p) => p.trim() === '')) return null;
  const lat = Number(parts[0]);
  const lon = Number(parts[1]);
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  return { lat, lon };
}

/** '#a=..&b=..' -> { a, b } with null for a missing or invalid point (garbage is ignored). */
export function parseHash(hash) {
  const params = new URLSearchParams((hash || '').replace(/^#/, ''));
  return { a: parsePoint(params.get('a')), b: parsePoint(params.get('b')) };
}

/** Points -> '#a=..&b=..' ('' when neither point is set). */
export function buildHash(a, b) {
  const parts = [];
  if (a) parts.push(`a=${round6(a.lat)},${round6(a.lon)}`);
  if (b) parts.push(`b=${round6(b.lat)},${round6(b.lon)}`);
  return parts.length ? `#${parts.join('&')}` : '';
}
