# METRICS — everything the app can calculate

Every metric is computed by the Python backend and returned by `POST /api/calculate` together with a step-by-step `explanation`. Clicking a metric card in the UI opens that explanation. Formulas live in [MATH.md](MATH.md); the API shape is in [ARCHITECTURE.md](ARCHITECTURE.md).

There are 20 metrics. They appear in this order (the panel order); note that the two course metrics are listed in the Travel group, right after the flight time. A metric's `value`/`display` can be `null`/a short reason in edge cases.

## Geometry
| id | What it tells you | Inputs | Edge cases |
|---|---|---|---|
| `distance_haversine` | Shortest distance over the surface (km, nm, mi); cross-checked with the law of cosines | A, B | A = B → 0; antipodal → πR |
| `ellipsoid_lambert` | Same distance on the WGS84 ellipsoid (Lambert's formula) and the difference vs the sphere | A, B | A = B, antipodal → `null` |
| `mercator_distortion` | Straight-line distance on a flat Mercator map vs reality, plus the local scale factor at A and B | A, B | \|lat\| > 85.0511° → `null` |
| `midpoint` | Point halfway along the great circle | A, B | antipodal → `null` |
| `vertex_latitude` | Highest-latitude point of the route, its hemisphere, endpoint vs vertex | A, B | A = B |
| `crossings` | Where the route crosses the equator, both tropics, both polar circles and the 0° and 180° meridians: coordinates, distance from A, share of the route, course there, time after take-off; lists what is not crossed. Also drawn on the globe (toggle "Crossings") | A, B | A = B, antipodal → `null`; route along the equator/a meridian → "runs along"; at a pole the course is undefined |
| `rhumb_line` | Constant-bearing path: distance, bearing, extra distance vs great circle | A, B | pole → `null` |
| `antipodes` | The point on the exact opposite side of the Earth, for A and B | A, B | none |

## Through the Earth
| id | What it tells you | Inputs | Edge cases |
|---|---|---|---|
| `chord_and_bulge` | Straight tunnel length and how far the surface bulges above it | A, B | none |
| `gravity_train` | Frictionless fall time (~42.2 min, independent of distance) and top speed | A, B | none |

## Travel
| id | What it tells you | Inputs | Edge cases |
|---|---|---|---|
| `flight_time` | **Airborne time** (take-off to landing, no taxiing) = distance / cruise speed + climb/descent allowance; also shows gate-to-gate time (adds taxiing) | A, B, `cruise_kmh`, `climb_descent_min`, `taxi_min` | ignores wind, airways, runways and procedures |
| `bearing_initial` | **Course after take-off**: azimuth (0° = true north) of the route at A, with 16-wind compass point | A, B | A = B, antipodal, pole → `null` |
| `bearing_final` | **Course before landing**: azimuth of the route immediately before reaching B, and how much the course changes over the route | A, B | same as above |
| `latency` | Light-in-vacuum and light-in-fiber one-way time, minimum round-trip ping | A, B | none |
| `travel_times` | Time at reference speeds (walking, car, train, airliner, Concorde, ISS, light) | A, B | none |
| `horizon_los` | How far the horizon is from A, B and cruise altitude; whether A and B could see each other | A, B, `height_a_m`, `height_b_m` | ignores terrain and refraction |

## Sun & time
| id | What it tells you | Inputs | Edge cases |
|---|---|---|---|
| `solar_offset` | Sun-time difference between A and B (15° of longitude = 1 h) | A, B | none |
| `timezone_diff` | Civil UTC offsets at A and B on the chosen date (incl. daylight saving) and their difference; states that rules are today's (tz database release shown) | A, B, `date` (1970-01-01 … 2049-12-31) | open ocean → nominal zone round(λ/15); future political changes unknown, later dates assume today's rules |
| `sun_a` | Sunrise, sunset, day length at A (UTC), for the chosen date | A, `date` | polar day / polar night, pole |
| `sun_b` | Same for B | B, `date` | same |

## Options (all optional)
`cruise_kmh` (default 850), `climb_descent_min` (default 15), `taxi_min` (default 15), `date` (default today, ISO `YYYY-MM-DD`, limited to 1970-01-01 … 2049-12-31; used by the sun and time-zone metrics), `height_a_m` and `height_b_m` (default 1.7).

## Non-metric outputs
Great-circle path and rhumb path (128 samples, antimeridian-unwrapped), and markers for midpoint, vertex, the two antipodes and the route crossings (labelled). These are drawn on the map, not shown as cards.

## Out of scope
Fuel and CO₂ estimates, real airways, wind, geocoding/place search, anything needing an external service.
