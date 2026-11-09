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
  ['Destination + return trip', [50.8659, 7.1427], [-33.393, -70.7858], { project_bearing_deg: 90, project_km: 1000, include_return: true }],
  ['Destination from a pole, past the antipode', [90, 0], [10, 20], { project_bearing_deg: 200, project_km: 25000, include_return: true }],
  ['Destination across the date line + circle radius', [0, 170], [0, 175], { project_bearing_deg: 90, project_km: 2000, circle_km: 2000 }],
  ['Miles, with projection and return', [50.8659, 7.1427], [-33.393, -70.7858], { units: 'mi', project_bearing_deg: 45, project_km: 5000, include_return: true }],
  ['Nautical miles, full moon date', [35.7, 139.7], [37.8, -122.4], { units: 'nm', date: '2000-01-21' }],
  ['Inverse mode (start + course), nautical miles', [50.8659, 7.1427], null, { course: { bearing_deg: 239.4, km: 12061 }, units: 'nm' }],
  ['Inverse mode from a pole, past the antipode', [90, 0], null, { course: { bearing_deg: 10, km: 25000 } }],
  ['Amsterdam -> Buenos Aires (distance analysis)', [52.3086, 4.7639], [-34.8222, -58.5358], {}],
  ['Distance analysis near the pole and near antipodal', [89.5, 10], [-60, -170], {}],
  ['Nearly antipodal: Vincenty does not converge', [0, 0], [0.5, 179.7], {}],
  ['Quito -> Singapore (Vincenty, 11 rounds)', [-0.18, -78.47], [1.35, 103.82], {}],
  ['Slow Vincenty (15 rounds, rounds summarised)', [0, 0], [0.2, 179.0], {}],
  ['Return trip, pole route', [52.4, 4.9], [61.2, -149.9], { include_return: true }],
];

let errors = 0;
let rendered = 0;

for (const [name, a, b, extra] of cases) {
  const { course, ...options } = typeof extra === 'string' ? { date: extra } : extra || {};
  const res = await fetch(`${base}/api/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(course
      ? { a: { lat: a[0], lon: a[1] }, course, options }
      : { a: { lat: a[0], lon: a[1] }, b: { lat: b[0], lon: b[1] }, options }),
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
