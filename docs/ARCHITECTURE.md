# ARCHITECTURE — Great Circle Explorer

Audience: another AI (or developer) picking up this codebase. Companion docs: [MATH.md](MATH.md) (formulas), [METRICS.md](METRICS.md) (metric catalogue), `../CLAUDE.md` (working rules).

## 1. Purpose and principles
Educational tool: pick points A and B on a globe, see grouped metrics, click a metric to see the full step-by-step calculation. Clarity of the math beats extreme accuracy; a spherical Earth is fine and the UI says so.

Design decisions (and why):
1. **Classical math only, hand-written.** `geo/` imports only `math`. No pyproj, geopy, geographiclib, haversine, shapely, numpy. The visible math is the product.
2. **Python is the single source of truth.** Every number in the UI and every explanation step comes from the backend, including the path coordinates drawn on the map. The frontend does no geodesy. (Allowed in the frontend: wrapping a clicked longitude into [−180, 180], formatting, layout.)
3. **Every metric is explainable.** A metric is not done until its `explanation` is returned and renders in the pop-up. Steps must reuse the *same* intermediate values the result was computed from; never recompute them separately.
4. **Two processes, started separately.** FastAPI backend on :8000, Vite dev server on :5173 proxying `/api`. No containers, no cloud hosting.
5. **Fully offline at runtime.** No internet, no external API calls. npm packages are bundled by Vite (no CDN). Map data, label glyphs and time-zone boundaries are local files committed to the repo (fetched once during development).
6. **No databases, no accounts, no geocoding.**

## 2. Stack
- Backend: Python 3.11+, FastAPI, Uvicorn, Pydantic v2, `tzdata` (IANA data for `zoneinfo`), pytest + httpx (dev). `uv` if available, else venv + `pip install -e .[dev]`.
- Frontend: plain JavaScript (ES modules, no framework), Vite, MapLibre GL JS (globe projection), KaTeX. Check the current MapLibre docs for the globe projection API before using it; do not rely on memory.

## 3. Repository layout
```
backend/
  pyproject.toml
  app/
    main.py            # FastAPI app, routes
    models.py          # Pydantic request/response models
    constants.py       # R, c, g, fiber index, WGS84, default speeds… (each with a source comment)
    geo/               # pure functions, math module only, radians internally
      crossings.py     # route crossings with latitude circles and meridians (vector maths)
      spherical.py     # haversine, law of cosines, bearings, midpoint, interpolation, vertex, antipode, chord
      rhumb.py         # rhumb distance, bearing, interpolation
      ellipsoid.py     # Lambert's formula on WGS84
      mercator.py      # isometric latitude, flat-map distance, scale factor
      sun.py           # declination, day length, sunrise/sunset (takes integer day of year)
      travel.py        # flight time, speeds, light/fiber latency, gravity train, horizon/line of sight
      pip.py           # ray-casting point-in-polygon
    data/              # bundled simplified timezone boundaries (GeoJSON)
    timezones.py       # zone lookup (pip.py + data) and UTC offsets (zoneinfo); lives outside geo/
    explain.py         # Step(label, tex, substituted_tex, result), number formatter (~5 significant digits)
    metrics.py         # assembles all metrics for a pair of points; converts date -> day of year
  tests/
frontend/
  package.json
  vite.config.js       # proxies /api -> http://localhost:8000
  index.html
  public/              # bundled country GeoJSON, label glyphs (PBF), nothing fetched at runtime
  src/
    config.js
    mapstyle.js        # local MapLibre style: land, borders, graticule, country labels
    main.js  api.js  map.js  panel.js  popup.js  wizard.js  modal.js  format.js  styles.css
tools/
  fetch_data.py        # one-time, needs internet: builds the bundled map, glyph and timezone data
docs/                  # this file, MATH.md, METRICS.md, EXECUTIVE_SUMMARY.md
README.md  CLAUDE.md
```

Implementation notes (things that differ from older MapLibre/Vite habits):
- MapLibre GL JS 6 has **no default export**: use `import * as maplibregl from 'maplibre-gl'`. The globe is enabled in the style (`projection: { type: 'globe' }` in `frontend/src/mapstyle.js`).
- MapLibre 6 loads its worker as a separate module, so `vite.config.js` sets `optimizeDeps.exclude: ['maplibre-gl']`; without it the worker fails to load in `npm run dev`.
- `frontend/scripts/check-tex.mjs` (`npm run check:tex`) renders every TeX string from the API with KaTeX in strict mode; run it with the backend up after changing any explanation.

## 4. Conventions
- Inside `geo/` angles are radians. The API takes/returns degrees. Convert at the boundary.
- API coordinates are `{ "lat": .., "lon": .. }`. Map path arrays are GeoJSON order `[lon, lat]`.
- Every geo function is pure, small, has a docstring stating its formula, and is tested against analytic values.
- No magic numbers: every constant lives in `constants.py` with a source/meaning comment, and appears in the explanation's `constants` list.
- `geo/` must stay free of non-`math` imports (acceptance check). Date handling and the timezone lookup (`zoneinfo`, GeoJSON loading) live in `metrics.py`/`timezones.py`.

## 5. API
Base path `/api`, JSON only.

`GET /api/health` → `{ "status": "ok" }`

`POST /api/calculate`

Request (`options` and every field in it are optional):
```json
{
  "a": { "lat": 51.2277, "lon": 6.7735 },
  "b": { "lat": 40.6413, "lon": -73.7781 },
  "options": { "cruise_kmh": 850, "climb_descent_min": 15, "taxi_min": 15, "date": "2026-11-09",
               "height_a_m": 1.7, "height_b_m": 1.7 }
}
```

Response:
```json
{
  "a": { "lat": 0, "lon": 0 }, "b": { "lat": 0, "lon": 0 },
  "warnings": [],
  "paths": { "great_circle": [[0, 0]], "rhumb": [[0, 0]] },
  "markers": { "midpoint": {"lat":0,"lon":0}, "vertex": {"lat":0,"lon":0},
               "antipode_a": {"lat":0,"lon":0}, "antipode_b": {"lat":0,"lon":0} },
  "metrics": [
    {
      "id": "distance_haversine", "group": "Geometry", "label": "Great-circle distance",
      "value": 0.0, "unit": "km", "display": "…", "secondary": ["… nm", "… mi"],
      "explanation": {
        "summary": "…",
        "steps": [ { "label": "…", "tex": "…", "substituted_tex": null, "result": "…" } ],
        "constants": [ { "symbol": "R", "value": "6371.0088 km", "meaning": "mean Earth radius" } ],
        "notes": ["…"]
      }
    }
  ]
}
```
The values above only show the shape. Do not use them as test values.

Rules:
- `markers.vertex` is `null` when the vertex is not on the segment. `markers.midpoint` is `null` for antipodal input.
- A metric `value` is the primary scalar. It is `null` in edge cases (then `display` is a short reason such as "undefined") and also for metrics that have no single scalar (`antipodes`). `display` is always present.
- A metric may carry an optional `table` (`[{label, display}]`, used by `travel_times`). A step's `tex` may be `null` for text-only steps.
- Metric ids in panel order (20; defined once as `ORDER` in `metrics.py`, which sorts the metrics at the end): `distance_haversine`, `ellipsoid_lambert`, `mercator_distortion`, `midpoint`, `vertex_latitude`, `crossings`, `rhumb_line`, `antipodes`, `chord_and_bulge`, `gravity_train`, `flight_time`, `bearing_initial`, `bearing_final`, `latency`, `travel_times`, `horizon_los`, `solar_offset`, `timezone_diff`, `sun_a`, `sun_b`.
- `markers.crossings` is a list of `{id, label, lat, lon, km_from_a, fraction, course_deg}` in travel order (empty when undefined); `id` is one of `equator`, `tropic_cancer`, `tropic_capricorn`, `arctic_circle`, `antarctic_circle`, `prime_meridian`, `antimeridian`. The `crossings` metric carries the same information as a `table`.
- `options.date` must be 1970-01-01 … 2049-12-31 (HTTP 422 otherwise). `options.overhead_min` no longer exists: it is split into `climb_descent_min` (part of the airborne time) and `taxi_min` (only in the gate-to-gate time).
- Groups: **Geometry** (distance → antipodes, including crossings), **Through the Earth** (chord, gravity train), **Travel** (flight time, the two courses, latency, travel times, horizon), **Sun & time** (solar offset, time zones, sun A/B).
- Numbers in steps are formatted to ~5 significant digits, with explicit units.

## 6. Edge cases (each needs a UI note)
- lat ∉ [−90, 90] or lon ∉ [−180, 180] → HTTP 422.
- **A == B**: distance 0; bearings `null` ("undefined for identical points"); no path.
- **Antipodal** (δ within 1e-9 of π): infinitely many great circles. Bearings and midpoint `null` with a warning; distance still πR; Lambert `null`. Path interpolation is refused (sin δ ≈ 0) already at ~1e-6 rad from π, with a warning.
- **A or B at a pole**: bearings from a pole are degenerate → `null` with a note. Rhumb is `null` (ψ → ∞). Mercator is `null` beyond ±85.0511°. The sun formula is guarded at cos φ = 0 (polar day/night decided from the sign of the declination).
- **Antimeridian crossing**: path longitudes must be unwrapped (continuous, ±360° adjustments) so MapLibre does not draw a line across the whole map.
- **Open ocean** (no timezone polygon): nominal zone round(λ/15) with a note.
- **Crossings**: undefined for identical or antipodal points. A route lying on the equator (or in a meridian plane) is reported as "runs along"; a circle the great circle never reaches (|sin φc| > C) or reaches only outside A–B is listed under "not crossed" with the reason. The course is `null` at a pole.
- **Time zones and dates**: offsets come from the bundled `tzdata` package only (`zoneinfo.reset_tzpath(to=[])` in `timezones.py`), reported with its IANA release. The data reflects today's rules and borders; future political decisions are unknowable, so dates after today assume the current rules continue. Allowed dates: 1970-01-01 … 2049-12-31.

## 7. Frontend behavior
**Layout:** full-screen globe with a **left-hand** side panel (~380 px, collapsible; bottom sheet on narrow screens). Dark, translucent, slightly blurred "glass" look with smooth transitions; it should look polished, not like a default template.

**Map (MapLibre, globe projection), offline:** local style in `mapstyle.js`: land and country borders from bundled Natural Earth GeoJSON, a graticule, country-name labels placed at each country's label point, glyphs served from `public/`. No network requests other than to the local backend.
- First click places A, second places B, third restarts with a new A. Markers are draggable; recalculate on drag end with light debounce and a loading state. Clicked longitudes are wrapped into [−180, 180] before calling the API.
- Great-circle path solid; rhumb dashed and muted (toggle). Midpoint, vertex and antipodes as small toggleable markers; the route crossings (equator, tropics, polar circles, 0°/180° meridians) as green labelled markers with their own "Crossings" toggle. "Swap A/B" and "Reset" buttons.

**Panel (top to bottom):**
- Coordinate inputs for A and B, in two-way sync with the markers. Typing coordinates is a first-class way to set points. A **DD | DMS | DDM** toggle (remembered in `localStorage`, optional) chooses how values are displayed and which grayed-out sample is shown as placeholder (`50.8659° N`, `50° 51′ 57.24″ N`, `50° 51.954′ N`). The parser (`parseCoord` in `format.js`) accepts every format in every mode — hemisphere letters N/S/E/W before or after, signed decimals, `°′″` or spaces — and the field is then normalized to the chosen format. The panel keeps the exact point values; the fields only show a rounded rendering. This is unit parsing/formatting only, not geodesy. A hint under the toggle (per mode) tells users the `° ′ ″` symbols are optional: spaces separate parts and a dot marks decimals. A **Wizard** button next to Reset (`wizard.js`) opens a modal with ONE scrollable form (not a multi-step flow). At the top the user picks the point (A/B) and the format (DD/DMS/DDM). Below, a Latitude and a Longitude section show only the fields that format needs (degrees; plus minutes; plus seconds), each with its own label, example placeholder and help text, and an N/S or E/W direction control (keyboard letters also work). Switching format converts what was typed so far (50.5 in DD becomes 50 30 0 in DMS); switching to a point that is already set prefills it. Validation is per field (ranges, whole numbers where required, minutes/seconds below 60, total not above 90°/180°); errors appear after a field is visited or on submit, all at once, and focus jumps to the first problem. A preview pinned above the buttons shows the resulting point in the chosen format plus decimal degrees; the footer offers "Set point X" and "Set X, then enter Y". Typing updates texts in place (no re-render), so focus is never lost. `modal.js` holds the overlay, Esc/backdrop close, focus trap and focus return, shared by the wizard and the explanation pop-up.
- Options: cruise speed, climb & descent allowance, taxiing allowance, date picker (limited to 1970-01-01 … 2049-12-31, with a note that time zones follow today's rules), observer heights.
- Metric cards grouped as in §5. Each shows label, big display value, secondary values, and a subtle "ƒ(x)" hint. The whole card is clickable (also Enter/Space).
- Disclaimer line: "Spherical Earth model, R = 6371.0088 km".

**Explanation pop-up:** modal with title, summary and ordered steps; each step shows label, KaTeX formula, KaTeX substituted formula (if present) and result. Below: constants table and notes. Closes on Esc, backdrop click, or close button. Focus trapped while open; returns to the card on close. "Copy as text" is a nice-to-have.

**Errors:** if the API is unreachable, show a banner ("Backend not running on :8000?").

## 8. Tests (pytest, backend)
Use analytic values; do not use web-sourced reference distances.
- (0,0)→(0,90): δ = π/2, d = πR/2 ≈ 10 007.56 km, initial bearing 90°. (0,0)→(90,0): d = πR/2, bearing 0°.
- (0,0)→(0,180): antipodal → d = πR, bearing `null`, warning present. Identical points → d = 0.
- Haversine ≈ law of cosines for medium distances (rel. tol 1e-9). Symmetry: d(A,B) = d(B,A); final bearing(A→B) = (initial(B→A) + 180) % 360.
- Rhumb along the equator or a meridian = great-circle distance; rhumb ≥ great circle (property test over random pairs).
- Midpoint equidistant from A and B (tol 1e-6 km). Interpolation at f = 0 / 1 equals A / B; all samples lie on the great circle.
- Chord for δ = π equals 2R; sagitta for δ = π equals R. Gravity train period π·√(R/g) ≈ 42.2 min.
- Sun: equator at an equinox → day length 12.0–12.2 h; 80° N on day 172 → polar day; day 355 → polar night; ±90° latitude does not divide by zero.
- Antimeridian: (0,170) → (0,−170) gives unwrapped, monotonic longitudes.
- Lambert: equatorial points differ from the sphere by about f-scale (sanity band), identical points → `null`; Lambert ≈ sphere within ~0.7% for any pair.
- Mercator: equator pairs → ratio 1; ratio ≥ 1 for pairs at the same latitude away from the equator; |φ| > 85.0511° → `null`.
- Horizon: h = 0 → 0; exact and √(2Rh) agree to <1% for h ≪ R; mutual LOS = sum of the two horizons.
- Time zones: points inside simple polygons resolve correctly; ocean point → nominal-zone fallback with a note; DST changes the offset between January and July for a European point.
- API: 422 on out-of-range input; response shape matches §5; every metric has ≥ 1 step.

## 9. Build order (milestones with acceptance checks)
Finish each milestone's acceptance check before moving on.

1. **M1 Backend skeleton.** `pyproject.toml` (fastapi, uvicorn[standard], pydantic, tzdata; dev: pytest, httpx), `app/main.py` with `/api/health`, `constants.py`, README stub, `.gitignore`. *Accept:* `uvicorn app.main:app --reload --port 8000` runs and `curl localhost:8000/api/health` → `{"status":"ok"}`.
2. **M2 Core spherical math.** `geo/spherical.py`, `geo/rhumb.py`, `geo/mercator.py`, tests from §8. *Accept:* `pytest` passes; only `math` imported in `geo/`.
3. **M3 Remaining calculations.** `geo/travel.py` (flight, latency, speed table, gravity train, horizon/LOS), `geo/sun.py`, `geo/ellipsoid.py`, `geo/pip.py`, timezone data preparation + `timezones.py`, tests. *Accept:* `pytest` passes, including polar day/night, equinox, timezone and DST cases.
4. **M4 Explanations + `/api/calculate`.** `explain.py`, `metrics.py` (all metrics in §5 order, each with summary/steps/constants/notes, steps reusing the same intermediates), `models.py`, the endpoint with validation, warnings and edge cases, API tests, and an early TeX-validity check (render the TeX strings with KaTeX in a small Node script). *Accept:* a `curl` with Düsseldorf → New York returns all metrics; every metric has ≥ 1 step; all TeX renders.
5. **M5 Frontend skeleton + offline globe.** Vite project, proxy `/api`, bundled Natural Earth data and glyphs, `mapstyle.js`, globe projection, click placement, draggable markers, Swap/Reset. *Accept:* `npm run dev` shows a spinnable globe with labels; two markers can be placed and dragged; browser network tab shows only localhost.
6. **M6 Left panel + paths.** `api.js` (fetch wrapper + error banner), `panel.js` (two-way coordinate sync, options, grouped cards), `format.js`; draw great-circle and rhumb lines; marker toggles; dark glass styling, responsive bottom sheet. *Accept:* moving a marker updates all cards; Tokyo → San Francisco draws correctly across the antimeridian; Europe → US visibly arcs north.
7. **M7 Explanation pop-up.** `popup.js` with KaTeX, constants table, notes, Esc/backdrop/close, focus trap, keyboard-accessible cards, optional "Copy as text". *Accept:* every card opens a pop-up whose formulas render without KaTeX errors (browser console clean).
8. **M8 Polish.** Edge-case UX (identical points, antipodes, poles show notes), loading state, backend-down banner, final README (what it is, how to run both processes, data attributions, spherical-model disclaimer). *Accept:* a fresh checkout following the README works, and the app functions with the network disabled.

Later ideas: multi-point routes with cumulative distance, geodesic polygon area (spherical excess), shareable URL (`?a=lat,lon&b=lat,lon`).
