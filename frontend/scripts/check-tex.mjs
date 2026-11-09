// Renders every TeX string returned by the backend with KaTeX in strict mode.
// Needs the backend running on :8000 (or pass another base URL as the first argument).
//   node scripts/check-tex.mjs [http://localhost:8000]
import katex from 'katex';

const base = process.argv[2] || 'http://localhost:8000';

const cases = [
  ['Dusseldorf -> New York', [51.2277, 6.7735], [40.6413, -73.7781]],
  ['Tokyo -> San Francisco (antimeridian)', [35.7, 139.7], [37.8, -122.4]],
  ['Sydney -> Buenos Aires (southern)', [-33.9, 151.2], [-34.6, -58.4]],
  ['Identical points', [10, 20], [10, 20]],
  ['Antipodal', [0, 0], [0, 180]],
  ['North pole -> equator', [90, 0], [0, 0]],
  ['Polar day (80N, June)', [80, 0], [80, 10], '2026-06-21'],
  ['Polar night (80N, December)', [80, 0], [80, 10], '2026-12-21'],
  ['Short hop', [51.0, 6.0], [51.001, 6.001]],
  ['Open ocean', [0, -140], [10, -150]],
  ['Cologne Bonn -> Santiago (equator, tropics, prime meridian)', [50.8659, 7.1427], [-33.393, -70.7858]],
  ['Amsterdam -> Anchorage (polar circle)', [52.4, 4.9], [61.2, -149.9]],
  ['North pole -> southern hemisphere', [90, 0], [-30, 40]],
  ['Along the equator', [0, 10], [0, 80]],
  ['Along a meridian', [10, 0], [50, 0]],
  ['Far future date', [51.2, 6.8], [40.6, -73.8], '2049-07-15'],
  ['Early date', [51.2, 6.8], [40.6, -73.8], '1970-01-01'],
];

let errors = 0;
let rendered = 0;

for (const [name, a, b, date] of cases) {
  const res = await fetch(`${base}/api/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ a: { lat: a[0], lon: a[1] }, b: { lat: b[0], lon: b[1] }, options: date ? { date } : {} }),
  });
  if (!res.ok) { console.error(`${name}: HTTP ${res.status}`); errors++; continue; }
  const data = await res.json();
  for (const m of data.metrics) {
    if (!m.explanation.steps.length) { console.error(`${name} / ${m.id}: no steps`); errors++; }
    for (const [i, s] of m.explanation.steps.entries()) {
      for (const key of ['tex', 'substituted_tex']) {
        if (!s[key]) continue;
        try {
          katex.renderToString(s[key], { displayMode: true, throwOnError: true, strict: 'error' });
          rendered++;
        } catch (err) {
          errors++;
          console.error(`${name} / ${m.id} / step ${i + 1} (${key}): ${err.message}\n   ${s[key]}`);
        }
      }
    }
  }
}

console.log(`${rendered} formulas rendered, ${errors} error(s)`);
process.exit(errors ? 1 : 0);
