# METRICS — everything the app can calculate

Every metric is computed by the Python backend and returned by `POST /api/calculate` together with a step-by-step `explanation`. Clicking a metric card in the UI opens that explanation. Formulas live in [MATH.md](MATH.md); the API shape is in [ARCHITECTURE.md](ARCHITECTURE.md).

There are 25 metrics, plus 2 optional ones that only appear when their option is set (`destination` and `return_trip`, marked *optional* below). They appear in this order (the panel order); note that the two course metrics are listed in the Travel group, right after the flight time. A metric's `value`/`display` can be `null`/a short reason in edge cases.

## Geometry
| id | What it tells you | Inputs | Edge cases |
|---|---|---|---|
| `distance_haversine` | Shortest distance over the surface (km, nm, mi); cross-checked with the law of cosines | A, B | A = B → 0; antipodal → πR |
| `distance_analysis` | **The same two points, ten ways of measuring**, each tagged `ellipsoid` or `sphere` and compared with the Vincenty reference: straight tunnel (ellipsoid), great circle on the polar / mean / equatorial sphere, Vincenty, Lambert, rhumb line, programmer's shortcut, degrees as a flat grid, Mercator ruler. The great circle on the mean sphere carries a *conventional* badge and its error margin; sphere-based methods also show their difference to the great circle on the same sphere; a summary separates the effect of the Earth model from the effect of the method. The card opens a *Distance analysis* pop-up with a bar per row; each row opens its calculation | A, B | A = B → `null`; Vincenty has no result near the antipode → Lambert is the reference (warning); exactly antipodal → the sphere; a measure that is undefined for the pair shows the reason |
| `ellipsoid_vincenty` | **The reference distance on the WGS84 ellipsoid** (Vincenty's iterative inverse formula, accurate to ~0.1 mm): every round of the iteration with λ, the series coefficients and the final distance | A, B | A = B → `null`; does not converge for nearly antipodal points (card says "no convergence", warning, Lambert becomes the reference); antipodal → `null` |
| `ellipsoid_lambert` | Lambert's formula, an **approximation** of the ellipsoid distance, with its difference to the sphere and to Vincenty (about −13 m on Cologne → Santiago); warns when the points are more than 170° apart (error grows from ~0.6 km to tens of km near the antipode) | A, B | A = B, antipodal → `null`; almost antipodal → accuracy warning |
| `mercator_distortion` | Straight-line distance on a flat Mercator map vs reality, plus the local scale factor at A and B | A, B | \|lat\| > 85.0511° → `null` |
| `midpoint` | Point halfway along the great circle | A, B | antipodal → `null` |
| `vertex_latitude` | Highest-latitude point of the route, its hemisphere, endpoint vs vertex | A, B | A = B |
| `crossings` | Where the route crosses the equator, both tropics, both polar circles and the 0° and 180° meridians: coordinates, distance from A, share of the route, course there, time after take-off; lists what is not crossed. Also drawn on the globe (toggle "Crossings") | A, B | A = B, antipodal → `null`; route along the equator/a meridian → "runs along"; at a pole the course is undefined |
| `rhumb_line` | Constant-bearing path: distance, bearing, extra distance vs great circle | A, B | pole → `null` |
| `rhumb_vs_great_circle` | What a constant bearing costs: extra distance (km, %), extra flying time at the cruise speed, the rhumb bearing next to the great-circle courses, and how far apart the two paths get (largest distance from the great circle to the rhumb line, with its position) | A, B, `cruise_kmh` | identical points, pole → `null`; 0 along the equator or a meridian |
| `antipodes` | The point on the exact opposite side of the Earth, for A and B | A, B | none |
| `earth_scale` | The route in proportion to the Earth: central angle, share of the circumference, how many such routes fit around the Earth, time to circle it at cruise speed, light laps per second | A, B, `cruise_kmh` | A = B → 0 % |
| `destination` *(optional)* | Where you end up from A after a distance on a true bearing (the direct problem), with a check by haversine; drawn on the globe. Always present in the *Start + course* input mode, where it is B | A, `project_bearing_deg`, `project_km` (both needed), or `course` in the request | distance > πR passes the antipode; at a pole the bearing is degenerate |

## Through the Earth
| id | What it tells you | Inputs | Edge cases |
|---|---|---|---|
| `chord_and_bulge` | Straight tunnel length and how far the surface bulges above it | A, B | none |
| `gravity_train` | Frictionless fall time (~42.2 min, independent of distance) and top speed | A, B | none |

## Travel
| id | What it tells you | Inputs | Edge cases |
|---|---|---|---|
| `flight_time` | **Airborne time** (take-off to landing, no taxiing) = distance / cruise speed + climb/descent allowance; also shows gate-to-gate time (adds taxiing) | A, B, `cruise_kmh`, `climb_descent_min`, `taxi_min` | ignores wind, airways, runways and procedures |
| `bearing_initial` | **Course after take-off**: azimuth (0° = true north) of the route at A, with 16-wind compass point, in radians and as an hour angle (15° = 1 h; a unit conversion, not a travel time) | A, B | A = B, antipodal, pole → `null` |
| `bearing_final` | **Course before landing**: azimuth of the route immediately before reaching B, how much the course changes over the route, also in radians and as an hour angle | A, B | same as above |
| `return_trip` *(optional)* | The same route flown from B to A: take-off course at B, landing course at A, and the (identical, no-wind) flight time | A, B, `include_return` | same as the courses |
| `latency` | Light-in-vacuum and light-in-fiber one-way time, minimum round-trip ping | A, B | none |
| `travel_times` | Time at reference speeds (walking, car, train, airliner, Concorde, ISS, light) | A, B | none |
| `horizon_los` | How far the horizon is from A, B and cruise altitude; whether A and B could see each other | A, B, `height_a_m`, `height_b_m` | ignores terrain and refraction |

## Sun & time
| id | What it tells you | Inputs | Edge cases |
|---|---|---|---|
| `solar_offset` | Sun-time difference between A and B (15° of longitude = 1 h) | A, B | none |
| `timezone_diff` | Civil UTC offsets at A and B on the chosen date (incl. daylight saving) and their difference; states that rules are today's (tz database release shown) | A, B, `date` (1970-01-01 … 2049-12-31) | overlapping polygons → the most specific zone; within 15 km of a polygon → the nearest zone (noted); open ocean → nominal zone round(λ/15); future political changes unknown, later dates assume today's rules |
| `sun_a` | Sunrise, sunset, day length at A (UTC clock times, marked when they fall on the previous/next UTC date), for the chosen date; the Sun's position is calculated step by step (mean longitude, anomaly, obliquity, declination, equation of time). Within about 1 min of an astronomical program up to ~50° latitude | A, `date` | polar day / polar night, pole; days longer than 21 h (near the midnight sun) → up to about 10 min of error, hint on the card |
| `sun_b` | Same for B | B, `date` | same |
| `moon_phase` | Phase of the Moon on the chosen date: name, lit percentage, age in days, next full and new moon (from the Moon's and the Sun's positions; lit fraction within 0.3 percentage points, new/full moon within 0.5 h; the same everywhere on Earth) | `date` | none |

## Options (all optional)
`cruise_kmh` (default 850), `climb_descent_min` (default 15), `taxi_min` (default 15), `date` (default today, ISO `YYYY-MM-DD`, limited to 1970-01-01 … 2049-12-31; used by the sun and time-zone metrics and by the night shading), `height_a_m` and `height_b_m` (default 1.7), `project_bearing_deg` (0–360) with `project_km` (≥ 0) for the `destination` metric, `include_return` (default false) for the `return_trip` metric, `circle_km` (0 … πR ≈ 20 015 km; default: the route length) for the circles of equal distance, `units` (`km` default, `nm`, `mi`) for how distances and speeds are written on the cards (values and calculations stay in km).

## Non-metric outputs
Great-circle path and rhumb path (128 samples, antimeridian-unwrapped), markers for midpoint, vertex, the two antipodes and the route crossings (labelled), the projection path and destination point (when requested), the circles of equal distance around A and B (cut at the date line), and the day/night shading with the sub-solar point (`GET /api/terminator`, for a UTC date and time, independent of A and B; the Night picker on the map takes the computer's local time or UTC and converts it to UTC), and an optional airports layer. The airport/city search (`GET /api/places`), the airports layer (`GET /api/airports`), the nearest-place hints (`GET /api/nearest`) and the unit table (`GET /api/units`) are helpers, not metrics. These are drawn on the map, not shown as cards; the layer toggles are in the toolbar on top of the map.

## Out of scope
Fuel and CO₂ estimates, real airways, wind, geocoding/place search, anything needing an external service.
