# Executive summary — Great Circle Explorer

**What it is.** A small web application for a home lab. The user picks two points on a 3D globe (by clicking, or by typing coordinates in the left-hand panel) and instantly sees how far apart they are and a set of related facts: real distance over the curved Earth, bearings, flight time, minimum network latency, sunrise and sunset, time-zone difference, and more.

**What makes it different.** Every number can be inspected. Clicking a metric opens a pop-up that shows the formula, the same formula with the actual numbers substituted, the intermediate results, and the final answer. It is meant to teach how distance on a sphere is really calculated using sine, cosine and related functions.

**How it works.** A Python backend (FastAPI) does *all* the math using only the standard `math` module on a spherical Earth, with no geodesy libraries. A plain JavaScript frontend (Vite, MapLibre GL JS, KaTeX) only draws what the backend returns. The two run as separate processes started by hand.

**Runs fully offline.** No internet connection and no external API calls are needed at runtime. Libraries are bundled, and the map is drawn from locally stored country outlines, labels, and time-zone boundaries.

**Scope.** 20 metrics in four groups (Geometry, Through the Earth, Travel, Sun & time), including the places where the route crosses the equator, the tropics, the polar circles and the 0° and 180° meridians, a flight time split into airborne time and gate-to-gate time with the courses after take-off and before landing, time zones for any date from 1970 to 2049, and comparisons that put the spherical result in context: the WGS84 ellipsoid, a flat Mercator map, and the rhumb line. Educational accuracy, not survey accuracy: a spherical Earth is accurate to roughly 0.3% for distances.

**Not in scope.** User accounts, databases, real flight routing or winds, fuel/CO₂ estimates, place search, containers or cloud hosting.

**Documents.** `README.md` (run it), `docs/ARCHITECTURE.md` (design, for AI collaborators), `docs/METRICS.md` (what is calculated), `docs/MATH.md` (the formulas), `CLAUDE.md` (working rules for Claude Code).
