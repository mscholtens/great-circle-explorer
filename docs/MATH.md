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
| `AXIAL_TILT_DEG` | 23.44 | Axial tilt ε used for the tropics (±ε) and the polar circles (±(90° − ε)); the Sun's declination uses the obliquity formula above instead |
| `TROPIC_LAT_DEG` / `POLAR_CIRCLE_LAT_DEG` | 23.44 / 66.56 | Latitudes of the tropics and polar circles (derived from ε) |
| `DATE_MIN` / `DATE_MAX` | 1970-01-01 / 2049-12-31 | Dates accepted for the sun and time-zone metrics |
| `EARTH_ROTATION_DEG_PER_H` | 15 | The Earth turns 360° in 24 h: used for hour angles (angle ↔ time) |
| `PROJECTION_SAMPLES` / `CIRCLE_SAMPLES` / `TERMINATOR_SAMPLES` | 64 / 180 / 180 | Points per drawn curve (projection path, circle of equal distance, day/night boundary) |
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

## ellipsoid_vincenty — the reference distance on the WGS84 ellipsoid
Vincenty's inverse formula (1975), `geo/ellipsoid.py`. With a = 6378.137 km, f = 1/298.257223563, b = a(1 − f) = 6356.752 km:
```
U = atan((1−f) tan φ)   for both points,   L = λ₂ − λ₁,   λ = L
repeat:
    sin σ = √[ (cos U₂ sin λ)² + (cos U₁ sin U₂ − sin U₁ cos U₂ cos λ)² ]
    cos σ = sin U₁ sin U₂ + cos U₁ cos U₂ cos λ,        σ = atan2(sin σ, cos σ)
    sin α = cos U₁ cos U₂ sin λ / sin σ,                cos²α = 1 − sin²α
    cos 2σm = cos σ − 2 sin U₁ sin U₂ / cos²α           (0 along the equator, cos²α = 0)
    C = f/16 · cos²α · (4 + f (4 − 3 cos²α))
    λ = L + (1−C) f sin α · (σ + C sin σ (cos 2σm + C cos σ (−1 + 2 cos² 2σm)))
until |λ_new − λ| < 10⁻¹² (at most 200 rounds)

u² = cos²α (a² − b²) / b²
A  = 1 + u²/16384 · (4096 + u²(−768 + u²(320 − 175 u²)))
B  = u²/1024 · (256 + u²(−128 + u²(74 − 47 u²)))
Δσ = B sin σ (cos 2σm + B/4 (cos σ(−1 + 2cos² 2σm) − B/6 cos 2σm (−3 + 4 sin² σ)(−3 + 4 cos² 2σm)))
s  = b · A · (σ − Δσ)
```
The card lists every round (λ before and after, the change), the series coefficients, Δσ and the final distance. Identical points give 0. **No convergence** (nearly antipodal points) or antipodal points give no result: the card says so, `warnings` gets "Vincenty's formula does not converge for nearly antipodal points; Lambert is used as the reference, and its accuracy is reduced here as well", and the distance analysis uses Lambert as its reference. The iteration has deliberately **no** "stop as soon as |λ| > π" shortcut: many implementations include one, but it rejects pairs that do converge (Quito → Singapore passes λ > π on the way and converges in 11 rounds). Measured against GeographicLib (Karney's algorithm, the more robust method), Vincenty agrees to 0.1 mm wherever it converges; of 30 000 pairs biased towards the antipode only 19 (all more than 175° apart) did not converge, and the slowest needed 141 rounds.

## ellipsoid_lambert — ellipsoid comparison (approximation)
Lambert's formula for long lines on the WGS84 ellipsoid (a, f):
```
β = atan((1−f) · tan φ)                 # reduced latitude, for both points
σ = central angle between (β₁, λ₁) and (β₂, λ₂)     # haversine on the reduced latitudes
P = (β₁ + β₂)/2,   Q = (β₂ − β₁)/2
X = (σ − sin σ) · sin²P · cos²Q / cos²(σ/2)
Y = (σ + sin σ) · cos²P · sin²Q / sin²(σ/2)
d = a · (σ − (f/2)·(X + Y))
```
Shown next to the spherical distance with the absolute (km) and relative (%) difference, and next to Vincenty's result (about −13 m on Cologne → Santiago). Undefined for σ = 0 (identical points) and σ = π (antipodal) → `null`. **Accuracy:** typically about 10 m against the exact geodesic (99 % of random pairs within 80 m), but the formula loses accuracy as the points approach the antipode (the denominators `cos²(σ/2)` and `sin²(σ/2)` and the reduced-latitude shortcut stop working): about 0.6 km at σ = 170°, 1.2 km at 174°, 2.5 km at 177°, tens of km within 2° of the antipode (`constants.LAMBERT_ERROR_TIERS`). The card and the pop-up warn beyond 170°.

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

## return_trip — the same route flown from B to A (optional metric)
Shown only when `include_return` is set. Because the course changes along a great circle, the return courses are not the outbound ones turned by 180° at the same ends:
```
take-off course at B   θ_BA,initial = initial bearing from B to A            = (θ_AB,final   + 180°) mod 360°
landing course at A    θ_BA,final   = final bearing from B to A              = (θ_AB,initial + 180°) mod 360°
t_BA = t_AB                                                                    (same distance, same speed, no wind)
```
The card checks both identities numerically (differences ≈ 10⁻¹³°). With real winds the two directions differ; that is not modelled.

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

**Radians and hour angle.** Each course card has two extra steps that only change the unit of the same angle: `θ_rad = θ° · π/180` and the hour angle `t = θ° / (15°/h)` (the Earth turns 15° per hour, the same conversion as for longitude and solar time), shown as `h min s`. The hour angle is not a travel time. Example: 239.4° = 4.178 rad = 15.96 h = 15 h 57 min 37 s.

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

## rhumb_vs_great_circle — what a constant bearing costs
Uses the rhumb results above and the great-circle distance:
```
Δd = d_rhumb − d_gc          Δd% = 100 · Δd / d_gc
Δt = Δd / v                  (v = cruise speed; no climb/descent or taxi allowance)
Δθ_start = θ_rhumb − θ_initial,   Δθ_end = θ_rhumb − θ_final      (each wrapped to −180°…180°)
```
**How far apart are the two paths?** The largest distance from a point of the great circle to the nearest point of the rhumb line, `s_max = R · max_i min_j ∠(G_i, R_j)`, with 48 points `G_i` of the great circle and 720 points `R_j` of the rhumb line as unit vectors (`spherical.max_separation`, angle = atan2(|G × R|, G · R)). The error is about half the spacing of the rhumb points (under 10 km). Amsterdam → Buenos Aires: up to about 450 km, near 27.1°N 22.0°W, although the lengths differ by only 0.4 %. (Not to be confused with the difference in latitude at the same longitude, which is larger, about 670 km at 32°W.)

`Δd ≥ 0` always (clamped at 0 for floating-point noise); it is 0 along the equator and along a meridian. Undefined (`null`) when the rhumb line is (identical points, a pole). If the great-circle courses are undefined (antipodal points), only the rhumb bearing is shown.

## distance_analysis — the same two points, ten ways of measuring
The answer depends on two things: the **method** (a path over a surface, on a flat map, or through the Earth) and the **model of the Earth** (a sphere of some radius, or the WGS84 ellipsoid). Each row is tagged `ellipsoid` or `sphere` and compared with a reference: Vincenty's distance (Lambert's when Vincenty has no result, the great circle on the mean sphere when neither exists, for antipodal points). Rows are sorted shortest first.
```
Straight tunnel (ellipsoid)      c = √(ΔX² + ΔY² + ΔZ²)    X = N cos φ cos λ, Y = N cos φ sin λ, Z = N (1−e²) sin φ
                                 e² = f(2−f), N = a / √(1 − e² sin²φ)
Great circle, polar radius       d = b δ                   b = a(1−f) = 6356.752 km
Ellipsoid, Vincenty (reference)  s = b A (σ − Δσ)          see ellipsoid_vincenty
Ellipsoid, Lambert               d = a (σ − f/2 (X + Y))   see ellipsoid_lambert
Great circle, mean radius        d = R δ                   R = 6371.0088 km = (2a + b)/3 (IUGG): the conventional method
Great circle, equatorial radius  d = a δ                   a = 6378.137 km
Rhumb line                       d = R √(Δφ² + q² Δλ²)     (rhumb_line)
Programmer's shortcut            d = R √(Δφ² + (Δλ cos φm)²)    φm = (φ₁ + φ₂)/2, Δλ wrapped to [−π, π]
Degrees as a flat grid           d = k √(Δφ² + Δλ²)        k = πR/180 = 111.195 km per degree, Δλ the shorter way around
Ruler on a flat Mercator map     d = R √(Δλ² + Δψ²)        (mercator_distortion)
```
The three great-circle rows use the **same** central angle δ (haversine); only the radius differs, so the Earth model alone moves the answer by about 0.3 %. The "programmer's shortcut" (equirectangular approximation) is common in games and fast code: fine for short distances, increasingly wrong for long ones; it differs from the flat grid because it scales longitude by cos φm. The "degrees as a flat grid" distance reads latitude and longitude as graph-paper coordinates: a degree of longitude is really only 111.195·cos φ km, so east-west distances are overstated away from the equator; it is exact along the equator and along a meridian and can be too long or too short elsewhere. The straight tunnel is computed in Earth-centred (ECEF) coordinates on the ellipsoid; the spherical chord 2R sin(δ/2) stays in the "Straight tunnel & bulge" card and the row's calculation compares the two.

Each row shows its difference to the reference (km, %). The four sphere-based *methods* (rhumb line, programmer's shortcut, flat grid, Mercator ruler) also show their difference to the great circle **on the same mean sphere**, because their difference to the reference includes the sphere's own model error (about +20 km on Cologne → Santiago). Under the table: *same method, different Earth model* (spread of the three great-circle rows) and *same Earth model, different method* (spread of the rows on the mean sphere). Cologne → Santiago: tunnel 10 320, polar 12 034, **Vincenty 12 041**, Lambert 12 041 (−13 m), **great circle 12 061 (+0.17 %, conventional)**, equatorial 12 074, rhumb 12 132, shortcut 12 694, grid 12 762, Mercator 13 640 km. Amsterdam → Buenos Aires: Vincenty 11 437.2 km. A row whose measure is undefined for the pair (Mercator above 85.05°, rhumb at a pole, Vincenty near the antipode) shows the reason instead of a distance. Each row opens its calculation.

## antipodes
`φa = −φ`, `λa = λ ± 180°` (normalized to [−180°, 180°]). Computed for both A and B.

## earth_scale — the route in proportion to the Earth
```
δ = d / R                              central angle (angle at the Earth's centre)
C = 2πR                                circumference of a great circle
share = d / C = δ / (2π)               (maximum 50 %, at the antipode)
n = C / d                              how many such routes fit around the Earth (omitted for d = 0)
t_lap = C / v                          time to circle the Earth at the cruise speed
laps_per_s = c / C                     light around the Earth, laps per second (≈ 7.49)
```

## destination — the direct problem (optional metric)
Shown only when both `project_bearing_deg` and `project_km` are given, and always in the *Start + course* input mode (the request's `course` replaces them, and B is this destination). Starting at A, travel the distance `d` on the true bearing `θ` along the great circle that starts in that direction (the inverse of the distance and bearing metrics):
```
σ  = d / R
φ₂ = asin( sin φ₁ · cos σ + cos φ₁ · sin σ · cos θ )
λ₂ = λ₁ + atan2( sin θ · sin σ · cos φ₁ , cos σ − sin φ₁ · sin φ₂ )         (normalized to [−180°, 180°])
check: haversine(A, destination) = R · min(σ mod 2π, 2π − (σ mod 2π))
```
For `d > πR` the path passes the antipode of A and comes back, so the destination is nearer than `d`. At a pole every direction is south or north; the bearing is then measured from the stored meridian. The path drawn on the globe is the same formula for σ·i/64, i = 0…64, with unwrapped longitudes. The function is `spherical.destination`, also used for the vertex and for the circles below.

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

**Which polygon wins.** A few zone polygons overlap (Xinjiang lies in both `Asia/Shanghai` and `Asia/Urumqi`; neighbouring zones overlap by the simplification tolerance along borders): the polygon with the smallest area, the most specific one, is chosen (`timezones.find_zone`). A point that lies in no polygon but within 15 km of one (a coast, or a gap left by the simplified borders) gets the nearest zone, and the card notes how far outside it is. Only further out (open ocean) the nominal zone `round(λ_deg / 15)` hours is used, with a note. When the bundled data is rebuilt, small rings (enclaves such as Melilla) are simplified less coarsely than large ones so that they survive. Against an exact-polygon library the bundled data agrees on 99.9 % of 4 748 airports and cities (100 % in UTC offset), see [ACCURACY.md](ACCURACY.md). Civil time zones differ from solar time (compare with `solar_offset`).

## sun_a / sun_b — sunrise, sunset, day length
**Where the Sun is.** Low-precision formulas of the kind published in the Astronomical Almanac, valid for roughly 1950–2050 (`geo/sun.py`, `sun_position`). With the Julian date JD of the *local solar noon* of the chosen date (`JD₁₂ = date.toordinal() + 1721425` is 12:00 UTC; local noon is `JD₁₂ − λ/360° − EoT₀/1440`, with EoT₀ the equation of time of a first pass, so the longitude does not change which day is meant) and `n = JD − 2451545.0`:
```
L    = 280.460° + 0.9856474° · n                     mean longitude of the Sun          (mod 360°)
g    = 357.528° + 0.9856003° · n                     mean anomaly                        (mod 360°)
λ☉   = L + 1.915° sin g + 0.020° sin 2g              ecliptic longitude (equation of centre)
ε    = 23.439° − 0.0000004° · n                      obliquity of the ecliptic
α    = atan2(cos ε sin λ☉, cos λ☉)                   right ascension
δ    = asin(sin ε sin λ☉)                            declination
EoT  = 4 min/° · (L − 0.0057183° − α)                equation of time (angle wrapped to ±180°)
```
Compared with PyEphem over 1970–2049: declination within 0.005°, equation of time within 0.07 min (see [ACCURACY.md](ACCURACY.md)).

**Sunrise and sunset** (φ = latitude, λ = longitude, h₀ = −0.833°, the standard refraction plus the radius of the solar disc):
```
cos ω₀ = (sin h₀ − sin φ · sin δ) / (cos φ · cos δ)
```
- cos ω₀ < −1 → polar day (24 h of daylight); cos ω₀ > 1 → polar night (0 h). At exactly φ = ±90° (cos φ = 0) the formula is not used; the case is handled explicitly from the sign of δ.
- `day_length_h = 2 · deg(ω₀) / 15`
- `solar_noon_utc_h = 12 − λ_deg/15 − EoT/60`
- `sunrise_utc = solar_noon − deg(ω₀)/15`, `sunset_utc = solar_noon + deg(ω₀)/15` (wrapped into 0–24 h; an event can fall on the previous or next UTC date, which the card marks)

Results are UTC clock times. Typical difference to an astronomical program, by length of the day: about 1 minute up to 8 h of daylight (all winter days, also far north), 2 minutes up to 16 h, under 5 minutes up to 21 h, and up to about 10 minutes (rarely 15) for days longer than 21 h, near the midnight sun, where the day length changes by many minutes per day (the card adds a hint then). Refraction is fixed (real refraction depends on weather); observer height and terrain are ignored. The date → Julian date conversion happens outside `geo/` (in `metrics.py`).

## moon_phase — phase of the Moon
`geo/moon.py`. With `T = (JD − 2451545.0) / 36525` (JD of 12:00 UTC on the chosen day), the Moon's ecliptic longitude and latitude come from a short series of sine terms (a low-precision formula of the kind published in the Astronomical Almanac, about 0.3° accuracy):
```
λM = 218.32° + 481267.881° T + 6.29° sin(135.0° + 477198.87° T) − 1.27° sin(259.3° − 413335.36° T) + 0.66° sin(235.7° + 890534.22° T)
     + 0.21° sin(269.9° + 954397.74° T) − 0.19° sin(357.5° + 35999.05° T) − 0.11° sin(186.5° + 966404.03° T)
βM = 5.13° sin(93.3° + 483202.02° T) + 0.28° sin(228.2° + 960400.89° T) − 0.28° sin(318.3° + 6003.15° T) − 0.17° sin(217.6° − 407332.21° T)
```
The Sun's longitude λ☉ comes from the formulas above. Then:
```
cos ψ = cos βM · cos(λM − λ☉)            elongation ψ (0 = new moon, 180° = full moon)
lit   = (1 − cos ψ) / 2                  lit fraction of the disc
D     = (λM − λ☉) mod 360°               0 new, 90 first quarter, 180 full, 270 last quarter
name  = one of 8, index = ⌊(D + 22.5°) / 45°⌋ mod 8
t ← t + (D_target − D(t)) / 12.19°/day   repeated 8 times, from the mean motion, to find the next new (0°) / full (180°) moon
                                         and the previous new moon (age = JD − that time)
```
Compared with PyEphem (1970–2049): lit fraction within 0.3 percentage points, times of new and full moon within 0.5 hour. The percentage ignores the small effect of the Moon's distance; eclipses and libration are not modelled. It is the same for everyone on Earth, so it does not depend on A or B.

## Units (cards only)
`km_per_unit` is 1 (km, km/h), 1.852 (nm, kn) or 1.609344 (mi, mph). A card in another unit shows `x / km_per_unit`; every calculation and every step stays in km, with a final step "Convert to {unit} for the card" (`x_unit = x_km / k`) in the affected explanations.

## Nearest airport / city
Linear scan over the bundled places with the haversine distance of `distance_haversine` (`places.nearest`); no new formula.

## Map overlays (not metrics)
These come from the same formulas and are only drawn on the globe.

**Circles of equal distance** (`circles` in the response, toggle "Equal-distance circles"). All points at distance `r` from a centre (A and B) are `destination(centre, θ_i, r/R)` for θ_i = 2πi/180, i = 0…180. The default radius is the route length, so the circle around A passes through B and vice versa; `circle_km` overrides it (0 … πR). The curve is cut into polylines where the longitude jumps across ±180°: the latitude at the edge is interpolated linearly and added to both pieces so they meet exactly at the edge of the map (`spherical.split_antimeridian`). A radius of 0 gives no circle.

**Day/night boundary** (`GET /api/terminator`, toggle "Night"; `overlays.py`, `geo/sun.py`). For a UTC date and time, whose Julian date `JD = date.toordinal() + 1721425 + (t_UTC − 12 h)/24` goes into the same Sun formulas (`sun_position`):
```
δ and EoT from `sun_position(JD)`                                  # the same Sun as in the sunrise calculation
sub-solar point: latitude = δ,   longitude λs = −15° · (t_UTC − 12 h) − EoT/4       (4 min of EoT = 1°)
```
The Sun's altitude h at (φ, λ) satisfies `sin h = sin φ sin decl + cos φ cos decl cos H` with the hour angle `H = λ − λs`. On the boundary h = 0, so
```
tan φ = − cos H / tan decl            computed as  φ = atan2( −cos H · cos decl · sgn(decl), |sin decl| )
```
(at an equinox, decl = 0, the boundary is the pair of meridians 90° from the Sun, which the atan2 form handles without a division by zero). Sampling λ from −180° to 180° in 2° steps gives the curve; the night polygon closes it along the pole that is in darkness (the south pole when decl ≥ 0, else the north pole), stopped at ±89.9° because Web-Mercator tiles end near 85°. The boundary is the geometric terminator (h = 0°), not the −0.833° of sunrise and sunset, and twilight is not shown. Accuracy follows the Sun formulas (declination within 0.005°, so the boundary is within about 1 km of the true terminator for the geometric horizon). The shading is flat at the poles: it stops at ±89.9°.

**Projection path.** See `destination`.
