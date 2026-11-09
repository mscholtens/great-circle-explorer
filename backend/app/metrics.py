"""Assembles all metrics (value, display, step-by-step explanation) for a pair of points.

Every explanation step is built from the very same intermediate values the result was computed
from. Angles are radians inside the geo functions; this module converts at the boundary.
"""
import datetime as dt
import math

from . import constants as K
from . import timezones
from .explain import (const, explanation, hm, latlon_text, offset_text, sig, space_thousands, step,
                      td, tn, tp, utc_hm)
from .geo import crossings, ellipsoid, mercator, rhumb, spherical, sun, travel

deg = math.degrees
rad = math.radians

C_R = const("R", f"{K.R_KM} km", "mean Earth radius (IUGG)")
LABEL_COURSE_1 = "Course after take-off (initial bearing)"
LABEL_COURSE_2 = "Course before landing (final bearing)"

# Panel order of the metrics (the course cards sit in the Travel group, right after the flight time).
ORDER = ["distance_haversine", "ellipsoid_lambert", "mercator_distortion", "midpoint", "vertex_latitude",
         "crossings", "rhumb_line", "antipodes", "chord_and_bulge", "gravity_train", "flight_time",
         "bearing_initial", "bearing_final", "latency", "travel_times", "horizon_los", "solar_offset",
         "timezone_diff", "sun_a", "sun_b"]

# Lines whose crossing with the route is reported: (id, label, kind, value in degrees)
CROSSING_SPECS = [
    ("equator", "Equator", "lat", 0.0),
    ("tropic_cancer", "Tropic of Cancer", "lat", K.TROPIC_LAT_DEG),
    ("tropic_capricorn", "Tropic of Capricorn", "lat", -K.TROPIC_LAT_DEG),
    ("arctic_circle", "Arctic Circle", "lat", K.POLAR_CIRCLE_LAT_DEG),
    ("antarctic_circle", "Antarctic Circle", "lat", -K.POLAR_CIRCLE_LAT_DEG),
    ("prime_meridian", "Prime meridian (0°)", "lon", 0.0),
    ("antimeridian", "180° meridian (date line)", "lon", 180.0),
]


def _compass(theta):
    """16-wind compass point for a bearing in radians."""
    idx = int(((deg(theta) % 360.0) + 11.25) // 22.5) % 16
    return K.COMPASS_16[idx]


def _metric(mid, group, label, value, unit, display, secondary, expl, table=None):
    m = {"id": mid, "group": group, "label": label, "value": value, "unit": unit,
         "display": display, "secondary": secondary or [], "explanation": expl}
    if table is not None:
        m["table"] = table
    return m


def _undefined(mid, group, label, reason, why, notes=None):
    """A metric that cannot be computed: display = short reason, one explanatory step."""
    return _metric(mid, group, label, None, None, reason, [],
                   explanation(why, [step("Why this is undefined", None, None, why)], [], notes or []))


def calculate(a_lat, a_lon, b_lat, b_lon, cruise_kmh=None, climb_descent_min=None, taxi_min=None, day=None,
              height_a_m=None, height_b_m=None):
    """Compute everything for points A, B given in degrees. Returns the /api/calculate payload (dict)."""
    cruise_kmh = K.CRUISE_KMH_DEFAULT if cruise_kmh is None else cruise_kmh
    climb_descent_min = K.CLIMB_DESCENT_MIN_DEFAULT if climb_descent_min is None else climb_descent_min
    taxi_min = K.TAXI_MIN_DEFAULT if taxi_min is None else taxi_min
    day = day or dt.date.today()
    height_a_m = K.EYE_HEIGHT_M_DEFAULT if height_a_m is None else height_a_m
    height_b_m = K.EYE_HEIGHT_M_DEFAULT if height_b_m is None else height_b_m

    R = K.R_KM
    p1, l1, p2, l2 = rad(a_lat), rad(a_lon), rad(b_lat), rad(b_lon)
    dphi, dlam = p2 - p1, l2 - l1
    a_hav, delta = spherical.haversine(p1, l1, p2, l2)
    d_km = R * delta

    same = delta < K.EPS_SAME
    antipodal = abs(delta - math.pi) < K.EPS_ANTIPODAL
    near_antipodal = math.pi - delta < K.EPS_PATH_ANTIPODAL
    pole_a = abs(abs(p1) - math.pi / 2) < K.EPS_POLE
    pole_b = abs(abs(p2) - math.pi / 2) < K.EPS_POLE
    bearings_ok = not (same or antipodal or pole_a or pole_b)

    warnings = []
    if same:
        warnings.append("A and B are the same point: distance is 0 and bearings are undefined.")
    if antipodal:
        warnings.append("A and B are antipodal: infinitely many great circles connect them, so bearings, "
                        "midpoint and path are not unique. The distance is still πR.")
    elif near_antipodal and not same:
        warnings.append("A and B are almost antipodal: the great-circle path is numerically unstable and is not drawn.")
    if pole_a or pole_b:
        warnings.append("A pole is selected: bearings from a pole are degenerate (every direction is south or north), "
                        "and the rhumb line is undefined.")

    metrics = []

    # Flight times: airborne = take-off to landing (no taxiing); gate to gate adds the taxi allowance.
    cruise_h = d_km / cruise_kmh
    airborne_h = travel.flight_time_h(d_km, cruise_kmh, climb_descent_min)
    gate_h = airborne_h + taxi_min / 60.0

    # ------------------------------------------------------------------ distance_haversine
    cos_delta, delta_cos = spherical.law_of_cosines(p1, l1, p2, l2)
    nm = d_km / K.KM_PER_NM
    mi = d_km / K.KM_PER_MI
    steps = [
        step("Convert coordinates to radians",
             r"\varphi = \varphi^{\circ}\cdot\frac{\pi}{180},\qquad \lambda = \lambda^{\circ}\cdot\frac{\pi}{180}",
             rf"\begin{{aligned}}\varphi_1 &= {td(a_lat)}\cdot\tfrac{{\pi}}{{180}} = {tn(p1)}\\"
             rf"\lambda_1 &= {td(a_lon)}\cdot\tfrac{{\pi}}{{180}} = {tn(l1)}\\"
             rf"\varphi_2 &= {td(b_lat)}\cdot\tfrac{{\pi}}{{180}} = {tn(p2)}\\"
             rf"\lambda_2 &= {td(b_lon)}\cdot\tfrac{{\pi}}{{180}} = {tn(l2)}\end{{aligned}}",
             f"φ₁ = {sig(p1)} rad, λ₁ = {sig(l1)} rad, φ₂ = {sig(p2)} rad, λ₂ = {sig(l2)} rad"),
        step("Differences",
             r"\Delta\varphi = \varphi_2-\varphi_1,\qquad \Delta\lambda = \lambda_2-\lambda_1",
             rf"\Delta\varphi = {tn(p2)}-{tp(p1)} = {tn(dphi)},\qquad \Delta\lambda = {tn(l2)}-{tp(l1)} = {tn(dlam)}",
             f"Δφ = {sig(dphi)} rad, Δλ = {sig(dlam)} rad"),
        step("Haversine term",
             r"a = \sin^2\frac{\Delta\varphi}{2} + \cos\varphi_1\cos\varphi_2\sin^2\frac{\Delta\lambda}{2}",
             rf"a = \sin^2\frac{{{tn(dphi)}}}{{2}} + \cos({tn(p1)})\cos({tn(p2)})\sin^2\frac{{{tn(dlam)}}}{{2}}",
             sig(a_hav)),
        step("Central angle",
             r"\delta = 2\,\operatorname{atan2}\!\left(\sqrt{a},\ \sqrt{1-a}\right)",
             rf"\delta = 2\,\operatorname{{atan2}}\!\left(\sqrt{{{tn(a_hav)}}},\ \sqrt{{1-{tn(a_hav)}}}\right)",
             f"{sig(delta)} rad"),
        step("Distance along the surface", r"d = R\cdot\delta",
             rf"d = {tn(R)}\ \text{{km}}\cdot {tn(delta)}", f"{sig(d_km)} km"),
        step("Other units", r"1\ \text{nm}=1.852\ \text{km},\quad 1\ \text{mi}=1.609344\ \text{km}",
             rf"\frac{{{tn(d_km)}}}{{1.852}} = {tn(nm)}\ \text{{nm}},\qquad \frac{{{tn(d_km)}}}{{1.609344}} = {tn(mi)}\ \text{{mi}}",
             f"{sig(nm)} nm, {sig(mi)} mi"),
        step("Cross-check: spherical law of cosines",
             r"\delta = \arccos\!\left(\sin\varphi_1\sin\varphi_2+\cos\varphi_1\cos\varphi_2\cos\Delta\lambda\right)",
             rf"\delta = \arccos({tn(cos_delta)}) = {tn(delta_cos)}",
             f"{sig(delta_cos)} rad → {sig(R * delta_cos)} km (difference {sig(abs(R * delta_cos - d_km), 2)} km)"),
    ]
    notes = ["Spherical model; the real Earth is slightly flattened (about 0.3% difference at most) — see the ellipsoid metric.",
             "The law of cosines is numerically worse for very small distances (acos near 1 loses precision), "
             "which is why haversine is the primary method."]
    if antipodal:
        notes.append("Antipodal points: the distance is exactly half a great circle, πR.")
    metrics.append(_metric(
        "distance_haversine", "Geometry", "Great-circle distance", d_km, "km",
        f"{space_thousands(d_km)} km", [f"{space_thousands(nm)} nm", f"{space_thousands(mi)} mi"],
        explanation("Shortest path along the surface of a sphere, via the haversine formula.", steps, [C_R], notes)))

    # ------------------------------------------------------------------ ellipsoid_lambert
    lam = None if (same or antipodal) else ellipsoid.lambert_distance(p1, l1, p2, l2, K.WGS84_A_KM, K.WGS84_F)
    consts_wgs = [const("a", f"{K.WGS84_A_KM} km", "WGS84 equatorial radius"),
                  const("f", "1/298.257223563", "WGS84 flattening")]
    if lam is None:
        metrics.append(_undefined("ellipsoid_lambert", "Geometry", "Ellipsoid distance (WGS84)", "undefined",
                                  "Lambert's formula divides by sin²(σ/2) and cos²(σ/2), so it breaks down for identical "
                                  "and for antipodal points."))
    else:
        diff = lam["dist"] - d_km
        pct = diff / d_km * 100.0
        steps = [
            step("Reduced latitudes", r"\beta = \arctan\!\big((1-f)\tan\varphi\big)",
                 rf"\beta_1 = \arctan\big((1-{tn(K.WGS84_F)})\tan({tn(p1)})\big) = {tn(lam['beta1'])},\quad "
                 rf"\beta_2 = {tn(lam['beta2'])}",
                 f"β₁ = {sig(lam['beta1'])} rad, β₂ = {sig(lam['beta2'])} rad"),
            step("Central angle on the reduced sphere", r"\sigma = 2\operatorname{atan2}(\sqrt{a},\sqrt{1-a})\ \text{with } \beta\text{ in place of }\varphi",
                 None, f"σ = {sig(lam['sigma'])} rad"),
            step("P and Q", r"P = \frac{\beta_1+\beta_2}{2},\qquad Q = \frac{\beta_2-\beta_1}{2}",
                 rf"P = {tn(lam['P'])},\qquad Q = {tn(lam['Q'])}", f"P = {sig(lam['P'])}, Q = {sig(lam['Q'])}"),
            step("Correction terms",
                 r"X = \frac{(\sigma-\sin\sigma)\sin^2 P\cos^2 Q}{\cos^2(\sigma/2)},\qquad Y = \frac{(\sigma+\sin\sigma)\cos^2 P\sin^2 Q}{\sin^2(\sigma/2)}",
                 rf"X = {tn(lam['X'])},\qquad Y = {tn(lam['Y'])}", f"X = {sig(lam['X'])}, Y = {sig(lam['Y'])}"),
            step("Distance on the ellipsoid", r"d = a\left(\sigma - \frac{f}{2}(X+Y)\right)",
                 rf"d = {tn(K.WGS84_A_KM)}\left({tn(lam['sigma'])} - \frac{{{tn(K.WGS84_F)}}}{{2}}\,({tn(lam['X'])}+{tp(lam['Y'])})\right)",
                 f"{sig(lam['dist'])} km"),
            step("Difference to the spherical result", r"\Delta d = d_{\text{ellipsoid}} - d_{\text{sphere}}",
                 rf"\Delta d = {tn(lam['dist'])} - {tn(d_km)}", f"{sig(diff)} km ({sig(pct, 3)} %)"),
        ]
        metrics.append(_metric(
            "ellipsoid_lambert", "Geometry", "Ellipsoid distance (WGS84)", lam["dist"], "km",
            f"{space_thousands(lam['dist'])} km",
            [f"{diff:+,.1f} km vs sphere".replace(",", "\u00a0").replace("-", "−"), f"{pct:+.2f} %".replace("-", "−")],
            explanation("Lambert's formula gives the distance on the WGS84 ellipsoid using only sines and cosines.",
                        steps, consts_wgs + [C_R],
                        ["Lambert's formula is an approximation (errors of tens of metres on long lines), good enough for comparing with the sphere.",
                         "The sphere uses the mean radius, so the difference can be positive or negative depending on latitude and direction."])))

    # ------------------------------------------------------------------ mercator_distortion
    lim = rad(K.MERCATOR_MAX_LAT_DEG)
    if same:
        metrics.append(_undefined("mercator_distortion", "Geometry", "Distance on a flat Mercator map", "undefined",
                                  "For identical points both distances are 0, so their ratio is undefined."))
    elif abs(p1) > lim or abs(p2) > lim:
        metrics.append(_undefined("mercator_distortion", "Geometry", "Distance on a flat Mercator map", "off the map",
                                  f"Web Mercator only covers latitudes up to ±{K.MERCATOR_MAX_LAT_DEG}°; the poles stretch to infinity."))
    else:
        mm = mercator.flat_map_distance(p1, l1, p2, l2)
        flat_km = R * mm["dist"]
        ratio = flat_km / d_km
        sf1, sf2 = mercator.scale_factor(p1), mercator.scale_factor(p2)
        psi1, psi2 = rhumb.isometric_lat(p1), rhumb.isometric_lat(p2)
        steps = [
            step("Stretched latitude of each point", r"\psi(\varphi) = \ln\tan\!\left(\frac{\pi}{4}+\frac{\varphi}{2}\right)",
                 rf"\psi_1 = \ln\tan\!\left(\frac{{\pi}}{{4}}+\frac{{{tn(p1)}}}{{2}}\right) = {tn(psi1)},\quad \psi_2 = {tn(psi2)}",
                 f"ψ₁ = {sig(psi1)}, ψ₂ = {sig(psi2)}"),
            step("Map coordinates differences (shorter way around)",
                 r"\Delta\psi = \psi_2-\psi_1,\qquad \Delta\lambda \in [-\pi,\pi]",
                 rf"\Delta\psi = {tn(mm['dpsi'])},\qquad \Delta\lambda = {tn(mm['dlam'])}",
                 f"Δψ = {sig(mm['dpsi'])}, Δλ = {sig(mm['dlam'])}"),
            step("Straight line on the flat map, scaled by R", r"d_{\text{flat}} = R\sqrt{\Delta\lambda^2+\Delta\psi^2}",
                 rf"d_{{\text{{flat}}}} = {tn(R)}\sqrt{{{tp(mm['dlam'])}^2+{tp(mm['dpsi'])}^2}}", f"{sig(flat_km)} km"),
            step("Compare with the real distance", r"\text{ratio} = d_{\text{flat}}/d",
                 rf"\text{{ratio}} = \frac{{{tn(flat_km)}}}{{{tn(d_km)}}}", f"{sig(ratio, 4)}×"),
            step("Local scale at each point", r"k = \sec\varphi = \frac{1}{\cos\varphi}",
                 rf"k_A = \frac{{1}}{{\cos({tn(p1)})}} = {tn(sf1, 4)},\qquad k_B = \frac{{1}}{{\cos({tn(p2)})}} = {tn(sf2, 4)}",
                 f"k_A = {sig(sf1, 4)}, k_B = {sig(sf2, 4)}"),
        ]
        metrics.append(_metric(
            "mercator_distortion", "Geometry", "Distance on a flat Mercator map", flat_km, "km",
            f"{space_thousands(flat_km)} km",
            [f"{ratio:.2f}× the real distance", f"scale at A ×{sf1:.2f}, at B ×{sf2:.2f}"],
            explanation("A ruler laid on a Mercator map overstates distances away from the equator.", steps, [C_R],
                        ["Mercator preserves angles, not distances: lengths are stretched by sec φ at latitude φ.",
                         "The straight line on the flat map is a rhumb-like path, not the shortest route; the real great circle is shorter."])))

    # ------------------------------------------------------------------ bearings
    th1 = th_f = None
    if bearings_ok:
        by, bx, th1 = spherical.initial_bearing(p1, l1, p2, l2)
        th_f = spherical.final_bearing(p1, l1, p2, l2)
        _, _, th_back = spherical.initial_bearing(p2, l2, p1, l1)

    bearing_reason = ("identical points" if same else "antipodal" if antipodal else "pole")
    bearing_why = {
        "identical points": "The bearing between identical points is undefined (there is no direction).",
        "antipodal": "Antipodal points are joined by infinitely many great circles, so the bearing is not unique.",
        "pole": "At a pole every direction points south (or north), so the bearing from there is degenerate.",
    }[bearing_reason]
    if th1 is None:
        metrics.append(_undefined("bearing_initial", "Travel", LABEL_COURSE_1, "undefined", bearing_why))
        metrics.append(_undefined("bearing_final", "Travel", LABEL_COURSE_2, "undefined", bearing_why))
    else:
        steps = [
            step("Bearing formula",
                 r"\theta_1 = \operatorname{atan2}\!\big(\sin\Delta\lambda\cos\varphi_2,\ \cos\varphi_1\sin\varphi_2-\sin\varphi_1\cos\varphi_2\cos\Delta\lambda\big)",
                 rf"\theta_1 = \operatorname{{atan2}}\!\big({tn(by)},\ {tn(bx)}\big) = {tn(math.atan2(by, bx))}",
                 f"{sig(math.atan2(by, bx))} rad"),
            step("Normalize to 0–360°", r"\theta = (\theta_1^{\circ}+360^{\circ}) \bmod 360^{\circ}",
                 rf"\theta = ({tn(deg(math.atan2(by, bx)))}^{{\circ}}+360^{{\circ}}) \bmod 360^{{\circ}}",
                 f"{sig(deg(th1))}° ({_compass(th1)})"),
        ]
        metrics.append(_metric(
            "bearing_initial", "Travel", LABEL_COURSE_1, deg(th1), "°",
            f"{deg(th1):.1f}°", [_compass(th1), "azimuth at A, 0° = true north"],
            explanation("The azimuth (clockwise from north) to fly after take-off from A, along the great circle towards B.", steps, [],
                        ["This is the true azimuth, measured from true north; magnetic variation is not applied.",
                         "It is the direction of the shortest route at the coordinates of A. Runway positions and headings and the departure procedure are not known to this app (no information about the runways is assumed), so the actual heading right after take-off differs while the aircraft turns onto the route.",
                         "On a great circle the course changes continuously along the way, which is why the course before landing is different."])))
        steps = [
            step("Initial bearing from B back to A",
                 r"\theta_{BA} = \operatorname{atan2}\!\big(\sin\Delta\lambda'\cos\varphi_1,\ \cos\varphi_2\sin\varphi_1-\sin\varphi_2\cos\varphi_1\cos\Delta\lambda'\big)\ \text{with }\Delta\lambda'=\lambda_1-\lambda_2",
                 None, f"θ_BA = {sig(deg(th_back))}°"),
            step("Turn it around", r"\theta_{\text{final}} = (\theta_{BA}+180^{\circ}) \bmod 360^{\circ}",
                 rf"\theta_{{\text{{final}}}} = ({tn(deg(th_back))}^{{\circ}}+180^{{\circ}}) \bmod 360^{{\circ}}",
                 f"{sig(deg(th_f))}° ({_compass(th_f)})"),
        ]
        change = (deg(th_f) - deg(th1) + 180.0) % 360.0 - 180.0
        steps.append(step("Course change along the route", r"\Delta\theta = \theta_{\text{final}}-\theta_{\text{initial}}\ \ (\text{wrapped to } -180^{\circ}\dots180^{\circ})",
                          rf"\Delta\theta = {tn(deg(th_f))}^{{\circ}}-{tn(deg(th1))}^{{\circ}}",
                          f"{sig(change)}° (negative = turning left / counter-clockwise)"))
        metrics.append(_metric(
            "bearing_final", "Travel", LABEL_COURSE_2, deg(th_f), "°",
            f"{deg(th_f):.1f}°", [_compass(th_f), f"course changes by {abs(change):.1f}° to the {'left' if change < 0 else 'right'} over the route"],
            explanation("The azimuth (clockwise from north) flown immediately before landing at B.", steps, [],
                        ["Final course = the initial course of the reverse trip (B → A), turned by 180°.",
                         "True azimuth from true north; magnetic variation is not applied.",
                         "It is the direction of the great circle at the coordinates of B. Without information about the runways, the final approach and the runway heading are not modelled."])))

    # ------------------------------------------------------------------ midpoint
    mid = None
    if same or antipodal:
        metrics.append(_undefined("midpoint", "Geometry", "Midpoint", "undefined",
                                  "For identical points the midpoint is the point itself; for antipodal points it is not unique."
                                  if antipodal else "Both points coincide, so the midpoint is that point itself."))
    else:
        bx_m, by_m, mid_lat, mid_lon = spherical.midpoint(p1, l1, p2, l2)
        mid = (mid_lat, mid_lon)
        steps = [
            step("Auxiliary terms", r"B_x = \cos\varphi_2\cos\Delta\lambda,\qquad B_y = \cos\varphi_2\sin\Delta\lambda",
                 rf"B_x = \cos({tn(p2)})\cos({tn(dlam)}) = {tn(bx_m)},\quad B_y = \cos({tn(p2)})\sin({tn(dlam)}) = {tn(by_m)}",
                 f"Bx = {sig(bx_m)}, By = {sig(by_m)}"),
            step("Latitude of the midpoint",
                 r"\varphi_m = \operatorname{atan2}\!\left(\sin\varphi_1+\sin\varphi_2,\ \sqrt{(\cos\varphi_1+B_x)^2+B_y^2}\right)",
                 rf"\varphi_m = \operatorname{{atan2}}\!\left(\sin({tn(p1)})+\sin({tn(p2)}),\ \sqrt{{(\cos({tn(p1)})+{tp(bx_m)})^2+{tp(by_m)}^2}}\right)",
                 f"{sig(mid_lat)} rad = {sig(deg(mid_lat))}°"),
            step("Longitude of the midpoint", r"\lambda_m = \lambda_1+\operatorname{atan2}\!\big(B_y,\ \cos\varphi_1+B_x\big)",
                 rf"\lambda_m = {tn(l1)}+\operatorname{{atan2}}\!\big({tn(by_m)},\ \cos({tn(p1)})+{tp(bx_m)}\big)",
                 f"{sig(mid_lon)} rad = {sig(deg(mid_lon))}° (normalized to −180…180)"),
        ]
        metrics.append(_metric(
            "midpoint", "Geometry", "Midpoint", deg(mid_lat), "°",
            latlon_text(deg(mid_lat), deg(mid_lon), 2), [],
            explanation("The point halfway along the great circle from A to B.", steps, [],
                        ["Note it is not the average of the coordinates: the great circle bends towards the pole."])))

    # ------------------------------------------------------------------ vertex_latitude
    vertex_marker = None
    if antipodal:
        metrics.append(_undefined("vertex_latitude", "Geometry", "Highest latitude reached", "undefined",
                                  "Antipodal points lie on infinitely many great circles, so the highest latitude is not unique."))
    else:
        lat_a_abs, lat_b_abs = abs(deg(p1)), abs(deg(p2))
        vtx = None
        steps = []
        if bearings_ok:
            vtx = spherical.vertex_of_route(p1, l1, th1, th_f, delta)
            phi_v_full = math.acos(min(1.0, abs(math.sin(th1) * math.cos(p1))))
            steps.append(step(
                "Highest latitude of the full great circle (Clairaut's relation)",
                r"\varphi_v = \arccos\!\left(\left|\sin\theta_1\cos\varphi_1\right|\right)",
                rf"\varphi_v = \arccos\!\left(\left|\sin({tn(th1)})\cos({tn(p1)})\right|\right) = {tn(phi_v_full)}",
                f"{sig(deg(phi_v_full))}°"))
            steps.append(step(
                "Is the vertex between A and B?",
                r"\text{north vertex: } \cos\theta_1>0\ \text{and}\ \cos\theta_{\text{final}}<0;\quad \text{south vertex: the mirror}",
                rf"\cos({tn(th1)}) = {tn(math.cos(th1))},\qquad \cos({tn(th_f)}) = {tn(math.cos(th_f))}",
                "Yes — the route turns around inside the segment" if vtx else "No — the route is still climbing or descending at B"))
        if vtx:
            best_lat, best_lon, kind = vtx["lat"], vtx["lon"], "vertex"
            steps.append(step(
                "Where is the vertex?", r"\tan\sigma_v = \frac{|\cos\theta_1|}{\pm\tan\varphi_1},\quad (\varphi_v,\lambda_v)=\text{destination}(A,\theta_1,\sigma_v)",
                None, f"{sig(R * vtx['sigma'])} km from A, at {latlon_text(deg(best_lat), deg(best_lon), 2)}"))
            vertex_marker = (best_lat, best_lon)
        else:
            if lat_a_abs >= lat_b_abs:
                best_lat, best_lon = p1, l1
            else:
                best_lat, best_lon = p2, l2
            kind = "endpoint"
            steps.append(step("Highest latitude is at an endpoint", r"\varphi_{\max} = \max(|\varphi_1|,|\varphi_2|)",
                              rf"\max({tn(lat_a_abs)}^{{\circ}},\ {tn(lat_b_abs)}^{{\circ}})",
                              f"{sig(abs(deg(best_lat)))}°"))
        hemi = "north" if best_lat > 1e-12 else "south" if best_lat < -1e-12 else "equator"
        hemi_short = {"north": "N", "south": "S", "equator": ""}[hemi]
        top = abs(deg(best_lat))
        where = {"vertex": "reached between A and B", "endpoint": "at the endpoint"}[kind]
        metrics.append(_metric(
            "vertex_latitude", "Geometry", "Highest latitude reached", top, "°",
            f"{top:.2f}°{hemi_short}", [where, latlon_text(deg(best_lat), deg(best_lon), 2)],
            explanation("How far towards a pole the shortest route takes you.", steps, [],
                        ["Great circles bulge towards the poles on the map; this is why flights from Europe to the US pass near Greenland."]
                        if kind == "vertex" else
                        ["For this pair the route does not turn around between A and B, so the highest latitude is at one of the endpoints."])))

    # ------------------------------------------------------------------ crossings
    cross_found = []
    frame = None if (same or antipodal) else crossings.route_frame(p1, l1, p2, l2)
    if frame is None:
        metrics.append(_undefined("crossings", "Geometry", "Route crossings", "undefined",
                                  "Identical points have no route, and for antipodal points there are infinitely many routes, so there is no unique crossing."))
    else:
        a_vec, e2_vec, n_vec = frame
        c_max, sigma0 = crossings.latitude_info(a_vec, e2_vec)
        top_lat = deg(math.asin(min(1.0, c_max)))
        along, missed = [], []
        for cid, clabel, kind, cval in CROSSING_SPECS:
            if kind == "lat":
                res = crossings.latitude_crossings(a_vec, e2_vec, delta, rad(cval))
            else:
                r = crossings.meridian_crossing(a_vec, e2_vec, n_vec, delta, rad(cval))
                res = "along" if r == "along" else ([] if r is None else [r])
            if res == "along":
                along.append(clabel)
            elif not res:
                missed.append((clabel, kind, cval))
            for sigma in ([] if res == "along" else res):
                clat, clon = crossings.point_at(a_vec, e2_vec, sigma)
                clat = 0.0 if abs(clat) < 1e-12 else clat                       # drop floating-point noise
                clon = 0.0 if abs(clon) < 1e-12 else (math.pi if abs(abs(clon) - math.pi) < 1e-9 else clon)
                course = crossings.course_at(a_vec, e2_vec, sigma)
                cross_found.append({"id": cid, "label": clabel, "kind": kind, "val": cval, "sigma": sigma,
                                    "lat": clat, "lon": clon, "course": course,
                                    "km": R * sigma, "fraction": sigma / delta})
        cross_found.sort(key=lambda c: c["sigma"])

        def where(c):   # compact: the longitude for a latitude line, the latitude for a meridian
            return latlon_text(deg(c["lat"]), deg(c["lon"]), 2).split(", ")[1 if c["kind"] == "lat" else 0]

        steps = [
            step("The route as a plane through the Earth's centre",
                 r"\begin{aligned}\mathbf{A}&=(\cos\varphi\cos\lambda,\ \cos\varphi\sin\lambda,\ \sin\varphi)\\"
                 r"\mathbf{n}&=\frac{\mathbf{A}\times\mathbf{B}}{|\mathbf{A}\times\mathbf{B}|},\qquad \mathbf{e}_2=\mathbf{n}\times\mathbf{A}\\"
                 r"\mathbf{P}(\sigma)&=\mathbf{A}\cos\sigma+\mathbf{e}_2\sin\sigma\end{aligned}",
                 rf"\begin{{aligned}}\mathbf{{A}}&=({tn(a_vec[0])},\ {tn(a_vec[1])},\ {tn(a_vec[2])})\\"
                 rf"\mathbf{{e}}_2&=({tn(e2_vec[0])},\ {tn(e2_vec[1])},\ {tn(e2_vec[2])})\end{{aligned}}",
                 f"P(σ) is the point σ radians from A along the route: σ = 0 at A and σ = δ = {sig(delta)} rad at B"),
            step("Crossing a circle of latitude φc",
                 r"\begin{aligned}A_z\cos\sigma+e_z\sin\sigma&=\sin\varphi_c\ \Rightarrow\ \sigma=\sigma_0\pm\arccos\frac{\sin\varphi_c}{C}\\"
                 r"C&=\sqrt{A_z^2+e_z^2},\qquad \sigma_0=\operatorname{atan2}(e_z,A_z)\end{aligned}",
                 rf"\begin{{aligned}}C&=\sqrt{{{tp(a_vec[2])}^2+{tp(e2_vec[2])}^2}}={tn(c_max)}\\"
                 rf"\sigma_0&=\operatorname{{atan2}}({tn(e2_vec[2])},\ {tn(a_vec[2])})={tn(sigma0)}\end{{aligned}}",
                 f"The whole great circle never goes beyond latitude arcsin(C) = {sig(top_lat)}°, so circles further out are not crossed"),
            step("Crossing a meridian λc",
                 r"\begin{aligned}\mathbf{P}&=\pm(\mathbf{n}\times\mathbf{m}),\qquad \mathbf{m}=(-\sin\lambda_c,\ \cos\lambda_c,\ 0)\\"
                 r"\sigma&=\operatorname{atan2}(\mathbf{P}\cdot\mathbf{e}_2,\ \mathbf{P}\cdot\mathbf{A})\end{aligned}",
                 None,
                 "The sign is chosen so that P lies on the requested meridian and not on the opposite one; σ must lie between 0 and δ"),
        ]
        for c in cross_found:
            course_txt = f"course {deg(c['course']):.1f}° ({_compass(c['course'])})" if c["course"] is not None else "course undefined at a pole"
            end_note = " (at A)" if c["sigma"] < 1e-9 else " (at B)" if delta - c["sigma"] < 1e-9 else ""
            if c["kind"] == "lat":
                ratio_sub = rf"\sigma={tn(sigma0)}\pm\arccos\frac{{\sin({tn(rad(c['val']))})}}{{{tn(c_max)}}}\ \Rightarrow\ \sigma={tn(c['sigma'])}"
                ex_tex = r"\sigma=\sigma_0\pm\arccos\frac{\sin\varphi_c}{C}"
            else:
                ratio_sub = rf"\sigma=\operatorname{{atan2}}(\mathbf{{P}}\cdot\mathbf{{e}}_2,\ \mathbf{{P}}\cdot\mathbf{{A}})={tn(c['sigma'])}"
                ex_tex = r"\sigma=\operatorname{atan2}(\mathbf{P}\cdot\mathbf{e}_2,\ \mathbf{P}\cdot\mathbf{A})"
            steps.append(step(
                f"{c['label']}{end_note}", ex_tex, ratio_sub,
                f"{latlon_text(deg(c['lat']), deg(c['lon']), 3)} · {space_thousands(c['km'])} km from A ({c['fraction'] * 100:.1f} % of the route) · "
                f"{course_txt} · about {hm(airborne_h * c['fraction'])} after take-off"))
        if along:
            steps.append(step("Route runs along a line", None, None,
                              "; ".join(f"{n}: the whole route lies on it, so there is no single crossing point" for n in along)))
        if missed:
            reasons = []
            for clabel, kind, cval in missed:
                if kind == "lat":
                    reasons.append(f"{clabel} ({cval:+.2f}°): " + (
                        f"the great circle never goes beyond {sig(top_lat)}° latitude" if abs(math.sin(rad(cval))) > c_max + 1e-12
                        else "the great circle reaches it, but not between A and B"))
                else:
                    reasons.append(f"{clabel}: not crossed between A and B")
            steps.append(step("Not crossed", None, None, "; ".join(reasons)))

        table = [{"label": c["label"] + (" (at A)" if c["sigma"] < 1e-9 else " (at B)" if delta - c["sigma"] < 1e-9 else ""),
                  "display": f"{where(c)} · {space_thousands(c['km'])} km"} for c in cross_found]
        table += [{"label": n, "display": "route runs along it"} for n in along]
        n_found = len(cross_found)
        sec = [f"not crossed: {', '.join(m[0] for m in missed)}"] if missed else []
        metrics.append(_metric(
            "crossings", "Geometry", "Route crossings (equator, circles, meridians)", float(n_found), None,
            f"{n_found} crossing{'s' if n_found != 1 else ''}" if (n_found or along) else "none of the listed lines", sec,
            explanation("Where the shortest route crosses the equator, the tropics, the polar circles and the 0° and 180° meridians, in travel order.",
                        steps, [const("ε", f"{K.AXIAL_TILT_DEG}°", "axial tilt: tropics at ±ε, polar circles at ±(90° − ε)"), C_R],
                        ["The tropics and polar circles use the Earth's axial tilt of 23.44° (tropics at ±23.44°, polar circles at ±66.56°). The real tilt drifts by about half an arc-second per year.",
                         "Positions are computed on a sphere; on the real ellipsoid they shift by a few kilometres.",
                         "The time after take-off is the share of the route flown times the airborne time.",
                         "A line the route only touches counts once; a crossing exactly at A or B is marked as such."]),
            table=table))

    # ------------------------------------------------------------------ rhumb_line
    rh = None
    rhumb_ok = not (pole_a or pole_b or same)
    if pole_a or pole_b:
        metrics.append(_undefined("rhumb_line", "Geometry", "Rhumb line (constant bearing)", "undefined",
                                  "The stretched latitude ψ = ln tan(π/4 + φ/2) is infinite at a pole, so the rhumb line is undefined there."))
    elif same:
        metrics.append(_metric("rhumb_line", "Geometry", "Rhumb line (constant bearing)", 0.0, "km", "0 km", [],
                               explanation("Identical points: the rhumb distance is 0.",
                                           [step("Identical points", None, None, "d = 0 km; the bearing is undefined")], [], [])))
    else:
        rh = rhumb.rhumb(p1, l1, p2, l2)
        rh_km = R * rh["dist"]
        extra = rh_km - d_km
        extra_pct = extra / d_km * 100.0 if d_km > 0 else 0.0
        steps = [
            step("Stretched latitude difference", r"\Delta\psi = \ln\frac{\tan(\pi/4+\varphi_2/2)}{\tan(\pi/4+\varphi_1/2)}",
                 rf"\Delta\psi = \ln\frac{{\tan(\pi/4+{tn(p2)}/2)}}{{\tan(\pi/4+{tn(p1)}/2)}}", f"{sig(rh['dpsi'])}"),
            step("Scale factor q", r"q = \frac{\Delta\varphi}{\Delta\psi}\quad(\text{or }\cos\varphi_1\text{ if }\Delta\psi\approx 0)",
                 rf"q = \frac{{{tn(rh['dphi'])}}}{{{tn(rh['dpsi'])}}}" if abs(rh["dpsi"]) > 1e-12 else rf"q = \cos({tn(p1)})",
                 sig(rh["q"])),
            step("Longitude difference, shorter way around", r"|\Delta\lambda|>\pi\ \Rightarrow\ \Delta\lambda \leftarrow \Delta\lambda-\operatorname{sign}(\Delta\lambda)\,2\pi",
                 None, f"Δλ = {sig(rh['dlam'])} rad"),
            step("Rhumb distance", r"d_{\text{rhumb}} = R\sqrt{\Delta\varphi^2+q^2\Delta\lambda^2}",
                 rf"d_{{\text{{rhumb}}}} = {tn(R)}\sqrt{{{tp(rh['dphi'])}^2+{tp(rh['q'])}^2\cdot {tp(rh['dlam'])}^2}}", f"{sig(rh_km)} km"),
            step("Constant bearing", r"\theta_{\text{rhumb}} = \operatorname{atan2}(\Delta\lambda,\ \Delta\psi)",
                 rf"\theta_{{\text{{rhumb}}}} = \operatorname{{atan2}}({tn(rh['dlam'])},\ {tn(rh['dpsi'])})",
                 f"{sig(deg(rh['theta']))}° ({_compass(rh['theta'])})"),
            step("Extra distance compared to the great circle", r"\Delta d = d_{\text{rhumb}}-d_{\text{gc}}",
                 rf"\Delta d = {tn(rh_km)}-{tn(d_km)}", f"{sig(extra)} km ({sig(extra_pct, 3)} %)"),
        ]
        metrics.append(_metric(
            "rhumb_line", "Geometry", "Rhumb line (constant bearing)", rh_km, "km",
            f"{space_thousands(rh_km)} km",
            [f"bearing {deg(rh['theta']):.1f}° ({_compass(rh['theta'])})", f"+{space_thousands(extra)} km (+{extra_pct:.2f} %)".replace("+-", "−")],
            explanation("A path that keeps one constant compass bearing: easy to steer, but longer than the great circle.",
                        steps, [C_R],
                        ["A rhumb line is a straight line on a Mercator map.",
                         "Along the equator or a meridian the rhumb line and the great circle coincide."])))

    # ------------------------------------------------------------------ antipodes
    ant_a = spherical.antipode(p1, l1)
    ant_b = spherical.antipode(p2, l2)
    steps = [
        step("Antipode of a point", r"\varphi_a = -\varphi,\qquad \lambda_a = \lambda\pm180^{\circ}\ (\text{normalized to }[-180^{\circ},180^{\circ}])",
             rf"A:\ \varphi_a = -{tp(a_lat)}^{{\circ}},\ \lambda_a = {tn(a_lon)}^{{\circ}}\pm180^{{\circ}}",
             f"A′ = {latlon_text(deg(ant_a[0]), deg(ant_a[1]), 3)}"),
        step("For point B", r"\varphi_a = -\varphi,\qquad \lambda_a = \lambda\pm180^{\circ}",
             rf"B:\ \varphi_a = -{tp(b_lat)}^{{\circ}},\ \lambda_a = {tn(b_lon)}^{{\circ}}\pm180^{{\circ}}",
             f"B′ = {latlon_text(deg(ant_b[0]), deg(ant_b[1]), 3)}"),
    ]
    metrics.append(_metric(
        "antipodes", "Geometry", "Antipodes", None, None, "A′ and B′",
        [f"A′: {latlon_text(deg(ant_a[0]), deg(ant_a[1]), 2)}", f"B′: {latlon_text(deg(ant_b[0]), deg(ant_b[1]), 2)}"],
        explanation("The point exactly on the other side of the Earth. Digging straight down from A would come out at A′.", steps, [],
                    ["Most antipodes of land points are in the ocean."])))

    # ------------------------------------------------------------------ chord_and_bulge
    chord_km = spherical.chord_length(R, delta)
    sag_km = spherical.sagitta(R, delta)
    approx_h = d_km ** 2 / (8.0 * R)
    err_pct = (approx_h - sag_km) / sag_km * 100.0 if sag_km > 0 else 0.0
    steps = [
        step("Chord (straight tunnel)", r"c = 2R\sin\frac{\delta}{2}",
             rf"c = 2\cdot {tn(R)}\cdot\sin\frac{{{tn(delta)}}}{{2}}", f"{sig(chord_km)} km"),
        step("Sagitta (deepest point of the tunnel / bulge of the surface)", r"h = R\left(1-\cos\frac{\delta}{2}\right)",
             rf"h = {tn(R)}\left(1-\cos\frac{{{tn(delta)}}}{{2}}\right)", f"{sig(sag_km)} km"),
        step("Small-distance approximation", r"h \approx \frac{d^2}{8R}",
             rf"h \approx \frac{{{tn(d_km)}^2}}{{8\cdot {tn(R)}}}",
             f"{sig(approx_h)} km (error {sig(err_pct, 2)} % vs exact)"),
    ]
    metrics.append(_metric(
        "chord_and_bulge", "Through the Earth", "Straight tunnel & bulge", chord_km, "km",
        f"{space_thousands(chord_km)} km tunnel", [f"{sig(sag_km, 4)} km deep at the middle"],
        explanation("A straight tunnel between A and B is shorter than the surface route and dips below the surface.", steps, [C_R],
                    ["For δ = π (antipodal points) the chord is the diameter 2R and the depth is R."])))

    # ------------------------------------------------------------------ gravity_train
    omega, t_trip, v_max = travel.gravity_train(R * 1000.0, K.G, chord_km * 1000.0)
    steps = [
        step("Angular frequency of the oscillation", r"\omega = \sqrt{g/R}",
             rf"\omega = \sqrt{{{tn(K.G)}\ \text{{m/s}}^2 / {tn(R * 1000.0)}\ \text{{m}}}}", f"{sig(omega)} rad/s"),
        step("Trip time (half a period), independent of the distance", r"T_{\text{trip}} = \pi\sqrt{R/g}",
             rf"T_{{\text{{trip}}}} = \pi\sqrt{{{tn(R * 1000.0)}/{tn(K.G)}}}", f"{sig(t_trip)} s = {sig(t_trip / 60.0)} min"),
        step("Top speed at the middle of the tunnel", r"v_{\max} = \omega\cdot\frac{c}{2}",
             rf"v_{{\max}} = {tn(omega)}\cdot\frac{{{tn(chord_km * 1000.0)}}}{{2}}", f"{sig(v_max)} m/s = {sig(v_max * 3.6)} km/h"),
    ]
    metrics.append(_metric(
        "gravity_train", "Through the Earth", "Gravity train", t_trip / 60.0, "min",
        f"{t_trip / 60.0:.1f} min", [f"top speed {space_thousands(v_max * 3.6)} km/h"],
        explanation("Fall through the straight tunnel with no friction: the trip takes about 42 minutes, no matter how far apart A and B are.",
                    steps, [const("g", f"{K.G} m/s²", "standard gravity"), C_R],
                    ["Surprising result: a tunnel between neighbouring towns takes the same 42.2 minutes as one through the centre of the Earth.",
                     "Assumes a uniform-density Earth, no friction and no air resistance (the real Earth is denser in the core, which would shorten the trip)."])))

    # ------------------------------------------------------------------ flight_time
    steps = [
        step("Cruise time", r"t_{\text{cruise}} = \frac{d}{v}",
             rf"t_{{\text{{cruise}}}} = \frac{{{tn(d_km)}\ \text{{km}}}}{{{tn(cruise_kmh)}\ \text{{km/h}}}}", f"{sig(cruise_h)} h = {hm(cruise_h)}"),
        step("Add climb and descent (airborne time: take-off to landing)",
             r"t_{\text{airborne}} = t_{\text{cruise}} + t_{\text{climb/descent}}",
             rf"t_{{\text{{airborne}}}} = {tn(cruise_h)}\ \text{{h}} + \frac{{{tn(climb_descent_min)}}}{{60}}\ \text{{h}}",
             f"{sig(airborne_h)} h = {hm(airborne_h)}"),
        step("Add taxiing (gate to gate)", r"t_{\text{gate to gate}} = t_{\text{airborne}} + t_{\text{taxi}}",
             rf"t_{{\text{{gate to gate}}}} = {tn(airborne_h)}\ \text{{h}} + \frac{{{tn(taxi_min)}}}{{60}}\ \text{{h}}",
             f"{sig(gate_h)} h = {hm(gate_h)}"),
    ]
    metrics.append(_metric(
        "flight_time", "Travel", "Flight time (take-off to landing)", airborne_h, "h", f"{hm(airborne_h)} in the air",
        [f"gate to gate {hm(gate_h)}", f"cruise {hm(cruise_h)} at {cruise_kmh:g} km/h + {climb_descent_min:g} min climb & descent",
         f"{taxi_min:g} min taxiing is not counted as flight time"],
        explanation("The time actually spent in the air from take-off to landing, plus the gate-to-gate time including taxiing.", steps,
                    [const("v", f"{cruise_kmh:g} km/h", "cruise ground speed (adjustable)"),
                     const("t_climb/descent", f"{climb_descent_min:g} min", "extra airborne time for climb and descent (adjustable assumption)"),
                     const("t_taxi", f"{taxi_min:g} min", "taxiing at both airports together (adjustable assumption)")],
                    ["Airborne time runs from take-off to landing; taxiing is excluded. The gate-to-gate time adds the taxi allowance.",
                     "The distance is measured point to point between the two coordinates. Runway positions and lengths, departure and arrival procedures and holding patterns are not known and not modelled.",
                     "Ignores winds (the jet stream can change real times by an hour or more) and airways.",
                     "The climb/descent and taxi allowances are rough assumptions; change them under Options."])))

    # ------------------------------------------------------------------ latency
    t_vac, t_fib, rtt = travel.light_times_s(d_km, K.C_KM_S, K.FIBER_INDEX)
    steps = [
        step("Light in vacuum, one way", r"t_{\text{vac}} = \frac{d}{c}",
             rf"t_{{\text{{vac}}}} = \frac{{{tn(d_km)}}}{{{tn(K.C_KM_S)}}}", f"{sig(t_vac * 1000)} ms"),
        step("Light in fiber, one way", r"t_{\text{fiber}} = \frac{d}{c/n}",
             rf"t_{{\text{{fiber}}}} = \frac{{{tn(d_km)}}}{{{tn(K.C_KM_S)}/{tn(K.FIBER_INDEX)}}}", f"{sig(t_fib * 1000)} ms"),
        step("Minimum round-trip time (ping)", r"\mathrm{RTT}_{\min} = 2\,t_{\text{fiber}}",
             rf"\mathrm{{RTT}}_{{\min}} = 2\cdot {tn(t_fib * 1000)}\ \text{{ms}}", f"{sig(rtt * 1000)} ms"),
    ]
    metrics.append(_metric(
        "latency", "Travel", "Light & fiber latency", rtt * 1000, "ms",
        f"RTT ≥ {rtt * 1000:.1f} ms", [f"fiber one-way {t_fib * 1000:.1f} ms", f"vacuum one-way {t_vac * 1000:.1f} ms"],
        explanation("The physical lower bound on ping between A and B.", steps,
                    [const("c", f"{K.C_KM_S} km/s", "speed of light in vacuum"),
                     const("n", f"{K.FIBER_INDEX}", "refractive index of single-mode fiber")],
                    ["Real cables are longer than the great circle and routers add delay, so real pings are typically 1.5–3× higher."])))

    # ------------------------------------------------------------------ travel_times
    table = []
    for label, kmh in K.REFERENCE_SPEEDS:
        hours = d_km / kmh
        table.append({"label": label, "display": hm(hours)})
    air = d_km / K.CRUISE_KMH_DEFAULT
    steps = [
        step("Time at constant speed", r"t = \frac{d}{v}", rf"t = \frac{{{tn(d_km)}\ \text{{km}}}}{{v}}",
             "; ".join(f"{r['label']}: {r['display']}" for r in table)),
    ]
    metrics.append(_metric(
        "travel_times", "Travel", "How long at…", air, "h", f"{hm(air)} by airliner", [],
        explanation("The same distance at different speeds.", steps,
                    [const(lbl, f"{sig(v)} km/h", "reference speed") for lbl, v in K.REFERENCE_SPEEDS],
                    ["The ISS speed is its orbital speed at about 400 km altitude, used here only as a fun comparison.",
                     "Walking, driving and train times ignore the fact that you cannot travel the great circle over oceans."]),
        table=table))

    # ------------------------------------------------------------------ horizon_los
    hz = {}
    for key, h in (("a", height_a_m), ("b", height_b_m), ("cruise", K.CRUISE_ALTITUDE_M)):
        hz[key] = (travel.horizon_distance_exact_km(R, h), travel.horizon_distance_approx_km(R, h))
    los_max = travel.horizon_distance_approx_km(R, height_a_m) + travel.horizon_distance_approx_km(R, height_b_m)
    visible = d_km <= los_max
    steps = [
        step("Horizon distance from height h (exact)", r"d_h = R\arccos\frac{R}{R+h}",
             rf"d_A = {tn(R)}\arccos\frac{{{tn(R)}}}{{{tn(R)}+{tn(height_a_m / 1000.0)}}}", f"A ({sig(height_a_m)} m): {sig(hz['a'][0])} km"),
        step("Small-height approximation", r"d_h \approx \sqrt{2Rh}",
             rf"d_A \approx \sqrt{{2\cdot {tn(R)}\cdot {tn(height_a_m / 1000.0)}}}", f"A: {sig(hz['a'][1])} km; B ({sig(height_b_m)} m): {sig(hz['b'][1])} km"),
        step("Airliner at cruise altitude", r"d_h = \sqrt{2Rh}",
             rf"d_{{\text{{cruise}}}} \approx \sqrt{{2\cdot {tn(R)}\cdot {tn(K.CRUISE_ALTITUDE_M / 1000.0)}}}", f"{sig(hz['cruise'][1])} km at {sig(K.CRUISE_ALTITUDE_M)} m"),
        step("Maximum distance at which A and B can see each other", r"d_{\max} = \sqrt{2Rh_A}+\sqrt{2Rh_B}",
             rf"d_{{\max}} = {tn(hz['a'][1])}+{tn(hz['b'][1])}", f"{sig(los_max)} km"),
        step("Can they see each other?", r"d \le d_{\max}", rf"{tn(d_km)} \le {tn(los_max)}",
             "Yes (ignoring terrain)" if visible else "No — the curvature of the Earth is in the way"),
    ]
    metrics.append(_metric(
        "horizon_los", "Travel", "Horizon & line of sight", los_max, "km",
        f"A sees {hz['a'][1]:.1f} km, B sees {hz['b'][1]:.1f} km",
        [f"airliner at {space_thousands(K.CRUISE_ALTITUDE_M)} m: {space_thousands(hz['cruise'][1])} km",
         "A and B can see each other" if visible else "A and B are hidden behind the curvature"],
        explanation("How far you can see before the curve of the Earth hides the ground.", steps, [C_R],
                    ["Ignores terrain, buildings and atmospheric refraction (which extends the horizon by roughly 8%).",
                     "Heights are adjustable in the panel; the default is eye height of a standing person."])))

    # ------------------------------------------------------------------ solar_offset
    dl_deg = (deg(dlam) + 180.0) % 360.0 - 180.0
    solar_h = dl_deg / 15.0
    ahead = "ahead of" if solar_h > 0 else "behind"
    steps = [
        step("Longitude difference, shorter way around", r"\Delta\lambda^{\circ} \in [-180^{\circ},180^{\circ}]",
             rf"\Delta\lambda = {tn(b_lon)}^{{\circ}}-{tp(a_lon)}^{{\circ}}", f"{sig(dl_deg)}°"),
        step("Convert to hours (the Sun moves 15° per hour)", r"\Delta t_{\text{solar}} = \frac{\Delta\lambda^{\circ}}{15^{\circ}/\text{h}}",
             rf"\Delta t_{{\text{{solar}}}} = \frac{{{tn(dl_deg)}}}{{15}}", f"{sig(solar_h)} h = {hm(abs(solar_h))} {ahead} A"),
    ]
    metrics.append(_metric(
        "solar_offset", "Sun & time", "Solar time offset", solar_h, "h",
        f"{hm(abs(solar_h))} {'ahead' if solar_h > 0 else 'behind'}" if abs(solar_h) > 1e-9 else "none",
        ["by the sun, B relative to A"],
        explanation("The Sun crosses every 15° of longitude in one hour, so the position of the Sun differs by this much between A and B.", steps, [],
                    ["Civil time zones follow borders and politics, not just longitude — see the time-zone metric."])))

    # ------------------------------------------------------------------ timezone_diff
    zi_a = timezones.zone_info(a_lat, a_lon, day)
    zi_b = timezones.zone_info(b_lat, b_lon, day)
    diff_h = zi_b["offset_h"] - zi_a["offset_h"]

    def zname(zi):
        return (zi["tzid"] or "open ocean") + f" ({offset_text(zi['offset_h'])}{', nominal' if zi['nominal'] else ''})"

    steps = [
        step("Find the time zone of each point (ray-casting point-in-polygon on bundled boundaries)", None, None,
             f"A: {zname(zi_a)}; B: {zname(zi_b)}"),
        step("UTC offset on the chosen date (daylight saving included)", r"\text{offset} = \text{local time} - \text{UTC}",
             rf"\text{{{day.isoformat()}}}:\ A = {tn(zi_a['offset_h'])}\,\text{{h}},\quad B = {tn(zi_b['offset_h'])}\,\text{{h}}",
             f"A: {offset_text(zi_a['offset_h'])}, B: {offset_text(zi_b['offset_h'])}"),
        step("Difference", r"\Delta t_{\text{civil}} = \text{offset}_B - \text{offset}_A",
             rf"\Delta t_{{\text{{civil}}}} = {tn(zi_b['offset_h'])} - {tp(zi_a['offset_h'])}", f"{sig(diff_h)} h"),
    ]
    tz_version = timezones.tz_database_version()
    tz_notes = [f"The time-zone rules come from the IANA tz database release {tz_version}, which reflects today's rules. The zone borders are today's borders as well.",
                "Time-zone agreements and daylight-saving rules can change through future political decisions, which this app cannot know. Dates after today therefore assume that today's rules simply continue: no new zones and no changes to daylight saving.",
                "For earlier dates each zone's historical UTC offsets and daylight-saving rules are used, but with today's zone borders: a region that changed zone since then is shown with the history of its present zone.",
                "Pick any date from 1 January 1970 to 31 December 2049 under Options.",
                "Zone boundaries are simplified (about 3 km), so points very close to a border may resolve to the neighbouring zone.",
                f"Offsets are for 12:00 UTC on {day.isoformat()}; the difference can change by an hour around daylight-saving switches."]
    if zi_a["nominal"] or zi_b["nominal"]:
        tz_notes.append("A point outside every zone polygon (open ocean) uses the nominal zone round(longitude/15°) hours.")
    metrics.append(_metric(
        "timezone_diff", "Sun & time", "Time-zone difference", diff_h, "h",
        (f"{hm(abs(diff_h))} {'ahead' if diff_h > 0 else 'behind'}" if abs(diff_h) > 1e-9 else "same time"),
        [f"A: {zname(zi_a)}", f"B: {zname(zi_b)}", f"{day.isoformat()} · today's rules (tz database {tz_version}); future changes unknown"],
        explanation("How many hours the clocks differ between A and B on the chosen date.", steps, [], tz_notes)))

    # ------------------------------------------------------------------ sun_a / sun_b
    n_day = day.timetuple().tm_yday
    for key, label, lat_r, lon_r, lat_d, lon_d in (("sun_a", "Sun at A", p1, l1, a_lat, a_lon),
                                                    ("sun_b", "Sun at B", p2, l2, b_lat, b_lon)):
        s = sun.sun_times(lat_r, lon_r, n_day, K.AXIAL_TILT_DEG, K.SUN_ALTITUDE_DEG)
        steps = [
            step("Day of year", None, None, f"{day.isoformat()} → N = {n_day}"),
            step("Solar declination", r"\delta_\odot = -23.44^{\circ}\cos\!\left(\frac{360^{\circ}}{365}(N+10)\right)",
                 rf"\delta_\odot = -23.44^{{\circ}}\cos\!\left(\frac{{360^{{\circ}}}}{{365}}({n_day}+10)\right)",
                 f"{sig(deg(s['decl']))}°"),
        ]
        if s["cos_w0"] is not None:
            steps.append(step(
                "Hour angle of sunrise/sunset", r"\cos\omega_0 = \frac{\sin h_0-\sin\varphi\sin\delta_\odot}{\cos\varphi\cos\delta_\odot},\quad h_0=-0.833^{\circ}",
                rf"\cos\omega_0 = \frac{{\sin(-0.833^{{\circ}})-\sin({tn(lat_r)})\sin({tn(s['decl'])})}}{{\cos({tn(lat_r)})\cos({tn(s['decl'])})}}",
                sig(s["cos_w0"])))
        else:
            steps.append(step("Pole: cos φ = 0", r"\text{Sun is up all day iff } \sin\varphi\sin\delta_\odot > \sin h_0",
                              None, "polar day" if s["state"] == "polar_day" else "polar night"))
        if s["state"] == "polar_day":
            steps.append(step("Polar day", r"\cos\omega_0 < -1", None, "The Sun does not set: 24 h of daylight."))
            disp, sec = "polar day (24 h)", ["the Sun does not set"]
        elif s["state"] == "polar_night":
            steps.append(step("Polar night", r"\cos\omega_0 > 1", None, "The Sun does not rise: 0 h of daylight."))
            disp, sec = "polar night (0 h)", ["the Sun does not rise"]
        else:
            steps.append(step("Day length", r"L = \frac{2\,\omega_0^{\circ}}{15^{\circ}/\text{h}}",
                              rf"\omega_0 = \arccos({tn(s['cos_w0'])}) = {tn(s['w0_deg'])}^{{\circ}},\quad L = \frac{{2\cdot {tn(s['w0_deg'])}}}{{15}}",
                              f"{sig(s['day_length_h'])} h = {hm(s['day_length_h'])}"))
        steps.append(step("Equation of time", r"B = \frac{360^{\circ}}{365}(N-81),\quad \mathrm{EoT} = 9.87\sin 2B - 7.53\cos B - 1.5\sin B\ \text{[min]}",
                          None, f"{sig(s['eot_min'])} min"))
        steps.append(step("Solar noon (UTC)", r"t_{\text{noon}} = 12 - \frac{\lambda^{\circ}}{15} - \frac{\mathrm{EoT}}{60}",
                          rf"t_{{\text{{noon}}}} = 12 - \frac{{{tn(lon_d)}}}{{15}} - \frac{{{tn(s['eot_min'])}}}{{60}}",
                          f"{sig(s['solar_noon_h'])} h = {utc_hm(s['solar_noon_h'])}"))
        if s["state"] == "normal":
            steps.append(step("Sunrise and sunset (UTC)", r"t_{\text{rise,set}} = t_{\text{noon}} \mp \frac{\omega_0^{\circ}}{15}",
                              rf"t_{{\text{{rise}}}} = {tn(s['solar_noon_h'])} - \frac{{{tn(s['w0_deg'])}}}{{15}},\quad t_{{\text{{set}}}} = {tn(s['solar_noon_h'])} + \frac{{{tn(s['w0_deg'])}}}{{15}}",
                              f"sunrise {utc_hm(s['sunrise_h'])}, sunset {utc_hm(s['sunset_h'])}"))
            disp = hm(s["day_length_h"]) + " of daylight"
            sec = [f"sunrise {utc_hm(s['sunrise_h'])}", f"sunset {utc_hm(s['sunset_h'])}", f"solar noon {utc_hm(s['solar_noon_h'])}"]
        else:
            sec.append(f"solar noon {utc_hm(s['solar_noon_h'])}")
        metrics.append(_metric(
            key, "Sun & time", label, s["day_length_h"], "h", disp, sec,
            explanation(f"Approximate sunrise, sunset and day length at {'A' if key == 'sun_a' else 'B'} on {day.isoformat()}.", steps,
                        [const("h₀", f"{K.SUN_ALTITUDE_DEG}°", "sun altitude at sunrise/sunset (refraction + solar disc)"),
                         const("ε", f"{K.AXIAL_TILT_DEG}°", "axial tilt of the Earth")],
                        ["Accuracy is within a few minutes; all times are in UTC.",
                         "Close to the polar circles the day length changes very quickly from day to day."])))

    # ------------------------------------------------------------------ paths and markers
    paths = {"great_circle": [], "rhumb": []}
    if not (same or near_antipodal):
        paths["great_circle"] = [[round(deg(lon), 6), round(deg(lat), 6)]
                                 for lat, lon in spherical.sample_path(p1, l1, p2, l2, delta, K.PATH_SAMPLES)]
    if rh is not None:
        paths["rhumb"] = [[round(deg(lon), 6), round(deg(lat), 6)]
                          for lat, lon in rhumb.sample_rhumb(p1, l1, rh, K.PATH_SAMPLES)]

    def pt(p):
        return None if p is None else {"lat": round(deg(p[0]), 6), "lon": round(deg(p[1]), 6)}

    markers = {"midpoint": pt(mid), "vertex": pt(vertex_marker),
               "antipode_a": pt(ant_a), "antipode_b": pt(ant_b),
               "crossings": [{"id": c["id"], "label": c["label"], "lat": round(deg(c["lat"]), 6),
                              "lon": round(deg(c["lon"]), 6), "km_from_a": round(c["km"], 3),
                              "fraction": round(c["fraction"], 6),
                              "course_deg": None if c["course"] is None else round(deg(c["course"]), 3)}
                             for c in cross_found]}
    metrics.sort(key=lambda m: ORDER.index(m["id"]))
    return {"a": {"lat": a_lat, "lon": a_lon}, "b": {"lat": b_lat, "lon": b_lon},
            "warnings": warnings, "paths": paths, "markers": markers, "metrics": metrics}
