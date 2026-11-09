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
      ellipsoid.py     # Vincenty's inverse formula (reference), Lambert's formula, ECEF chord on WGS84
      mercator.py      # isometric latitude, flat-map distance, scale factor
      sun.py           # Sun position (low-precision formulas, takes a Julian date), sunrise/sunset, sub-solar point, terminator
      moon.py          # Moon position (short series), elongation, lit fraction, phase name, time of the next/previous new or full moon
      travel.py        # flight time, speeds, light/fiber latency, gravity train, horizon/line of sight
      pip.py           # ray-casting point-in-polygon
    data/              # bundled simplified timezone boundaries (GeoJSON) and places.json (airports + cities)
    places.py          # airport/city search and nearest place (uses geo/spherical.haversine); lives outside geo/
    timezones.py       # zone lookup (pip.py + data) and UTC offsets (zoneinfo); lives outside geo/
    explain.py         # Step(label, tex, substituted_tex, result), number formatter (~5 significant digits)
    metrics.py         # assembles all metrics for a pair of points; converts date -> Julian date; also the circles/projection overlays
    overlays.py        # day/night boundary for a UTC date and time (uses geo/sun.py)
  tests/
frontend/
  package.json
  vite.config.js       # proxies /api -> http://localhost:8000
  index.html
  public/              # bundled country GeoJSON, label glyphs (PBF), nothing fetched at runtime
  src/
    config.js
    mapstyle.js        # local MapLibre style: land, borders, graticule, country labels
    main.js  api.js  map.js  panel.js  toolbar.js  popup.js  wizard.js  modal.js  format.js  styles.css
    instant.js         # date + time (computer's clock or UTC) <-> UTC instant, clamped to 1970–2049 (pure functions, used by the Night picker)
    explanation.js     # step / constants / notes builders (KaTeX), shared by the pop-up and the PDF report
    search.js          # airport/city combobox + nearest-place hint
    share.js           # URL hash <-> points (#a=lat,lon&b=lat,lon)
    report.js          # PDF export form + printable report (print dialog)
    unitfield.js       # number input shown in the chosen unit, kept exactly in km
tools/
  fetch_data.py        # one-time, needs internet: builds the bundled map, glyph, places and timezone data
  verify_accuracy.py   # optional: compares the maths with GeographicLib, PyEphem and TimezoneFinder (installed separately)
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

`GET /api/terminator?date=YYYY-MM-DD&time=HH:MM` → the night side of the Earth at a UTC date and time: `{ date, time, subsolar: {lat, lon}, declination_deg, eot_min, polygon: [[lon, lat], …] }` (the polygon is the closed night ring; 422 for dates outside 1970-01-01 … 2049-12-31 or an invalid time). It does not depend on A and B.

`GET /api/places?q=cgn&limit=8` → airports (IATA code) and cities matching a code or name, best first: `[{kind, code, name, city, country, lat, lon, label, detail}]`. Matching ignores case and accents (`koln` finds Köln); ranking: exact code, code prefix, name/city prefix, word prefix, substring. `q` is 1–80 characters, `limit` 1–20 (422 otherwise).

`GET /api/airports` → every bundled airport `[{code, name, city, country, lat, lon}]` (about 3 200 entries, ~400 KB, loaded once by the frontend when the Airports layer is first switched on).

`GET /api/nearest?lat=&lon=` → `{ airport, city }`, each the nearest place with `km` (haversine, hand-written); ranges validated (422).

`GET /api/units` → `[{id, label, speed_label, km_per_unit}]` for `km`, `nm`, `mi`, so the frontend never repeats a conversion factor.

`POST /api/calculate`

Request (`options` and every field in it are optional; give **either** `b` **or** `course`, never both and never neither, otherwise 422):
```json
{
  "a": { "lat": 51.2277, "lon": 6.7735 },
  "b": { "lat": 40.6413, "lon": -73.7781 },
  "options": { "cruise_kmh": 850, "climb_descent_min": 15, "taxi_min": 15, "date": "2026-11-09",
               "height_a_m": 1.7, "height_b_m": 1.7,
               "project_bearing_deg": 90, "project_km": 1000, "include_return": false, "circle_km": 5000, "units": "km" }
}
```

Response:
```json
{
  "a": { "lat": 0, "lon": 0 }, "b": { "lat": 0, "lon": 0 },
  "warnings": [],
  "paths": { "great_circle": [[0, 0]], "rhumb": [[0, 0]], "projection": [] },
  "markers": { "midpoint": {"lat":0,"lon":0}, "vertex": {"lat":0,"lon":0},
               "antipode_a": {"lat":0,"lon":0}, "antipode_b": {"lat":0,"lon":0},
               "crossings": [], "projected": null },
  "circles": [ { "center": "a", "radius_km": 0, "segments": [[[0, 0]]] } ],
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
**Inverse mode:** instead of `b`, the request may hold `"course": { "bearing_deg": 0–360, "km": 0–100000 }`. The backend then computes B as the destination from A (`metrics.destination_point`, the direct problem), runs every metric for A → B, returns B in `b` (rounded to 6 decimals), sets the `destination` metric and `markers.projected` from the course, and ignores `options.project_*`.

The values above only show the shape. Do not use them as test values.

Rules:
- `markers.vertex` is `null` when the vertex is not on the segment. `markers.midpoint` is `null` for antipodal input.
- A metric `value` is the primary scalar. It is `null` in edge cases (then `display` is a short reason such as "undefined") and also for metrics that have no single scalar (`antipodes`). `display` is always present.
- A metric may carry an optional `table` (`[{label, display}]`, used by `travel_times`). A step's `tex` may be `null` for text-only steps.
- Metric ids in panel order (25, plus 2 optional; defined once as `ORDER` in `metrics.py`, which sorts the metrics at the end): `distance_haversine`, `distance_analysis`, `ellipsoid_vincenty`, `ellipsoid_lambert`, `mercator_distortion`, `midpoint`, `vertex_latitude`, `crossings`, `rhumb_line`, `rhumb_vs_great_circle`, `antipodes`, `earth_scale`, `destination` (optional), `chord_and_bulge`, `gravity_train`, `flight_time`, `bearing_initial`, `bearing_final`, `return_trip` (optional), `latency`, `travel_times`, `horizon_los`, `solar_offset`, `timezone_diff`, `sun_a`, `sun_b`, `moon_phase`.
- **`analysis`** (only on the `distance_analysis` metric): `{ reference_id, reference_label, rows: [{ id, label, what, km, display, diff_km, diff_display, diff_pct, is_reference, model, badges, vs_sphere_km, vs_sphere_pct, vs_sphere_display, metric_id, explanation }], summary, footnotes }`, ten rows sorted shortest first (the reference leads equal values). `model` is `ellipsoid` or `sphere`; `badges` holds `reference` and/or `conventional`; the `vs_sphere_*` fields (sphere-based methods only) give the difference to the great circle on the same sphere; `summary` has the two backend-computed "what changes the answer" sentences (Earth model, method) and `footnotes` the sphere note and the conventional-method note with its error margin. `reference_id` is `vincenty`, or `lambert` when Vincenty does not converge, or `great_circle_mean` when neither exists. `metric_id` names the metric whose explanation a click opens; the rows without a metric (tunnel on the ellipsoid, polar and equatorial sphere, programmer's shortcut, flat grid) carry their own `explanation` (and `km` is null with the reason in `display` when a measure is undefined). The frontend (`popup.openAnalysis`) draws one clickable row per entry with a bar (width relative to the longest, a white tick at the reference length), opens the row's calculation in the normal explanation pop-up with a "← Distance analysis" button, and prints the card's `table` in the PDF.
- **Optional metrics** exist only when asked for: `destination` needs both `project_bearing_deg` (0–360) and `project_km` (≥ 0, ≤ 100 000; one alone is ignored), `return_trip` needs `include_return: true`. Out-of-range values are rejected with 422. When `destination` exists, `markers.projected` is `{lat, lon, bearing_deg, km}` and `paths.projection` the sampled path from A (both empty/`null` otherwise).
- `circles` always holds two entries (`center` `"a"` and `"b"`) unless the radius is 0 (identical points): the circle of radius `radius_km` around each point, as `segments` (polylines of `[lon, lat]`, cut at the antimeridian so they meet exactly at ±180°). `radius_km` is the route length unless `options.circle_km` (0 … πR) is set.
- `markers.crossings` is a list of `{id, label, lat, lon, km_from_a, fraction, course_deg}` in travel order (empty when undefined); `id` is one of `equator`, `tropic_cancer`, `tropic_capricorn`, `arctic_circle`, `antarctic_circle`, `prime_meridian`, `antimeridian`. The `crossings` metric carries the same information as a `table`.
- **Units:** `options.units` (`km` default, `nm`, `mi`; 422 otherwise) changes how distances and speeds are written on the cards (`display`, `secondary`, `table`); numeric `value`s stay in km. The explanation steps keep calculating in km: each affected explanation gets a final step "Convert to {unit} for the card" and a note, so with `km` nothing is added. The panel shows and accepts the option fields (speed, projection distance, circle radius) in the chosen unit and sends km (`unitfield.js`, factors from `/api/units`).
- `options.date` must be 1970-01-01 … 2049-12-31 (HTTP 422 otherwise). `options.overhead_min` no longer exists: it is split into `climb_descent_min` (part of the airborne time) and `taxi_min` (only in the gate-to-gate time).
- Groups: **Geometry** (distance → antipodes, including crossings), **Through the Earth** (chord, gravity train), **Travel** (flight time, the two courses, latency, travel times, horizon), **Sun & time** (solar offset, time zones, sun A/B, moon phase).
- Numbers in steps are formatted to ~5 significant digits, with explicit units.

## 6. Edge cases (each needs a UI note)
- lat ∉ [−90, 90] or lon ∉ [−180, 180] → HTTP 422.
- **A == B**: distance 0; bearings `null` ("undefined for identical points"); no path.
- **Antipodal** (δ within 1e-9 of π): infinitely many great circles. Bearings and midpoint `null` with a warning; distance still πR; Lambert `null`. Path interpolation is refused (sin δ ≈ 0) already at ~1e-6 rad from π, with a warning.
- **A or B at a pole**: bearings from a pole are degenerate → `null` with a note. Rhumb is `null` (ψ → ∞). Mercator is `null` beyond ±85.0511°. The sun formula is guarded at cos φ = 0 (polar day/night decided from the sign of the declination).
- **Antimeridian crossing**: path longitudes must be unwrapped (continuous, ±360° adjustments) so MapLibre does not draw a line across the whole map.
- **Open ocean** (no timezone polygon): nominal zone round(λ/15) with a note.
- **Crossings**: undefined for identical or antipodal points. A route lying on the equator (or in a meridian plane) is reported as "runs along"; a circle the great circle never reaches (|sin φc| > C) or reaches only outside A–B is listed under "not crossed" with the reason. The course is `null` at a pole.
- **Overlays**: the circle of radius πR collapses to the antipode, a radius of 0 gives no circle; a circle may cross the date line more than once (several segments). The night polygon is closed along the pole in darkness at ±89.9°, so it never reaches a pole exactly (Web-Mercator tiles end near 85°). At an exact equinox the boundary degenerates to two meridians (handled by `atan2`).
- **Time zones and dates**: offsets come from the bundled `tzdata` package only (`zoneinfo.reset_tzpath(to=[])` in `timezones.py`), reported with its IANA release. The data reflects today's rules and borders; future political decisions are unknowable, so dates after today assume the current rules continue. Allowed dates: 1970-01-01 … 2049-12-31. Zone lookup: the smallest containing polygon wins when polygons overlap; a point in none but within `TZ_NEAR_BORDER_KM` (15) of one gets the nearest zone (`near_km` in `zone_info`, noted on the card); only further out the nominal ocean zone applies. The bundled polygons are rebuilt with small rings simplified less coarsely so enclaves (Melilla) survive.

## 7. Frontend behavior
**Layout:** full-screen globe with a **left-hand** side panel (~380 px, collapsible; bottom sheet on narrow screens). Dark, translucent, slightly blurred "glass" look with smooth transitions; it should look polished, not like a default template.

**Map (MapLibre, globe projection), offline:** local style in `mapstyle.js`: land and country borders from bundled Natural Earth GeoJSON, a graticule, country-name labels placed at each country's label point, glyphs served from `public/`. No network requests other than to the local backend.
- First click places A, second places B, third restarts with a new A. Markers are draggable; recalculate on drag end with light debounce and a loading state. Clicked longitudes are wrapped into [−180, 180] before calling the API.
- Great-circle path solid; rhumb dashed and muted. A **toolbar on top of the map** (`toolbar.js`, centred over the map area, moves left when the panel is collapsed) holds the layer toggles: Rhumb line, Midpoint, Vertex, Crossings (green labelled markers), Antipodes, **Equal-distance circles** (dashed in the colour of A and B, with a radius field, empty = route length) and **Airports** and **Night** (dark shading plus a yellow sub-solar point). The Airports toggle fetches `/api/airports` once (cached), fills a GeoJSON source `airports` and shows a small dot layer plus an IATA-code label layer (from zoom 4, `text-optional` so MapLibre's collision handling thins them out); hovering a dot shows a tooltip (code, name, city, country), and the map `click` handler first checks `queryRenderedFeatures` (a 12 px box) on the dot layer and, on a hit, calls the normal `onMapClick` with the airport's exact coordinates (read from the feature properties, not the tile geometry), so the A/B/restart rules and the Start + course rule "a click moves A" apply unchanged.
- **Night picker (`toolbar.js` + `instant.js`):** date input (1970-01-01 … 2049-12-31), time input, a 24 h slider (5-minute steps, 120 ms debounce), a **My time | UTC** switch (remembered in `localStorage`, default My time) and a **Now** button (the computer's current date and time in the chosen clock). In My time the typed local date and time are converted to UTC with the browser's own time-zone rules (`new Date(y, m-1, d, h, mi)`, so daylight saving is right) and clamped to the 1970–2049 range, then sent to `GET /api/terminator`; the UTC equivalent is always shown ("= 2026-06-21 10:00 UTC") next to the sub-solar point. Switching the clock keeps the same instant. **The date is the shared date**: `onDateChanged` updates Options → Date, the sun, moon and time-zone cards and the shading; changing Options → Date updates the picker (`toolbar.setDate`). The conversion is input handling only; the shading itself is calculated in Python. Night data refresh when the toggle, the date, the time, the slider or the clock changes; stale responses are dropped. The projection (when both "Project from A" fields are filled) is a purple dashed path with a "Destination" marker. "Swap A/B" and "Reset" stay in the panel. **Reset** clears A, B, both search boxes (`createSearch(...).clear()` also cancels a pending request), the nearest hints and the course/distance inputs; units, input mode, options and layer toggles are kept.
- **Inverse mode (start + course):** a segmented control "Two points | Start + course" at the top of the coordinate section (remembered in `localStorage`). In *Start + course* only A is entered; a box with **Course (°)** and **Distance** (in the chosen unit, kept exactly in km by `unitfield.js`) appears under A, the B fields become read-only and show the calculated destination, the B search and *Swap A/B* are disabled, a map click moves A, and B's pin is not draggable. The request is sent with `course` instead of `b` once both values are valid (otherwise B and the results are cleared); the returned `b` becomes `state.b`, so the share link, the nearest-place hint and the PDF ("Point B (calculated)" plus a course line) work as usual. Switching back to *Two points* keeps the calculated B as an ordinary editable point; opening a share link also switches to *Two points*. The wizard has the same choice at the top ("What do you want to enter?"): in *Start, course and distance* it shows the start point fields plus Course and Distance fields (validated, unit-aware, prefilled from the panel) and applies all three at once.
- **Flat/globe:** a "Globe | Flat" switch in the toolbar calls `map.setProjection` (globe or Mercator); remembered in `localStorage`.
- **Airport/city search:** each point has a search box (combobox with listbox, arrow keys, Enter, Esc, 150 ms debounce, stale responses dropped; the pick sets the point through the normal edit path) and a hint with the nearest airport and city (`/api/nearest`, asked only when the point changed; distances in the chosen unit).
- **Share link (`share.js`):** the hash `#a=lat,lon&b=lat,lon` (6 decimals) is rewritten with `history.replaceState` after every change and read on load and on `hashchange`. Invalid points (non-numeric, out of range) are ignored; nothing else (options, units) is in the link. The panel's *Copy link* button copies `location.href`.
- **PDF export (`report.js`):** *Export PDF* opens a form (title, "include the full calculation", "include a picture of the map", a checkbox per existing metric grouped as in the panel with All/None; choices remembered in `localStorage`). It then builds `#print-root` (title, points in the chosen format, options, optional map picture, selected metrics, optionally steps/constants/notes via `explanation.js`), lays it out off-screen so the KaTeX fonts are loaded, and calls `window.print()`; the user chooses "Save as PDF". `@media print` hides everything except `#print-root` and uses a light theme with A4 margins; `afterprint` removes the report. The map picture crops the canvas to the area right of the panel and draws the A/B pins on it (the map is created with `preserveDrawingBuffer`).
- **Pointer readout** at the bottom of the map: live latitude/longitude under the mouse pointer from MapLibre (`map.on('mousemove')`), formatted in the chosen DD/DMS/DDM format; empty off the globe; hidden on narrow (touch) screens. It is a readout only (no backend call, no geodesy).

**Panel (top to bottom):**
- Coordinate inputs for A and B, in two-way sync with the markers. Typing coordinates is a first-class way to set points. A **DD | DMS | DDM** toggle (remembered in `localStorage`, optional) chooses how values are displayed and which grayed-out sample is shown as placeholder (`50.8659° N`, `50° 51′ 57.24″ N`, `50° 51.954′ N`). The parser (`parseCoord` in `format.js`) accepts every format in every mode — hemisphere letters N/S/E/W before or after, signed decimals, `°′″` or spaces — and the field is then normalized to the chosen format. The panel keeps the exact point values; the fields only show a rounded rendering. This is unit parsing/formatting only, not geodesy. A hint under the toggle (per mode) tells users the `° ′ ″` symbols are optional: spaces separate parts and a dot marks decimals. A **Wizard** button next to Reset (`wizard.js`) opens a modal with ONE scrollable form (not a multi-step flow). At the top the user picks the point (A/B) and the format (DD/DMS/DDM). Below, a Latitude and a Longitude section show only the fields that format needs (degrees; plus minutes; plus seconds), each with its own label, example placeholder and help text, and an N/S or E/W direction control (keyboard letters also work). Switching format converts what was typed so far (50.5 in DD becomes 50 30 0 in DMS); switching to a point that is already set prefills it. Validation is per field (ranges, whole numbers where required, minutes/seconds below 60, total not above 90°/180°); errors appear after a field is visited or on submit, all at once, and focus jumps to the first problem. A preview pinned above the buttons shows the resulting point in the chosen format plus decimal degrees; the footer offers "Set point X" and "Set X, then enter Y". Typing updates texts in place (no re-render), so focus is never lost. `modal.js` holds the overlay, Esc/backdrop close, focus trap and focus return, shared by the wizard and the explanation pop-up.
- Options: cruise speed, climb & descent allowance, taxiing allowance, date picker (limited to 1970-01-01 … 2049-12-31, with a note that time zones follow today's rules), observer heights, the two optional "Project from A" fields (bearing and distance, empty by default) and an "Include return trip (B → A)" checkbox. The layer toggles are no longer in the panel.
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
- Lambert: equatorial points differ from the sphere by about f-scale (sanity band), identical points → `null`; Lambert ≈ sphere within ~0.7% for any pair. The accuracy claims in `docs/ACCURACY.md` are measured with `tools/verify_accuracy.py`; the tests store reference values from PyEphem (Sun declination and equation of time, sunrise/sunset, lit fraction and new/full moon times) so a regression in the astronomy fails without the library being installed.
- Mercator: equator pairs → ratio 1; ratio ≥ 1 for pairs at the same latitude away from the equator; |φ| > 85.0511° → `null`.
- Horizon: h = 0 → 0; exact and √(2Rh) agree to <1% for h ≪ R; mutual LOS = sum of the two horizons.
- Time zones: points inside simple polygons resolve correctly; ocean point → nominal-zone fallback with a note; DST changes the offset between January and July for a European point.
- Inverse mode: B from (0°,0°), bearing 90°, a quarter circumference is (0°, 90°E); the metrics equal those of the same scene given as two points; the (initial bearing, distance) of a route reproduce its B; exactly one of `b`/`course` (422 otherwise, also for a bearing outside 0–360 or a negative distance); zero distance (B = A), half the circumference (antipode) and more than half (note about the antipode) are handled.
- Distance analysis: the ten Cologne → Santiago rows with the values from an independent computation (GeographicLib/Karney and a separate Vincenty implementation), shortest-first order, model tags, the reference and conventional badges, the "vs same sphere" text, the summary and footnotes, the Vincenty fallback for (0,0) → (0.5,179.7), Quito → Singapore (converges in 11 rounds: regression test for a missing |λ| > π shortcut), exactly antipodal points, units; the grid measure (exactly πR/2 along the equator and a meridian, short way across ±180°); `max_separation` (0 for identical paths, the shift for a shifted copy, 450 km for AMS → EZE against a brute-force search); a regression test for double superscripts in TeX (tiny angles like 10⁻¹⁵°).
- Accuracy hints: the Lambert card warns for pairs more than 170° apart (tier text from `constants.LAMBERT_ERROR_TIERS`; stored GeographicLib distances check that the real error stays inside the stated tier) and the Sun card hints for days of 21 h or more, polar states and nothing for ordinary days.
- Airports: `/api/airports` has > 3 000 unique 3-letter codes with valid coordinates and contains CGN, SCL and GRQ with the expected data.
- Moon: age 0 and 0 % lit at the epoch, 100 % half a month later, 8 phase names at the 1/8 boundaries, a known full moon (21 Jan 2000) within a day. Places: exact code ranks first, accents/case ignored, nearest to an airport's own coordinates is that airport (distance cross-checked with haversine), 422 on bad ranges. Units: cards change by the exact factors, `value`s do not, km adds nothing to the explanation, mi/nm add the conversion step and note, `/api/units` shape.
- Vincenty: agrees with the exact geodesic to 1 mm for five reference routes (equator = a·π/2, quarter meridian, AMS → EZE, Cologne → Santiago, Quito → Singapore), no result for nearly antipodal, exactly antipodal and pole-to-pole pairs, identical points 0, symmetric; ECEF chord = a·√2 along the equator quarter; three radii; equirectangular shortcut.
- Direct problem: (0°,0°) bearing 90° at πR/2 → (0°, 90°E); bearing 0° from the equator at πR/2 → the pole; destination of (initial bearing, distance) of a route reaches B; random round trips agree to 1e-9. `split_antimeridian` pieces meet exactly at ±π. Sub-solar point and terminator: every boundary point has Sun altitude 0 (1e-9), the closing pole is in darkness, equinox gives ±90°.
- Rhumb comparison ≥ 0 and 0 along the equator and a meridian; earth scale 50 % at the antipode, 25 % for a quarter circle; return courses = outbound courses ± 180° (final/initial swapped); optional metrics absent unless asked; circles: every vertex at the radius from its centre, cut into 3 pieces for a circle crossing the date line twice; `/api/terminator` shape, closing pole and 422 cases.
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
