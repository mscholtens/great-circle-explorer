# FEATURES — everything Great Circle Explorer can do

A user-facing list. Details: [METRICS.md](METRICS.md) (every metric), [MATH.md](MATH.md) (the formulas), [ARCHITECTURE.md](ARCHITECTURE.md) (how it is built), [README.md](../README.md) (how to run it). Everything works offline once installed.

## 1. Choosing the points
- **Click the globe:** the first click places A, the second B, a third starts over. Drag the pins to move them.
- **Typed coordinates** in the left panel, in three formats (switch with the DD | DMS | DDM toggle): decimal degrees, degrees-minutes-seconds, degrees and decimal minutes. Hemisphere letters N/S/E/W go before or after; the `° ′ ″` symbols are optional (spaces and dots are enough). Fields show grayed-out samples of the chosen format.
- **Wizard:** a single scrollable form with fields and help texts that adapt to the chosen format, live preview, per-field validation and "Set A, then enter B".
- **Start + course mode (inverse mode):** switch *Enter* to **Start + course** (in the panel, and as the first choice in the Wizard). Give only a start point A, a **course** (azimuth in degrees from true north) and a **distance**; the app calculates the destination B and shows every metric for the route to it. B is shown read-only; clicking the map moves A. Switching back to *Two points* keeps the calculated B as a normal point.
- **Airport and city search:** type an IATA code or a name (`CGN`, `Groningen`, `Santiago`) under A or B. Accents and case are ignored. About 3 200 airports with scheduled service and 1 500 cities of 300 000+ people are bundled. The nearest airport and city (with distance) are shown under each point.
- **Swap A/B** and **Reset**. Reset clears both points, the airport/city search boxes, the nearest-place hints and (in Start + course mode) the course and distance; it keeps your units, input mode, options and layer toggles.
- **Share link:** *Copy link* puts both points in the URL (`#a=lat,lon&b=lat,lon`); opening the link restores them.

## 2. The map
- **The globe fills the window:** on startup, on reload and when the window is resized (as long as you have not zoomed by hand), the globe is zoomed so that it fills the free part of the window between the panel, the toolbar and the pointer readout, with the Mediterranean in the middle. Collapsing the panel or switching between globe and flat map refits the view.
- **Globe or flat:** a *Globe | Flat* switch shows the same scene on a 3D globe or on a flat Mercator map (where the great circle visibly curves and the rhumb line is straight).
- **Toolbar on top of the map** with layer toggles: rhumb line, midpoint, vertex (highest latitude), route crossings, antipodes, **circles of equal distance**, **night**.
- **Circles of equal distance** around A and B, by default as large as the route (so each passes through the other point), or any radius you type.
- **Airports layer:** an **Airports** toggle shows every bundled airport as a dot (IATA code labels from zoom 4). Hovering shows its name, city and country; clicking an airport sets A or B at its exact coordinates and fills that point's search box with the airport, as a search would (a click elsewhere or a dragged pin empties the box) (first click A, second B; clicking a placed pin again removes that point so it can be chosen anew; in Start + course mode it sets A). Works on the globe and on the flat map.
- **Night shading** with a friendly **date and time picker**: a date, a time, a slider for the whole day (00:00–24:00), a **My time | UTC** switch (default: this computer's clock; the UTC equivalent is always shown) and a **Now** button that uses this computer's current date and time. The picker date is the same shared date as Options → Date (it also drives the sun, moon and time-zone cards). The point where the Sun is straight overhead is shown.
- **Crossings on the map:** equator, tropics, polar circles, 0° and 180° meridians, as labelled markers.
- **Destination path:** with "Project from A" (or in Start + course mode) the path from A and the destination are drawn.
- **Live coordinates** under the mouse pointer at the bottom of the map, in the chosen coordinate format.
- Fully local map: country outlines, borders, graticule and country-name labels from bundled data; collapsible panel (bottom sheet on narrow screens).

## 3. Metrics (click any card to see the calculation)
25 metrics in four groups, plus two optional ones.

**Geometry:** great-circle distance (km, nm, mi, cross-checked with the law of cosines) · **distance analysis** (the same two points measured ten ways, each tagged sphere or ellipsoid, compared with the Vincenty reference; the great circle is marked as the conventional method with its error margin; a summary separates the effect of the Earth model from the effect of the method; every row opens its calculation; a **Choose distances…** button opens a window with a check box per distance to declutter the table, all on by default, the reference always shown, the choice remembered in the browser) · **ellipsoid distance, Vincenty (reference)** (every iteration shown) · ellipsoid distance, Lambert (an approximation, with an accuracy warning for nearly antipodal pairs) · distance on a flat Mercator map and its distortion · midpoint · highest latitude reached (vertex) · **route crossings** with coordinates, distance, course and elapsed time · rhumb line (constant bearing) · **great circle vs rhumb line** (extra distance and time, and how far apart the two paths get) · antipodes · **scale on the Earth** (central angle, share of the circumference, laps) · *destination from A (optional)*.

**Through the Earth:** straight tunnel length and depth · gravity train (about 42 minutes, top speed).

**Travel:** **flight time** as airborne time (take-off to landing) with gate-to-gate time next to it · **course after take-off** and **course before landing** (also in radians and as an hour angle) · *return trip B → A (optional)* · light and fiber latency (minimum ping) · time at reference speeds (walking to Concorde, ISS, light) · horizon and line of sight.

**Sun & time:** solar time offset · **time-zone difference** (daylight saving included) for any date from 1 Jan 1970 to 31 Dec 2049, with a note that the rules are today's · sunrise, sunset and day length at A and at B (polar day and night handled) · **moon phase**.

### Example scene
Amsterdam Schiphol → Buenos Aires Ezeiza: open `http://localhost:5173/#a=52.3086,4.7639&b=-34.8222,-58.5358` (or search `AMS` and `EZE`), click the **Distance analysis** card, and switch the map to **Flat**. The straight line on the flat map is 13 045 km by the ruler, the great circle 11 462 km, the WGS84 geodesic (Vincenty) 11 437 km, and the two paths are up to about 450 km apart.

## 4. Explanations
- Every metric opens a pop-up with the steps of its calculation: the formula, the same formula with your numbers filled in, and the result of each step, followed by the constants used and notes on accuracy and assumptions.
- Formulas are rendered offline with KaTeX. *Copy as text* copies the whole calculation.
- Esc, a click outside or the close button closes it; keyboard focus is trapped inside and returned afterwards.

## 5. Options
- Cruise speed, climb and descent allowance, taxiing allowance (flight time).
- Date for the sun, moon and time-zone metrics and the night shading (1970–2049; future dates assume today's time-zone rules). The same date is shown in the Night picker on the map; changing it in either place updates the other.
- Observer eye heights (horizon and line of sight).
- **Project from A:** a bearing and a distance give the destination point, as a card and on the globe.
- **Include return trip (B → A).**
- **Distance units:** km, nautical miles or statute miles (speeds in km/h, knots or mph). The cards and the option fields follow the unit; the step-by-step calculations stay in km and say so.

## 6. Export
- **PDF report:** *Export PDF* opens a form: choose a title, which metrics to include, whether to include the **full calculation** (steps, formulas, constants and notes), and whether to include a picture of the map. The browser's print dialog then opens; choose *Save as PDF*. The report is a clean white A4 document with crisp (vector) formulas.
- **Copy link** (see section 1) and **Copy as text** for a single calculation.

## 7. Offline and data
- No internet at runtime: no CDN, tiles, geocoding or external API. Libraries are bundled; map data, fonts, time-zone boundaries, the IANA time-zone database (release shown on the time-zone card), airports and cities are local files.
- `tools/fetch_data.py` rebuilds the bundled data once (needs internet).
- All geodesy is hand-written Python (`math` only) on a spherical Earth (R = 6371.0088 km); the ellipsoid distance uses Vincenty's and Lambert's formulas on WGS84. The frontend only draws what the backend returns.

## 8. HTTP API (local, port 8000)
`POST /api/calculate` (two points, or a start point with a course) · `GET /api/terminator` (night side for a UTC date and time) · `GET /api/places` (airport/city search) · `GET /api/airports` (all airports, for the map layer) · `GET /api/nearest` · `GET /api/units` · `GET /api/health`. Details in [ARCHITECTURE.md](ARCHITECTURE.md).

## 9. Quality
- 118 backend tests (analytic values, property tests, API shape and validation), a strict-KaTeX check of every formula the API returns (`npm run check:tex`), and keyboard-accessible controls (listboxes, radio groups, focus trap in dialogs).

## 10. Accuracy and license
- The accuracy of every part is measured against independent references (GeographicLib, PyEphem, TimezoneFinder) and documented, with all assumptions, in [ACCURACY.md](ACCURACY.md). **For learning and exploration only: not for production use or real-life navigation.**
- Released under the MIT License ([LICENSE](../LICENSE)); data and library notices in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Not included
Fuel and CO₂ estimates, real airways and winds, a geocoder beyond the bundled airports and cities, user accounts or a database, containers or cloud hosting.
