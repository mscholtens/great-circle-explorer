# MATH — formulas used per metric

All geodesy is hand-written with Python's `math` module on a **spherical Earth** (R = 6371.0088 km), except the ellipsoid comparison, which uses the WGS84 ellipsoid with Lambert's formula (still only sin/cos/atan/tan). Inside `geo/` all angles are radians; the API speaks degrees.

**Notation:** φ = latitude, λ = longitude, Δφ = φ₂ − φ₁, Δλ = λ₂ − λ₁, δ = central angle (rad), d = R·δ, θ = bearing, point A = (φ₁, λ₁), point B = (φ₂, λ₂).

Constants (all in `backend/app/constants.py`, each with a source comment):

| Name | Value | Meaning |
|---|---|---|
| `R_KM` | 6371.0088 | Mean Earth radius (IUGG), km |
| `G` | 9.80665 | Standard gravity, m/s² |
| `C_KM_S` | 299792.458 | Speed of light in vacuum, km/s |
| `FIBER_INDEX` | 1.468 | Typical refractive index of single-mode fiber |
| `KM_PER_NM` | 1.852 | Nautical mile |
| `KM_PER_MI` | 1.609344 | Statute mile |
| `CRUISE_KMH_DEFAULT` | 850 | Typical airliner cruise ground speed, no wind |
| `CLIMB_DESCENT_MIN_DEFAULT` | 15 | Extra airborne time for climb and descent, minutes (assumption, adjustable) |
| `TAXI_MIN_DEFAULT` | 15 | Taxiing at both airports together, minutes (assumption, adjustable; not flight time) |
| `SUN_ALTITUDE_DEG` | −0.833 | Sunrise/sunset altitude (refraction + solar disc radius) |
| `AXIAL_TILT_DEG` | 23.44 | Axial tilt ε (sun declination; tropics at ±ε, polar circles at ±(90° − ε)) |
| `TROPIC_LAT_DEG` / `POLAR_CIRCLE_LAT_DEG` | 23.44 / 66.56 | Latitudes of the tropics and polar circles (derived from ε) |
| `DATE_MIN` / `DATE_MAX` | 1970-01-01 / 2049-12-31 | Dates accepted for the sun and time-zone metrics |
| `WGS84_A_KM` | 6378.137 | WGS84 equatorial radius, km |
| `WGS84_F` | 1/298.257223563 | WGS84 flattening |
| `CRUISE_ALTITUDE_M` | 11000 | Typical airliner cruise altitude, m |
| `EYE_HEIGHT_M_DEFAULT` | 1.7 | Default observer eye height, m |

Reference speeds for `travel_times`: walking 5 km/h, car 100 km/h, high-speed train 300 km/h, airliner (cruise default), Concorde 2180 km/h, ISS 27 600 km/h (orbital speed at altitude, used as a fun comparison only), light in vacuum.

---

## distance_haversine — great-circle distance
```
a = sin²(Δφ/2) + cos φ₁ · cos φ₂ · sin²(Δλ/2)
δ = 2 · atan2(√a, √(1−a))
d = R · δ
```
Cross-check with the spherical law of cosines: `δ = acos(sin φ₁ sin φ₂ + cos φ₁ cos φ₂ cos Δλ)`. It is numerically worse for very small distances (acos near 1 loses precision), which is why haversine is primary. Shown in km, nm and mi.

## ellipsoid_lambert — ellipsoid comparison
Lambert's formula for long lines on the WGS84 ellipsoid (a, f):
```
β = atan((1−f) · tan φ)                 # reduced latitude, for both points
σ = central angle between (β₁, λ₁) and (β₂, λ₂)     # haversine on the reduced latitudes
P = (β₁ + β₂)/2,   Q = (β₂ − β₁)/2
X = (σ − sin σ) · sin²P · cos²Q / cos²(σ/2)
Y = (σ + sin σ) · cos²P · sin²Q / sin²(σ/2)
d = a · (σ − (f/2)·(X + Y))
```
Shown next to the spherical distance with the absolute (km) and relative (%) difference. Undefined for σ = 0 (identical points) and σ = π (antipodal) → `null`.

## mercator_distortion — distance on a flat Mercator map
Isometric ("stretched") latitude: `ψ(φ) = ln(tan(π/4 + φ/2))`. On a Web Mercator map, scaled to Earth radius:
```
x = R · λ,   y = R · ψ(φ)
Δλ is reduced to [−π, π] (shorter way around)
d_flat = √((R·Δλ)² + (R·Δψ)²)
ratio  = d_flat / d_great_circle
local scale factor at a point = sec φ = 1 / cos φ
```
The point of the metric: a ruler on a Mercator map overstates distances away from the equator. Only defined for |φ| ≤ 85.0511° (the Web Mercator limit); otherwise `null` with a note.

## bearing_initial / bearing_final — course after take-off and course before landing
Shown in the Travel group right after the flight time. `bearing_initial` is the **course after take-off** (azimuth of the great circle at A, 0° = true north, clockwise); `bearing_final` is the **course before landing** (azimuth of the route immediately before reaching B). Both are great-circle azimuths at the given coordinates: no information about runway positions, lengths or headings is assumed, and magnetic variation is not applied. The course changes continuously along a great circle; the card states the total change `Δθ = θ_final − θ_initial` (wrapped to −180°…180°, negative = turning left).
```
θ₁ = atan2( sin Δλ · cos φ₂ , cos φ₁ · sin φ₂ − sin φ₁ · cos φ₂ · cos Δλ )
θ  = (deg(θ₁) + 360) % 360
final bearing = (initial bearing from B to A + 180) % 360
```
Also the 16-wind compass point (N, NNE, NE, …). Bearings are `null` when A = B, when the points are antipodal, or when A or B is a pole (see edge cases in ARCHITECTURE.md).

## midpoint
```
Bx = cos φ₂ · cos Δλ
By = cos φ₂ · sin Δλ
φm = atan2( sin φ₁ + sin φ₂ , √((cos φ₁ + Bx)² + By²) )
λm = λ₁ + atan2( By , cos φ₁ + Bx )          # normalized to [−180°, 180°]
```

## Path sampling (not a metric; powers the drawn path)
For f ∈ [0, 1], about 128 samples:
```
A = sin((1−f)·δ) / sin δ        B = sin(f·δ) / sin δ
x = A cos φ₁ cos λ₁ + B cos φ₂ cos λ₂
y = A cos φ₁ sin λ₁ + B cos φ₂ sin λ₂
z = A sin φ₁ + B sin φ₂
φ = atan2(z, √(x² + y²)),   λ = atan2(y, x)
```
Longitudes are **unwrapped** (consecutive values kept continuous by adding/subtracting 360°) so MapLibre does not draw a line across the whole map. Interpolation is refused when sin δ < ~1e-6 (near-antipodal).

## vertex_latitude — northernmost/southernmost point (Clairaut's relation)
Latitude of the vertex of the full great circle: `φv = acos(|sin θ₁ · cos φ₁|)`.
- Northern vertex lies on the segment A→B iff the route heads north at A (cos θ₁ > 0) and south at B (cos θ_final < 0).
- Southern vertex (−φv) lies on the segment iff cos θ₁ < 0 and cos θ_final > 0.
- Otherwise the segment's extreme latitude is at an endpoint: max(|φ₁|, |φ₂|).

Reported as the highest absolute latitude, its hemisphere, and whether it is an endpoint or the vertex. Explains why Europe–US flights pass near Greenland.

## crossings — where the route crosses the equator, tropics, polar circles and the 0° / 180° meridians
Work with unit vectors so every route (also through a pole) is handled:
```
A  = (cos φ cos λ, cos φ sin λ, sin φ)        unit vector of the start point (B likewise)
n  = A × B / |A × B|                           normal of the plane of the route
e₂ = n × A                                     unit vector in that plane, perpendicular to A, towards B
P(σ) = A cos σ + e₂ sin σ                      the point σ radians from A along the route (σ = 0 at A, σ = δ at B)
```
**Circle of latitude φc** (equator 0°, tropics ±23.44°, polar circles ±66.56°): the height of P(σ) is `z(σ) = A_z cos σ + e₂z sin σ = C cos(σ − σ₀)` with `C = √(A_z² + e₂z²)` and `σ₀ = atan2(e₂z, A_z)`. Setting `z = sin φc` gives
```
σ = σ₀ ± acos( sin φc / C )          kept if 0 ≤ σ ≤ δ;  no solution if |sin φc| > C
```
`asin(C)` is the highest latitude of the whole great circle, so circles beyond it are never crossed. A route that lies on the equator (C = 0) is reported as "runs along", not as a crossing.

**Meridian λc** (0° and 180°): the route plane and the meridian plane `m = (−sin λc, cos λc, 0)` meet in the line `±(n × m)`. Choose the sign whose longitude is λc (the other sign is the opposite meridian), then `σ = atan2(P·e₂, P·A)` mod 2π, kept if `σ ≤ δ`. A route in the meridian's own plane is "runs along".

**Position and course at a crossing**: `lat = atan2(P_z, √(P_x² + P_y²))`, `lon = atan2(P_y, P_x)`. The direction of travel is `T = −A sin σ + e₂ cos σ`; the course is the angle of T from local north towards local east (undefined at a pole). Distance from A is `R·σ`, the share of the route `σ/δ`, and the time after take-off is that share times the airborne time. Crossings are listed in travel order; lines that are not crossed are named, with the reason.

Accuracy: sphere model (positions can shift by a few km on the real ellipsoid). The tropics and polar circles use ε = 23.44°; the real tilt drifts by about half an arc-second per year.

## rhumb_line — constant-bearing path
```
Δψ = ln( tan(π/4 + φ₂/2) / tan(π/4 + φ₁/2) )
q  = Δφ / Δψ   if |Δψ| > 1e-12   else cos φ₁
if |Δλ| > π: Δλ = Δλ − sign(Δλ)·2π
d_rhumb = R · √(Δφ² + q² · Δλ²)
θ_rhumb = atan2(Δλ, Δψ)
```
Reported: rhumb distance, constant bearing, and the extra distance vs the great circle (km and %).
Path sampling: `φf = φ₁ + f·Δφ`, `λf = λ₁ + Δλ · (ψ(φf) − ψ(φ₁)) / Δψ` (if Δψ ≈ 0: `λf = λ₁ + f·Δλ`). Undefined when A or B is a pole (ψ → ∞) → `null` with a note.

## antipodes
`φa = −φ`, `λa = λ ± 180°` (normalized to [−180°, 180°]). Computed for both A and B.

## chord_and_bulge — straight tunnel through the Earth
```
chord   = 2R · sin(δ/2)
sagitta = R · (1 − cos(δ/2))          # how far the surface bulges above the straight line = max tunnel depth
```
Small-distance approximation `h ≈ d²/(8R)` is shown with its error vs the exact value.

## gravity_train — frictionless fall through the chord tunnel
Assumes **uniform density** and no friction. Motion along a chord is simple harmonic with ω = √(g/R) (R in metres):
```
T_trip = π · √(R/g)            # independent of distance! ≈ 42.2 min
v_max  = ω · chord/2           # at the deepest point
```

## flight_time — airborne time and gate-to-gate time
```
t_cruise     = d / v
t_airborne   = t_cruise + t_climb/descent      # take-off to landing, no taxiing (the headline value)
t_gate_gate  = t_airborne + t_taxi             # adds taxiing at both airports
```
`v`, `t_climb/descent` and `t_taxi` are adjustable (defaults 850 km/h, 15 min, 15 min; the two allowances are assumptions). The distance is point to point between the two coordinates: runway positions and lengths, departure/arrival procedures, holding patterns, airways and wind (jet stream) are not known and not modelled.

## latency — theoretical minimum ping
```
t_vacuum_one_way = d / c
t_fiber_one_way  = d / (c / n)
RTT_min          = 2 · t_fiber_one_way
```
In ms. Real routes are longer than the great circle and routers add delay, so real pings are typically 1.5–3× higher.

## travel_times — time at reference speeds
`t = d / v` for each reference speed (table).

## horizon_los — horizon and line of sight
For an observer at height h above a smooth sphere:
```
d_horizon (ground distance, exact)  = R · acos( R / (R + h) )
d_horizon (approx., h ≪ R)          = √(2·R·h)
d_los_max (two heights h_a, h_b)    = √(2·R·h_a) + √(2·R·h_b)
A and B can see each other (ignoring terrain, refraction) iff d ≤ d_los_max
```
Shown for the A and B heights (defaults 1.7 m) and for cruise altitude (11 000 m). Terrain, buildings and atmospheric refraction are ignored.

## solar_offset — solar time offset
`Δt_solar = Δλ_deg / 15` hours (each 15° of longitude = 1 hour of sun time). Δλ is normalized to [−180°, 180°].

## timezone_diff — civil time-zone difference
1. Find the IANA zone of each point with a hand-written ray-casting point-in-polygon test (`geo/pip.py`) over bundled, simplified timezone boundaries.
2. Get the UTC offset on the chosen date (12:00 UTC) with Python's `zoneinfo`, always using the bundled `tzdata` package (the system tz database is deliberately ignored, so results are reproducible; the release, e.g. `2026f`, is shown in the card). Daylight saving is included.
3. Difference = offset_B − offset_A.

**Date and its limits.** The chosen date (default today) must lie between 1 January 1970 and 31 December 2049 (HTTP 422 otherwise); it also drives the sun metrics. For past dates each zone's historical offsets and DST rules are used, but with *today's* zone borders. The rules and borders are today's: future political decisions (new zones, changes to daylight saving) cannot be predicted, so dates after today assume the current rules simply continue.

Points over open ocean (no polygon) fall back to the nominal zone `round(λ_deg / 15)` hours, with a note. Civil time zones differ from solar time (compare with `solar_offset`).

## sun_a / sun_b — sunrise, sunset, day length (approximation)
For day of year N (integer), latitude φ and longitude λ:
```
decl  = −23.44° · cos(360°/365 · (N + 10))
cos ω₀ = (sin h₀ − sin φ · sin decl) / (cos φ · cos decl)       # h₀ = −0.833°
```
- cos ω₀ < −1 → polar day (24 h of daylight); cos ω₀ > 1 → polar night (0 h). At exactly φ = ±90° (cos φ = 0) the formula is not used; the case is handled explicitly from the sign of decl.
- `day_length_h = 2 · deg(ω₀) / 15`
- Equation of time (minutes): `B = 360°/365 · (N − 81)`, `EoT = 9.87 sin 2B − 7.53 cos B − 1.5 sin B`
- `solar_noon_utc_h = 12 − λ_deg/15 − EoT/60`
- `sunrise_utc = solar_noon − deg(ω₀)/15`, `sunset_utc = solar_noon + deg(ω₀)/15` (wrapped into 0–24 h)

Results in UTC. Accuracy: ± a few minutes. Converting the chosen date into N happens outside `geo/` (in `metrics.py`).
