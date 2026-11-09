# CLAUDE.md — Great Circle Explorer

Homelab web app: click two points on a 3D globe and see distance, flight time and other metrics in a **left-hand** side panel. **Click any metric to open a pop-up that shows the full calculation, step by step.**

Read these before writing code:
- `docs/ARCHITECTURE.md`: design decisions, API contract, edge cases, UI behavior, tests, and the **build order** (milestones with acceptance checks)
- `docs/MATH.md`: the formulas for every metric
- `docs/METRICS.md`: the catalogue of metrics, their ids and groups
- `docs/FEATURES.md`: the complete list of user-facing features (keep it updated when a feature is added)
- `docs/ACCURACY.md`: every assumption and the measured accuracy (keep it updated when a formula or data source changes; re-run `tools/verify_accuracy.py` and copy the numbers)

## Hard rules

1. **Classical math only.** All geodesy uses Python's `math` module (sin, cos, atan2, sqrt, log, …) on a **spherical Earth** (plus Vincenty's and Lambert's formulas on WGS84 for the ellipsoid distance, also hand-written). Do NOT use pyproj, geopy, geographiclib, the `haversine` package, shapely, numpy or any other geo or math library. The point of the project is that the math is visible and hand-written. `geo/` imports only `math`.
2. **Python is the single source of truth.** Every number shown in the UI, and every step in the explanation pop-ups, is computed by the backend. The frontend does not do geodesy. It only renders what the API returns, including the path coordinates drawn on the map.
3. **Every metric is explainable.** A metric is not done until its `explanation` (formula, substituted values, intermediate results) is returned by the API and renders correctly in the pop-up.
4. **Runs locally as two processes.** The backend (FastAPI) and the frontend (Vite dev server) are separate processes; `./run.sh` starts both with one command (and each can still be started by hand). No containers, no cloud hosting.
5. **Learning project, not a navigation tool.** README, the app footer and the PDF report say so; keep that wording and never present the results as suitable for real-life navigation or safety decisions. Any new simplification or inaccuracy must be written down in `docs/ACCURACY.md`.
6. **Fully offline at runtime.** No internet and no external API calls: no CDN, no online tile servers, no geocoding. Libraries come from npm and are bundled by Vite. Map data (Natural Earth country GeoJSON), label glyphs and time-zone boundaries are local files in the repo.

## Stack

- **Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2, `tzdata`, pytest. A plain venv + `pip install -e '.[dev]'` (`uv` also works but is not required).
- **Frontend:** plain JavaScript (ES modules, no framework) + Vite, MapLibre GL JS (globe projection), KaTeX for rendering formulas.
- **Map:** a local MapLibre style (`frontend/src/mapstyle.js`) with bundled country outlines, graticule and country-name labels. No remote tiles.

Check the current MapLibre GL JS docs for the globe projection API before using it. Don't rely on memory for the exact call.

## Repository layout (target)

```
backend/
  pyproject.toml
  app/
    main.py            # FastAPI app, routes
    models.py          # Pydantic request/response models
    constants.py       # R, c, g, fiber index, WGS84, default speeds…
    geo/
      crossings.py     # where the route crosses equator, tropics, polar circles, meridians (vector maths)
      spherical.py     # haversine, law of cosines, bearings, midpoint, interpolation, direct problem (destination), antimeridian splitting, vertex, antipode, chord
      rhumb.py         # rhumb line distance, bearing, interpolation
      ellipsoid.py     # Vincenty's inverse formula (reference), Lambert's formula, ECEF chord on WGS84
      mercator.py      # flat-map (Mercator) distance and scale factor
      sun.py           # declination, day length, sunrise/sunset, sub-solar point and day/night boundary (approx.)
      moon.py          # moon phase from the Moon's and the Sun's positions
      travel.py        # flight time, speeds, light/fiber latency, gravity train, horizon / line of sight
      pip.py           # point-in-polygon (ray casting)
    data/              # bundled timezone boundaries, places.json (airports + cities)
    places.py          # airport/city search, airports list and nearest place (outside geo/)
    timezones.py       # zone lookup + UTC offsets (zoneinfo)
    explain.py         # helpers to build explanation steps (TeX + values)
    metrics.py         # assembles all metrics for a pair of points (+ circles/projection overlays)
    overlays.py        # day/night boundary for GET /api/terminator
  tests/
frontend/
  package.json
  vite.config.js       # proxies /api -> http://localhost:8000
  index.html
  public/              # bundled map data and label glyphs
  src/
    config.js
    mapstyle.js
    main.js
    api.js
    map.js
    panel.js
    popup.js
    explanation.js     # steps/constants/notes builders shared by the pop-up and the PDF report
    search.js  share.js  report.js  unitfield.js   # airport search, URL hash, PDF export (print dialog), unit inputs
    toolbar.js         # map-layer toggles (incl. airports), circles and the night date/time picker on top of the map
    instant.js         # date + time (local or UTC) -> UTC instant, clamped to 1970–2049
    wizard.js          # coordinate entry modal (one scrollable form)
    modal.js           # shared overlay / focus-trap behavior
    format.js
    styles.css
tools/
  fetch_data.py        # one-time (needs internet): builds the bundled map, glyph, places and timezone data
  verify_accuracy.py   # optional: compares the maths with independent libraries (installed separately)
docs/
  ARCHITECTURE.md  MATH.md  METRICS.md  FEATURES.md  ACCURACY.md  EXECUTIVE_SUMMARY.md
LICENSE  THIRD_PARTY_NOTICES.md  README.md
```

## Commands

```bash
./run.sh                     # everything: sets up on first run, starts backend + frontend, Ctrl+C stops both

# or by hand — backend (terminal 1)
cd backend
python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'    # first time only (uv is optional)
uvicorn app.main:app --reload --port 8000
python -m pytest

# frontend (terminal 2)
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

## Conventions

- Inside the geo functions, angles are radians. The API takes and returns degrees. Convert at the boundary.
- Coordinates in API payloads are objects `{ "lat": .., "lon": .. }`. Path arrays for the map are GeoJSON order `[lon, lat]`.
- Every geo function is a pure function with a docstring that states the formula. Keep each one small, and test it against analytic values (see ARCHITECTURE.md §8).
- Don't hide magic numbers. Every constant lives in `constants.py` with a comment giving its source or meaning, and it appears in the explanation's `constants` list.
- Date handling (date → Julian date) and the timezone lookup live outside `geo/` (in `metrics.py` / `timezones.py`).
- Keep the README updated with run instructions. Keep MATH.md and METRICS.md in sync when a metric or formula changes.
- The user handles git themselves; don't run git commands unless asked.
