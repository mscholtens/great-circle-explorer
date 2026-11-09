"""Assembles all metrics (value, display, step-by-step explanation) for a pair of points.

Every explanation step is built from the very same intermediate values the result was computed
from. Angles are radians inside the geo functions; this module converts at the boundary.
"""
import datetime as dt
import math

from . import constants as K
from . import timezones
from .explain import (const, explanation, fmt_dist, fmt_speed, hm, hms, latlon_text, offset_text, sig, space_thousands, step,
                      td, tn, tp, utc_hm)
from .geo import crossings, ellipsoid, mercator, moon, rhumb, spherical, sun, travel

deg = math.degrees
rad = math.radians

C_R = const("R", f"{K.R_KM} km", "mean Earth radius (IUGG)")
LABEL_COURSE_1 = "Course after take-off (initial bearing)"
LABEL_COURSE_2 = "Course before landing (final bearing)"

# Panel order of the metrics (the course cards sit in the Travel group, right after the flight time).
# "destination" and "return_trip" only appear when their options are set.
ORDER = ["distance_haversine", "distance_analysis", "ellipsoid_vincenty", "ellipsoid_lambert", "mercator_distortion", "midpoint", "vertex_latitude",
         "crossings", "rhumb_line", "rhumb_vs_great_circle", "antipodes", "earth_scale", "destination",
         "chord_and_bulge", "gravity_train", "flight_time", "bearing_initial", "bearing_final", "return_trip",
         "latency", "travel_times", "horizon_los", "solar_offset", "timezone_diff", "sun_a", "sun_b", "moon_phase"]

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


def _metric(mid, group, label, value, unit, display, secondary, expl, table=None, analysis=None):
    m = {"id": mid, "group": group, "label": label, "value": value, "unit": unit,
         "display": display, "secondary": secondary or [], "explanation": expl}
    if table is not None:
        m["table"] = table
    if analysis is not None:
        m["analysis"] = analysis
    return m


def _undefined(mid, group, label, reason, why, notes=None):
    """A metric that cannot be computed: display = short reason, one explanatory step."""
    return _metric(mid, group, label, None, None, reason, [],
                   explanation(why, [step("Why this is undefined", None, None, why)], [], notes or []))


def _detour_text(d_km, unit, cruise_kmh):
    """What real flights typically add to the great-circle distance (Dobruszkes & Peeters, 2019), for this route's class."""
    limit_short, limit_medium = K.FLIGHT_DETOUR_LIMITS_KM
    cls = "short" if d_km <= limit_short else "medium" if d_km <= limit_medium else "long"
    names = {"short": "short haul", "medium": "medium haul", "long": "long haul"}
    pct = K.FLIGHT_DETOUR_PCT[cls]
    flown = d_km * (1.0 + pct / 100.0)
    p = K.FLIGHT_DETOUR_PCT

    def n(x):
        return space_thousands(x)
    return (f"Real flights follow airways, winds and airspace restrictions and are longer than the great circle: on average +{p['all']:g} %, "
            f"but +{p['short']:g} % up to {n(limit_short)} km, +{p['medium']:g} % for {n(limit_short + 1)}–{n(limit_medium)} km and +{p['long']:g} % above {n(limit_medium)} km "
            f"(Dobruszkes & Peeters, 2019: {n(K.FLIGHT_DETOUR_SAMPLE)} flights, weighted by distance; a conservative estimate). "
            f"For this route ({names[cls]}) that would be about {fmt_dist(flown, unit)} flown, roughly {hm((flown - d_km) / cruise_kmh)} more at {fmt_speed(cruise_kmh, unit)}.")


def _angle_forms(theta_deg):
    """Two extra steps for a course: in radians, and as an hour angle (15 degrees = 1 hour)."""
    theta_rad = rad(theta_deg)
    hours = theta_deg / K.EARTH_ROTATION_DEG_PER_H
    return [
        step("In radians", r"\theta_{\text{rad}} = \theta^{\circ}\cdot\frac{\pi}{180^{\circ}}",
             rf"\theta_{{\text{{rad}}}} = {tn(theta_deg)}^{{\circ}}\cdot\frac{{\pi}}{{180^{{\circ}}}}", f"{sig(theta_rad)} rad"),
        step("As an hour angle (the Earth turns 15° per hour)", r"t = \frac{\theta^{\circ}}{15^{\circ}/\text{h}}",
             rf"t = \frac{{{tn(theta_deg)}^{{\circ}}}}{{15^{{\circ}}/\text{{h}}}}", f"{sig(hours)} h = {hms(hours)}"),
    ]


ANGLE_NOTE = ("Radians and the hour angle are only other units for the same angle. 15° ↔ 1 h comes from the Earth turning 360° in 24 h, "
              "the same conversion used for longitude and solar time. An hour angle is not a travel time.")
C_ROT = const("ω", f"{K.EARTH_ROTATION_DEG_PER_H:g}°/h", "Earth's rotation rate (360° in 24 h)")


def destination_point(a_lat, a_lon, bearing_deg, km):
    """Point reached from A (degrees) after km on a true bearing (degrees): the direct problem, in degrees."""
    lat, lon = spherical.destination(rad(a_lat), rad(a_lon), rad(bearing_deg), km / K.R_KM)
    return round(deg(lat), 6), round(deg(lon), 6)


def _add_unit_info(m, items, unit):
    """For a card shown in mi or nm: append the conversion step and a note; the calculation itself stays in km."""
    u = K.UNITS[unit]
    f = u["km_per_unit"]
    if items:
        parts, tex = [], []
        for kind, v in items:
            src, dst = ("km", u["label"]) if kind == "dist" else ("km/h", u["speed_label"])
            parts.append(f"{sig(v)} {src} = {sig(v / f)} {dst}")
            tex.append(rf"\frac{{{tn(v)}}}{{{tn(f, 7)}}} = {tn(v / f)}")
        m["explanation"]["steps"].append(step(
            f"Convert to {u['label']} for the card",
            rf"x_{{\text{{{u['label']}}}}} = \frac{{x_{{\text{{km}}}}}}{{k}},\qquad k = {tn(f, 7)}\ \text{{km per {u['label']}}}",
            r",\quad ".join(tex), "; ".join(parts)))
    m["explanation"]["notes"].append(
        f"Calculations are done in km. The card shows {u['label']} (speeds in {u['speed_label']}); 1 {u['label']} = {f} km.")


def calculate(a_lat, a_lon, b_lat, b_lon, cruise_kmh=None, climb_descent_min=None, taxi_min=None, day=None,
              height_a_m=None, height_b_m=None, project_bearing_deg=None, project_km=None,
              include_return=False, circle_km=None, units=None):
    """Compute everything for points A, B given in degrees. Returns the /api/calculate payload (dict)."""
    cruise_kmh = K.CRUISE_KMH_DEFAULT if cruise_kmh is None else cruise_kmh
    climb_descent_min = K.CLIMB_DESCENT_MIN_DEFAULT if climb_descent_min is None else climb_descent_min
    taxi_min = K.TAXI_MIN_DEFAULT if taxi_min is None else taxi_min
    day = day or dt.date.today()
    unit = units or "km"
    fu = K.UNITS[unit]["km_per_unit"]
    ulabel = K.UNITS[unit]["label"]
    unit_conv = {}        # metric id -> [("dist"|"speed", value in km or km/h)] shown converted on the card
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

    # Vincenty's inverse formula: the reference distance (WGS84). None if it does not converge (nearly antipodal points).
    vin = None if same else ellipsoid.vincenty_inverse(p1, l1, p2, l2, K.WGS84_A_KM, K.WGS84_F,
                                                        K.VINCENTY_TOLERANCE, K.VINCENTY_MAX_ITERATIONS)
    if vin is None and not same and not antipodal:
        warnings.append("Vincenty's formula does not converge for nearly antipodal points; Lambert is used as the reference, "
                        "and its accuracy is reduced here as well.")
    vin_km = None if vin is None else vin["dist"]

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
    if vin_km is not None:
        conv_pct = (d_km - vin_km) / vin_km * 100.0
        conventional_line = (f"the conventional method · vs ellipsoid (Vincenty) {'+' if conv_pct >= 0 else '−'}{fmt_dist(abs(d_km - vin_km), unit)} "
                             f"({'+' if conv_pct >= 0 else '−'}{abs(conv_pct):.2f} %) · typically within {K.SPHERE_ERROR_TYPICAL_PCT:g} %, at most about {K.SPHERE_ERROR_MAX_PCT:g} %")
    else:
        conventional_line = f"the conventional method · typically within {K.SPHERE_ERROR_TYPICAL_PCT:g} % of the ellipsoid distance, at most about {K.SPHERE_ERROR_MAX_PCT:g} %"
    notes = ["Spherical model; the real Earth is slightly flattened. Compared with the exact WGS84 distance the spherical one is typically within 0.2% and at most about 0.5% off (longer or shorter depending on latitude and direction) — see the ellipsoid metric. Latitudes are used as if they were latitudes on a sphere.",
             "The law of cosines is numerically worse for very small distances (acos near 1 loses precision), "
             "which is why haversine is the primary method."]
    if antipodal:
        notes.append("Antipodal points: the distance is exactly half a great circle, πR.")
    metrics.append(_metric(
        "distance_haversine", "Geometry", "Great-circle distance", d_km, "km",
        fmt_dist(d_km, unit), [fmt_dist(d_km, u) for u in K.UNIT_ORDER if u != unit] + [conventional_line],
        explanation("Shortest path along the surface of a sphere, via the haversine formula.", steps, [C_R], notes)))
    unit_conv["distance_haversine"] = [("dist", d_km)]

    # ------------------------------------------------------------------ ellipsoid_vincenty
    if same:
        metrics.append(_undefined("ellipsoid_vincenty", "Geometry", "Ellipsoid distance, Vincenty (reference)", "undefined",
                                  "Identical points: the distance is 0."))
    elif vin is None:
        why = ("Antipodal points are joined by infinitely many shortest paths, so there is no unique ellipsoid distance."
               if antipodal else
               f"Vincenty's iteration did not converge within {K.VINCENTY_MAX_ITERATIONS} rounds. This happens for nearly antipodal points. "
               "Lambert's formula is used as the reference instead, but its accuracy is reduced here as well.")
        metrics.append(_undefined("ellipsoid_vincenty", "Geometry", "Ellipsoid distance, Vincenty (reference)", "no convergence" if not antipodal else "undefined", why))
    else:
        log = vin["log"]
        shown = list(enumerate(log, 1))
        hidden = 0
        if len(shown) > 12:
            hidden = len(shown) - 12
            shown = shown[:10] + shown[-2:]
        steps = [step("Reduced latitudes and longitude difference",
                      r"U = \arctan\!\big((1-f)\tan\varphi\big),\qquad L = \lambda_2-\lambda_1,\qquad \lambda_0 = L",
                      rf"U_1 = {tn(vin['U1'])},\quad U_2 = {tn(vin['U2'])},\quad L = {tn(vin['L'])}",
                      f"U₁ = {sig(vin['U1'])} rad, U₂ = {sig(vin['U2'])} rad, L = {sig(vin['L'])} rad")]
        for k, e in shown:
            if hidden and k == shown[10][0]:
                steps.append(step(f"… {hidden} more rounds …", None, None, f"rounds 11 to {len(log) - 2} are not shown; the iteration keeps converging"))
            first = k == 1
            steps.append(step(
                f"Round {k}: improve λ",
                (r"\begin{aligned}\sin\sigma&=\sqrt{(\cos U_2\sin\lambda)^2+(\cos U_1\sin U_2-\sin U_1\cos U_2\cos\lambda)^2},\quad \cos\sigma=\sin U_1\sin U_2+\cos U_1\cos U_2\cos\lambda\\"
                 r"\sin\alpha&=\frac{\cos U_1\cos U_2\sin\lambda}{\sin\sigma},\quad \cos 2\sigma_m=\cos\sigma-\frac{2\sin U_1\sin U_2}{\cos^2\alpha},\quad C=\frac{f}{16}\cos^2\alpha\,\bigl(4+f(4-3\cos^2\alpha)\bigr)\\"
                 r"\lambda_{k}&=L+(1-C)\,f\sin\alpha\,\Bigl(\sigma+C\sin\sigma\bigl(\cos 2\sigma_m+C\cos\sigma(-1+2\cos^2 2\sigma_m)\bigr)\Bigr)\end{aligned}") if first else None,
                rf"\sigma = {tn(e['sigma'], 9)},\ \cos^2\alpha = {tn(e['cos2_alpha'], 9)},\ \cos 2\sigma_m = {tn(e['cos_2sigma_m'], 9)},\ C = {tn(e['C'], 6)}\ \Rightarrow\ \lambda = {tn(e['new_lam'], 12)}",
                f"λ = {e['lam']:.12f} → {e['new_lam']:.12f} (change {abs(e['new_lam'] - e['lam']):.1e})"))
        steps += [
            step("Converged: the change of λ is below the tolerance", r"|\lambda_k-\lambda_{k-1}| < 10^{-12}", None,
                 f"after {vin['iterations']} round{'s' if vin['iterations'] != 1 else ''}"),
            step("Series coefficients",
                 r"u^2=\frac{\cos^2\alpha\,(a^2-b^2)}{b^2},\quad A=1+\frac{u^2}{16384}\bigl(4096+u^2(-768+u^2(320-175u^2))\bigr),\quad B=\frac{u^2}{1024}\bigl(256+u^2(-128+u^2(74-47u^2))\bigr)",
                 rf"u^2 = {tn(vin['u2'], 8)},\quad A = {tn(vin['A'], 10)},\quad B = {tn(vin['B'], 8)}",
                 f"u² = {sig(vin['u2'], 7)}, A = {sig(vin['A'], 10)}, B = {sig(vin['B'], 7)}"),
            step("Correction to the angular distance",
                 r"\Delta\sigma = B\sin\sigma\Bigl(\cos 2\sigma_m+\tfrac{B}{4}\bigl(\cos\sigma(-1+2\cos^2 2\sigma_m)-\tfrac{B}{6}\cos 2\sigma_m(-3+4\sin^2\sigma)(-3+4\cos^2 2\sigma_m)\bigr)\Bigr)",
                 rf"\sigma = {tn(vin['sigma'], 10)},\quad \Delta\sigma = {tn(vin['delta_sigma'], 8)}", f"σ = {sig(vin['sigma'], 10)} rad, Δσ = {sig(vin['delta_sigma'], 6)} rad"),
            step("Distance on the ellipsoid", r"s = b\,A\,(\sigma-\Delta\sigma),\qquad b = a(1-f)",
                 rf"s = {tn(vin['b'], 9)}\ \text{{km}}\cdot {tn(vin['A'], 10)}\cdot ({tn(vin['sigma'], 10)}-{tn(vin['delta_sigma'], 8)})", f"{sig(vin['dist'], 9)} km"),
            step("Difference to the spherical result", r"\Delta d = s - d_{\text{sphere}}", rf"\Delta d = {tn(vin['dist'])} - {tn(d_km)}",
                 f"{sig(d_km - vin['dist'], 4)} km sphere − ellipsoid ({(d_km - vin['dist']) / vin['dist'] * 100:+.3f} % of the ellipsoid distance)"),
        ]
        vdiff = vin["dist"] - d_km
        vpct = vdiff / d_km * 100.0
        metrics.append(_metric(
            "ellipsoid_vincenty", "Geometry", "Ellipsoid distance, Vincenty (reference)", vin["dist"], "km", fmt_dist(vin["dist"], unit),
            ["the reference: closest to reality here", f"{vin['iterations']} iteration{'s' if vin['iterations'] != 1 else ''}",
             f"{vdiff / fu:+,.1f} {ulabel} vs great circle ({vpct:+.2f} %)".replace(",", " ").replace("-", "−")],
            explanation("The shortest distance over the WGS84 ellipsoid, found with Vincenty's iterative inverse formula.", steps,
                        [const("a", f"{K.WGS84_A_KM} km", "WGS84 equatorial radius"), const("f", "1/298.257223563", "WGS84 flattening"),
                         const("b", f"{K.WGS84_B_KM:.6f} km", "polar radius b = a(1 − f)"),
                         const("tolerance", f"{K.VINCENTY_TOLERANCE:g} rad", "the iteration stops when λ changes less than this")],
                        ["Vincenty's formula (1975) finds the geodesic on the ellipsoid by repeating one calculation until λ settles. Wherever it converges it agrees with Karney's algorithm (the more robust method used by GeographicLib) to about 0.1 mm.",
                         "It does not converge for nearly antipodal points (within a few degrees of the opposite side of the Earth); then this card says so and Lambert's formula is used as the reference, with reduced accuracy.",
                         "The ellipsoid is still a model: the geoid (mean sea level) differs from it by up to about 100 m in height, which changes the distance by a few metres at most, and terrain is ignored."])))
        unit_conv["ellipsoid_vincenty"] = [("dist", vin["dist"])]

    # ------------------------------------------------------------------ ellipsoid_lambert
    lam = None if (same or antipodal) else ellipsoid.lambert_distance(p1, l1, p2, l2, K.WGS84_A_KM, K.WGS84_F)
    consts_wgs = [const("a", f"{K.WGS84_A_KM} km", "WGS84 equatorial radius"),
                  const("f", "1/298.257223563", "WGS84 flattening")]
    if lam is None:
        metrics.append(_undefined("ellipsoid_lambert", "Geometry", "Ellipsoid distance, Lambert (approximation)", "undefined",
                                  "Lambert's formula divides by sin²(σ/2) and cos²(σ/2), so it breaks down for identical "
                                  "and for antipodal points."))
    else:
        diff = lam["dist"] - d_km
        pct = diff / d_km * 100.0
        lambert_tier = next((text for limit, text in K.LAMBERT_ERROR_TIERS if deg(delta) >= limit), None)
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
        ] + ([step("Difference to Vincenty's result (the reference)", r"\Delta d_{\text{Lambert}} = d_{\text{Lambert}} - s_{\text{Vincenty}}",
                   rf"\Delta d = {tn(lam['dist'], 9)} - {tn(vin_km, 9)}", f"{(lam['dist'] - vin_km) * 1000.0:+.1f} m".replace("-", "−"))] if vin_km is not None else [])
        metrics.append(_metric(
            "ellipsoid_lambert", "Geometry", "Ellipsoid distance, Lambert (approximation)", lam["dist"], "km",
            fmt_dist(lam["dist"], unit),
            [f"{diff / fu:+,.1f} {ulabel} vs sphere".replace(",", "\u00a0").replace("-", "−"), f"{pct:+.2f} %".replace("-", "−")]
            + ([f"{(lam['dist'] - vin_km) * 1000.0:+,.1f} m vs Vincenty".replace(",", "\u00a0").replace("-", "−")] if vin_km is not None else [])
            + ([f"almost antipodal ({deg(delta):.1f}°): Lambert's formula may be off by {lambert_tier}"] if lambert_tier else []),
            explanation("Lambert's formula gives the distance on the WGS84 ellipsoid using only sines and cosines: an approximation of Vincenty's result.",
                        steps, consts_wgs + [C_R],
                        ["Lambert's formula is an approximation: against the exact geodesic the error is typically about 10 m and rarely above 100 m, but it grows when the two points are nearly opposite each other on the Earth: about 0.6 km at 170° apart, 2.5 km at 177°, and tens of km within 2° of the antipode (the formula is undefined at exactly 180°). It is good enough for comparing with the sphere. The latitudes are treated as geodetic WGS84 latitudes.",
                         "The sphere uses the mean radius, so the difference can be positive or negative depending on latitude and direction."]
                        + ([f"This pair is almost antipodal ({deg(delta):.1f}° apart): Lambert's formula loses accuracy there and may be off by {lambert_tier}. Below about 170° the error is typically about 10 m."] if lambert_tier else []))))
        unit_conv["ellipsoid_lambert"] = [("dist", lam["dist"]), ("dist", diff)]

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
            fmt_dist(flat_km, unit),
            [f"{ratio:.2f}× the real distance", f"scale at A ×{sf1:.2f}, at B ×{sf2:.2f}"],
            explanation("A ruler laid on a Mercator map overstates distances away from the equator.", steps, [C_R],
                        ["Mercator preserves angles, not distances: lengths are stretched by sec φ at latitude φ.",
                         "The straight line on the flat map is a rhumb-like path, not the shortest route; the real great circle is shorter."])))
        unit_conv["mercator_distortion"] = [("dist", flat_km)]

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
        ] + _angle_forms(deg(th1))
        metrics.append(_metric(
            "bearing_initial", "Travel", LABEL_COURSE_1, deg(th1), "°",
            f"{deg(th1):.1f}°", [_compass(th1), "azimuth at A, 0° = true north", f"{th1:.4f} rad · hour angle {hm(deg(th1) / K.EARTH_ROTATION_DEG_PER_H)}"],
            explanation("The azimuth (clockwise from north) to fly after take-off from A, along the great circle towards B.", steps, [C_ROT],
                        ["This is the true azimuth, measured from true north; magnetic variation is not applied. It is calculated on a sphere: on the real (WGS84) Earth the azimuth is typically within 0.2° of this value, and in rare cases (near the poles, almost antipodal points) off by more.",
                         "It is the direction of the shortest route at the coordinates of A. Runway positions and headings and the departure procedure are not known to this app (no information about the runways is assumed), so the actual heading right after take-off differs while the aircraft turns onto the route.",
                         "On a great circle the course changes continuously along the way, which is why the course before landing is different.",
                         ANGLE_NOTE])))
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
        steps += _angle_forms(deg(th_f))
        metrics.append(_metric(
            "bearing_final", "Travel", LABEL_COURSE_2, deg(th_f), "°",
            f"{deg(th_f):.1f}°", [_compass(th_f), f"course changes by {abs(change):.1f}° to the {'left' if change < 0 else 'right'} over the route",
                                  f"{th_f:.4f} rad · hour angle {hm(deg(th_f) / K.EARTH_ROTATION_DEG_PER_H)}"],
            explanation("The azimuth (clockwise from north) flown immediately before landing at B.", steps, [C_ROT],
                        ["Final course = the initial course of the reverse trip (B → A), turned by 180°.",
                         "True azimuth from true north; magnetic variation is not applied.",
                         "It is the direction of the great circle at the coordinates of B. Without information about the runways, the final approach and the runway heading are not modelled.",
                         ANGLE_NOTE])))

    # ------------------------------------------------------------------ return_trip (optional)
    if include_return:
        if th1 is None:
            metrics.append(_undefined("return_trip", "Travel", "Return trip (B → A)", "undefined", bearing_why))
        else:
            th_ba_final = spherical.final_bearing(p2, l2, p1, l1)
            rel_final = (deg(th1) + 180.0) % 360.0
            rel_initial = (deg(th_f) + 180.0) % 360.0
            diff_final = abs((deg(th_ba_final) - rel_final + 180.0) % 360.0 - 180.0)
            diff_initial = abs((deg(th_back) - rel_initial + 180.0) % 360.0 - 180.0)
            steps = [
                step("Course after take-off from B (initial bearing B → A)",
                     r"\theta_{BA} = \operatorname{atan2}\!\big(\sin\Delta\lambda'\cos\varphi_1,\ \cos\varphi_2\sin\varphi_1-\sin\varphi_2\cos\varphi_1\cos\Delta\lambda'\big),\quad \Delta\lambda'=\lambda_1-\lambda_2",
                     None, f"{sig(deg(th_back))}° ({_compass(th_back)})"),
                step("Course before landing at A (final bearing B → A)",
                     r"\theta^{BA}_{\text{final}} = (\theta^{AB}_{\text{initial}}+180^{\circ}) \bmod 360^{\circ}",
                     rf"\theta^{{BA}}_{{\text{{final}}}} = ({tn(deg(th1))}^{{\circ}}+180^{{\circ}}) \bmod 360^{{\circ}}",
                     f"{sig(deg(th_ba_final))}° ({_compass(th_ba_final)}); direct calculation differs by {sig(diff_final, 2)}°"),
                step("Consistency check: the outbound course before landing, turned around, is the return take-off course",
                     r"\theta^{BA}_{\text{initial}} = (\theta^{AB}_{\text{final}}+180^{\circ}) \bmod 360^{\circ}",
                     rf"({tn(deg(th_f))}^{{\circ}}+180^{{\circ}}) \bmod 360^{{\circ}} = {tn(rel_initial)}^{{\circ}}",
                     f"{sig(deg(th_back))}° from the formula above, difference {sig(diff_initial, 2)}°"),
                step("Flight time", r"t_{BA} = t_{AB}", None,
                     f"{hm(airborne_h)} in the air, gate to gate {hm(gate_h)}: same distance, same speed, no wind"),
            ]
            metrics.append(_metric(
                "return_trip", "Travel", "Return trip (B → A)", deg(th_back), "°",
                f"{deg(th_back):.1f}° → {deg(th_ba_final):.1f}°",
                [f"take-off from B {_compass(th_back)}, landing at A {_compass(th_ba_final)}",
                 f"{hm(airborne_h)} in the air, same as the outbound flight"],
                explanation("The same great circle flown the other way: the courses are not simply the outbound ones turned by 180°, "
                            "because the course changes along the route. The flight time is the same.", steps, [],
                            ["Take-off course from B = outbound course before landing + 180°; landing course at A = outbound take-off course + 180°.",
                             "With real winds the two directions differ (the jet stream blows west to east), so the return flight from east to west is usually slower.",
                             "True azimuths from true north; runway headings and procedures are not modelled."])))

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
                  "display": f"{where(c)} · {fmt_dist(c['km'], unit)}"} for c in cross_found]
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
        unit_conv["crossings"] = []

    # ------------------------------------------------------------------ rhumb_line
    rh = None
    rhumb_ok = not (pole_a or pole_b or same)
    if pole_a or pole_b:
        metrics.append(_undefined("rhumb_line", "Geometry", "Rhumb line (constant bearing)", "undefined",
                                  "The stretched latitude ψ = ln tan(π/4 + φ/2) is infinite at a pole, so the rhumb line is undefined there."))
    elif same:
        metrics.append(_metric("rhumb_line", "Geometry", "Rhumb line (constant bearing)", 0.0, "km", f"0 {ulabel}", [],
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
            fmt_dist(rh_km, unit),
            [f"bearing {deg(rh['theta']):.1f}° ({_compass(rh['theta'])})", f"+{fmt_dist(extra, unit)} (+{extra_pct:.2f} %)".replace("+-", "−")],
            explanation("A path that keeps one constant compass bearing: easy to steer, but longer than the great circle.",
                        steps, [C_R],
                        ["A rhumb line is a straight line on a Mercator map.",
                         "Along the equator or a meridian the rhumb line and the great circle coincide."])))
        unit_conv["rhumb_line"] = [("dist", rh_km), ("dist", extra)]

    # ------------------------------------------------------------------ rhumb_vs_great_circle
    path_sep_km, path_sep_line = None, None
    if rh is None:
        metrics.append(_undefined("rhumb_vs_great_circle", "Geometry", "Great circle vs rhumb line", "undefined",
                                  "There is no rhumb line for identical points or when a pole is involved (see the rhumb-line metric)."))
    else:
        rh_km = R * rh["dist"]
        extra = max(0.0, rh_km - d_km)
        extra = 0.0 if extra < 1e-9 else extra
        extra_pct = extra / d_km * 100.0 if d_km > 0 else 0.0
        extra_h = extra / cruise_kmh
        steps = [
            step("Both distances", r"d_{\text{gc}} = R\,\delta,\qquad d_{\text{rhumb}} = R\sqrt{\Delta\varphi^2+q^2\Delta\lambda^2}",
                 rf"d_{{\text{{gc}}}} = {tn(d_km)}\ \text{{km}},\qquad d_{{\text{{rhumb}}}} = {tn(rh_km)}\ \text{{km}}",
                 f"great circle {sig(d_km)} km, rhumb line {sig(rh_km)} km"),
            step("Extra distance of the constant-bearing path", r"\Delta d = d_{\text{rhumb}}-d_{\text{gc}},\qquad \Delta d\,\% = 100\,\Delta d/d_{\text{gc}}",
                 rf"\Delta d = {tn(rh_km)}-{tn(d_km)} = {tn(extra)}\ \text{{km}},\qquad \Delta d\,\% = \frac{{100\cdot {tn(extra)}}}{{{tn(d_km)}}}",
                 f"{sig(extra)} km ({sig(extra_pct, 3)} %)"),
            step("Extra flying time at the cruise speed", r"\Delta t = \frac{\Delta d}{v}",
                 rf"\Delta t = \frac{{{tn(extra)}\ \text{{km}}}}{{{tn(cruise_kmh)}\ \text{{km/h}}}}", f"{sig(extra_h)} h = {hm(extra_h)}"),
        ]
        if not (same or near_antipodal):
            gc_pts = spherical.sample_path(p1, l1, p2, l2, delta, K.SEPARATION_GC_SAMPLES)
            rh_pts = rhumb.sample_rhumb(p1, l1, rh, K.SEPARATION_RHUMB_SAMPLES)
            sep, sep_gc, sep_rh = spherical.max_separation(gc_pts, rh_pts)
            path_sep_km = R * sep
            if path_sep_km >= 1.0:
                sep_round = round(path_sep_km / 10.0) * 10.0 if path_sep_km >= 100 else round(path_sep_km)
                steps.append(step(
                    "How far apart are the two paths?",
                    r"s_{\max} = R\cdot\max_i\ \min_j\ \angle(\mathbf{G}_i,\ \mathbf{R}_j)",
                    rf"\text{{{K.SEPARATION_GC_SAMPLES} points }}\mathbf{{G}}_i\text{{ on the great circle, {K.SEPARATION_RHUMB_SAMPLES} points }}\mathbf{{R}}_j\text{{ on the rhumb line}}",
                    f"up to {fmt_dist(path_sep_km, unit)}, where the great circle is at {latlon_text(deg(sep_gc[0]), deg(spherical.wrap_pi(sep_gc[1])), 2)} "
                    f"and the nearest point of the rhumb line at {latlon_text(deg(sep_rh[0]), deg(spherical.wrap_pi(sep_rh[1])), 2)}"))
                path_sep_line = (f"the two paths are up to about {fmt_dist(sep_round, unit)} apart "
                                 f"(near {latlon_text(deg(sep_gc[0]), deg(spherical.wrap_pi(sep_gc[1])), 1)})")
        rh_bearing = deg(rh["theta"]) % 360.0
        if bearings_ok:
            d_start = (rh_bearing - deg(th1) + 180.0) % 360.0 - 180.0
            d_end = (rh_bearing - deg(th_f) + 180.0) % 360.0 - 180.0
            steps.append(step(
                "Constant rhumb bearing compared with the changing great-circle course",
                r"\theta_{\text{rhumb}}-\theta_{\text{initial}},\qquad \theta_{\text{rhumb}}-\theta_{\text{final}}\quad(\text{wrapped to } -180^{\circ}\dots180^{\circ})",
                rf"{tn(rh_bearing)}^{{\circ}}-{tn(deg(th1))}^{{\circ}},\qquad {tn(rh_bearing)}^{{\circ}}-{tn(deg(th_f))}^{{\circ}}",
                f"rhumb {sig(rh_bearing)}°; great circle starts {sig(deg(th1))}° (rhumb {d_start:+.1f}°) and ends {sig(deg(th_f))}° (rhumb {d_end:+.1f}°)"
                .replace("-", "−")))
            course_line = f"rhumb {rh_bearing:.1f}° vs great circle {deg(th1):.1f}° → {deg(th_f):.1f}°"
        else:
            steps.append(step("Constant rhumb bearing", r"\theta_{\text{rhumb}} = \operatorname{atan2}(\Delta\lambda,\ \Delta\psi)", None,
                              f"{sig(rh_bearing)}° (the great-circle courses are undefined for this pair)"))
            course_line = f"rhumb bearing {rh_bearing:.1f}°"
        metrics.append(_metric(
            "rhumb_vs_great_circle", "Geometry", "Great circle vs rhumb line", extra, "km",
            f"+{fmt_dist(extra, unit)}" if extra >= 0.5 else "no difference",
            [f"+{extra_pct:.2f} % longer · +{hm(extra_h)} at {fmt_speed(cruise_kmh, unit)}" if extra >= 0.5 else "the two paths coincide",
             course_line] + ([path_sep_line] if path_sep_line else []),
            explanation("What it costs to keep one constant compass bearing instead of following the great circle.", steps,
                        [C_R, const("v", f"{cruise_kmh:g} km/h", "cruise ground speed (adjustable)")],
                        ["The rhumb line is a straight line on a Mercator map and needs no course changes, which is why sailors used it. The great circle is always the shortest path.",
                         "The difference is zero along the equator and along a meridian, and grows with distance and with latitude, especially for east-west routes far from the equator.",
                         "Time difference uses the cruise speed only (no climb, descent or taxi allowance).",
                         "How far apart the paths are is measured from 48 points of the great circle to the nearest of 720 points of the rhumb line, so it is accurate to about 10 km."])))
        unit_conv["rhumb_vs_great_circle"] = [("dist", extra)]

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

    # ------------------------------------------------------------------ earth_scale
    circumference = 2.0 * math.pi * R
    share = delta / (2.0 * math.pi)
    lap_h = circumference / cruise_kmh
    light_laps = K.C_KM_S / circumference
    steps = [
        step("Central angle (the angle at the Earth's centre between A and B)", r"\delta = \frac{d}{R}",
             rf"\delta = \frac{{{tn(d_km)}\ \text{{km}}}}{{{tn(R)}\ \text{{km}}}}", f"{sig(delta)} rad = {sig(deg(delta))}°"),
        step("Circumference of the Earth (a great circle)", r"C = 2\pi R",
             rf"C = 2\pi\cdot {tn(R)}\ \text{{km}}", f"{sig(circumference)} km"),
        step("Share of the way around the Earth", r"\frac{d}{C} = \frac{\delta}{2\pi}",
             rf"\frac{{{tn(d_km)}}}{{{tn(circumference)}}}", f"{sig(share * 100.0, 4)} % (the largest possible distance is {sig(50.0)} %, to the antipode)"),
    ]
    sec = [f"central angle {deg(delta):.2f}° ({delta:.4f} rad)"]
    if d_km > 0:
        steps.append(step("How many such routes fit around the Earth", r"n = \frac{C}{d}",
                          rf"n = \frac{{{tn(circumference)}}}{{{tn(d_km)}}}", f"{sig(circumference / d_km, 4)}"))
        sec.append(f"{circumference / d_km:.2f} such routes fit around the Earth")
    steps.append(step("Circling the Earth at the cruise speed", r"t = \frac{C}{v}",
                      rf"t = \frac{{{tn(circumference)}\ \text{{km}}}}{{{tn(cruise_kmh)}\ \text{{km/h}}}}", f"{sig(lap_h)} h = {hm(lap_h)}"))
    steps.append(step("Light around the Earth", r"\frac{c}{C}\ \text{laps per second}",
                      rf"\frac{{{tn(K.C_KM_S)}}}{{{tn(circumference)}}}", f"{sig(light_laps, 4)} laps per second"))
    sec.append(f"around the Earth at {fmt_speed(cruise_kmh, unit)}: {hm(lap_h)}")
    unit_conv["earth_scale"] = [("speed", cruise_kmh)]
    metrics.append(_metric(
        "earth_scale", "Geometry", "Scale on the Earth", share * 100.0, "%",
        f"{share * 100.0:.1f} % of the way around", sec,
        explanation("Puts the route in proportion to the whole Earth.", steps,
                    [C_R, const("c", f"{K.C_KM_S} km/s", "speed of light in vacuum"), const("v", f"{cruise_kmh:g} km/h", "cruise ground speed (adjustable)")],
                    ["The central angle is also the angular distance in the formulas: d = R·δ.",
                     "The antipode is at half the circumference (50 %), so no two points are ever more than 50 % apart."])))

    # ------------------------------------------------------------------ destination (optional: direct problem)
    proj_marker, proj_path = None, []
    if project_bearing_deg is not None and project_km is not None:
        th_p, sig_p = rad(project_bearing_deg), project_km / R
        lat_p, lon_p = spherical.destination(p1, l1, th_p, sig_p)
        _, back = spherical.haversine(p1, l1, lat_p, lon_p)
        reduced = sig_p % (2.0 * math.pi)
        expected = min(reduced, 2.0 * math.pi - reduced)
        steps = [
            step("Angular distance", r"\sigma = \frac{d}{R}",
                 rf"\sigma = \frac{{{tn(project_km)}\ \text{{km}}}}{{{tn(R)}\ \text{{km}}}}", f"{sig(sig_p)} rad = {sig(deg(sig_p))}°"),
            step("Latitude of the destination",
                 r"\varphi_2 = \arcsin\!\big(\sin\varphi_1\cos\sigma+\cos\varphi_1\sin\sigma\cos\theta\big)",
                 rf"\varphi_2 = \arcsin\!\big(\sin({tn(p1)})\cos({tn(sig_p)})+\cos({tn(p1)})\sin({tn(sig_p)})\cos({tn(th_p)})\big) = {tn(lat_p)}",
                 f"{sig(deg(lat_p))}°"),
            step("Longitude of the destination",
                 r"\lambda_2 = \lambda_1+\operatorname{atan2}\!\big(\sin\theta\sin\sigma\cos\varphi_1,\ \cos\sigma-\sin\varphi_1\sin\varphi_2\big)",
                 rf"\lambda_2 = {tn(l1)}+\operatorname{{atan2}}\!\big(\sin({tn(th_p)})\sin({tn(sig_p)})\cos({tn(p1)}),\ \cos({tn(sig_p)})-\sin({tn(p1)})\sin({tn(lat_p)})\big)",
                 f"{sig(deg(lon_p))}° (normalized to −180…180)"),
            step("Check: distance from A back to the destination (haversine)", r"d' = R\,\delta'",
                 rf"d' = {tn(R)}\cdot {tn(back)}",
                 f"{sig(R * back)} km; expected {sig(R * expected)} km (difference {sig(abs(R * back - R * expected), 2)} km)"),
        ]
        notes = ["This is the direct geodetic problem: given a start, a true bearing and a distance, find the end point. The metrics for distance and course solve the inverse problem.",
                 "The bearing is a true azimuth (0° = north, clockwise). The path follows the great circle that starts in that direction, so the bearing changes along the way."]
        if sig_p > math.pi:
            notes.append("The distance is longer than half the Earth's circumference: the path passes the antipode of A and comes back, so the destination is closer to A than the distance suggests.")
        if pole_a:
            notes.append("A is at a pole, where every direction is south (or north): the bearing is measured from the meridian of the pole's stored longitude.")
        metrics.append(_metric(
            "destination", "Geometry", "Destination from A", deg(lat_p), "°",
            latlon_text(deg(lat_p), deg(lon_p), 3),
            [f"{fmt_dist(project_km, unit)} from A on bearing {project_bearing_deg:g}° ({_compass(th_p)})"],
            explanation("The point reached from A after travelling the given distance along the great circle that starts on the given bearing.",
                        steps, [C_R], notes)))
        unit_conv["destination"] = [("dist", project_km)]
        n_p = K.PROJECTION_SAMPLES
        pts = [spherical.destination(p1, l1, th_p, sig_p * i / n_p) for i in range(n_p + 1)]
        lons_p = spherical.unwrap_longitudes([q[1] for q in pts])
        proj_path = [[round(deg(lo), 6), round(deg(la), 6)] for (la, _), lo in zip(pts, lons_p)]
        proj_marker = {"lat": round(deg(lat_p), 6), "lon": round(deg(lon_p), 6),
                       "bearing_deg": project_bearing_deg, "km": project_km}

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
        f"{fmt_dist(chord_km, unit)} tunnel", [f"{sig(sag_km / fu, 4)} {ulabel} deep at the middle"],
        explanation("A straight tunnel between A and B is shorter than the surface route and dips below the surface.", steps, [C_R],
                    ["For δ = π (antipodal points) the chord is the diameter 2R and the depth is R."])))
    unit_conv["chord_and_bulge"] = [("dist", chord_km), ("dist", sag_km)]

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
        f"{t_trip / 60.0:.1f} min", [f"top speed {fmt_speed(v_max * 3.6, unit)}"],
        explanation("Fall through the straight tunnel with no friction: the trip takes about 42 minutes, no matter how far apart A and B are.",
                    steps, [const("g", f"{K.G} m/s²", "standard gravity"), C_R],
                    ["Surprising result: a tunnel between neighbouring towns takes the same 42.2 minutes as one through the centre of the Earth.",
                     "Assumes a uniform-density Earth, no friction and no air resistance (the real Earth is denser in the core, which would shorten the trip)."])))
    unit_conv["gravity_train"] = [("speed", v_max * 3.6)]

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
        [f"gate to gate {hm(gate_h)}", f"cruise {hm(cruise_h)} at {fmt_speed(cruise_kmh, unit)} + {climb_descent_min:g} min climb & descent",
         f"{taxi_min:g} min taxiing is not counted as flight time"],
        explanation("The time actually spent in the air from take-off to landing, plus the gate-to-gate time including taxiing.", steps,
                    [const("v", f"{cruise_kmh:g} km/h", "cruise ground speed (adjustable)"),
                     const("t_climb/descent", f"{climb_descent_min:g} min", "extra airborne time for climb and descent (adjustable assumption)"),
                     const("t_taxi", f"{taxi_min:g} min", "taxiing at both airports together (adjustable assumption)")],
                    ["Airborne time runs from take-off to landing; taxiing is excluded. The gate-to-gate time adds the taxi allowance.",
                     "The distance is measured point to point between the two coordinates. Runway positions and lengths, departure and arrival procedures and holding patterns are not known and not modelled.",
                     "Ignores winds (the jet stream can change real times by an hour or more) and airways. The distance is measured at sea level; at cruise altitude the path is about 0.17 % longer.",
                     _detour_text(d_km, unit, cruise_kmh),
                     "The climb/descent and taxi allowances are rough assumptions; change them under Options."])))
    unit_conv["flight_time"] = [("speed", cruise_kmh)]

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
        f"A sees {hz['a'][1] / fu:.1f} {ulabel}, B sees {hz['b'][1] / fu:.1f} {ulabel}",
        [f"airliner at {space_thousands(K.CRUISE_ALTITUDE_M)} m: {fmt_dist(hz['cruise'][1], unit)}",
         "A and B can see each other" if visible else "A and B are hidden behind the curvature"],
        explanation("How far you can see before the curve of the Earth hides the ground.", steps, [C_R],
                    ["Ignores terrain, buildings and atmospheric refraction (which extends the horizon by roughly 8%).",
                     "Heights are adjustable in the panel; the default is eye height of a standing person."])))
    unit_conv["horizon_los"] = [("dist", los_max)]

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
        tz_notes.append(f"A point more than {K.TZ_NEAR_BORDER_KM:g} km outside every zone polygon (open ocean) uses the nominal zone round(longitude/15°) hours.")
    for who, zi in (("A", zi_a), ("B", zi_b)):
        if zi.get("near_km") is not None:
            tz_notes.append(f"Point {who} lies {zi['near_km']:.1f} km outside every zone polygon (a coast, or a gap left by the simplified borders), so the nearest zone ({zi['tzid']}) is used.")
    metrics.append(_metric(
        "timezone_diff", "Sun & time", "Time-zone difference", diff_h, "h",
        (f"{hm(abs(diff_h))} {'ahead' if diff_h > 0 else 'behind'}" if abs(diff_h) > 1e-9 else "same time"),
        [f"A: {zname(zi_a)}", f"B: {zname(zi_b)}", f"{day.isoformat()} · today's rules (tz database {tz_version}); future changes unknown"],
        explanation("How many hours the clocks differ between A and B on the chosen date.", steps, [], tz_notes)))

    # ------------------------------------------------------------------ sun_a / sun_b
    jd_day = day.toordinal() + K.JD_AT_ORDINAL_ZERO_NOON          # Julian date of 12:00 UTC on the chosen date

    def utc_date_of(jd_event):
        return dt.date.fromordinal(int(math.floor(jd_event + 0.5)) - int(K.JD_AT_ORDINAL_ZERO_NOON))

    def event_text(jd_event):
        """'06:41 UTC', with '(previous day)' / '(next day)' when the event falls on another UTC date than the chosen one."""
        hours = ((jd_event - 0.5) % 1.0) * 24.0
        shift = (utc_date_of(jd_event) - day).days
        return utc_hm(hours) + {-1: " (previous day)", 1: " (next day)"}.get(shift, "")

    for key, label, lat_r, lon_r, lon_d in (("sun_a", "Sun at A", p1, l1, a_lon), ("sun_b", "Sun at B", p2, l2, b_lon)):
        s = sun.sun_times(lat_r, lon_r, jd_day, K.SUN_ALTITUDE_DEG)
        pos = s["pos"]
        steps = [
            step("Julian date of local solar noon",
                 r"\mathrm{JD} = \mathrm{JD}_{12\,\mathrm{UTC}} - \frac{\lambda^{\circ}}{360^{\circ}} - \frac{\mathrm{EoT}_0}{1440}",
                 rf"\mathrm{{JD}} = {tn(jd_day, 9)} - \frac{{{tn(lon_d)}}}{{360}} - \frac{{{tn(s['eot_first_min'])}}}{{1440}}",
                 f"{day.isoformat()} → JD {sig(s['jd_noon'], 10)} (EoT₀ is the equation of time found in a first pass)"),
            step("Days since J2000.0", r"n = \mathrm{JD} - 2451545.0",
                 rf"n = {tn(s['jd_noon'], 10)} - 2451545.0", f"n = {sig(pos['n'], 8)} days"),
            step("Mean longitude and mean anomaly of the Sun",
                 r"\begin{aligned}L &= 280.460^{\circ} + 0.9856474^{\circ}\,n\\ g &= 357.528^{\circ} + 0.9856003^{\circ}\,n\end{aligned}\ \ (\bmod 360^{\circ})",
                 rf"\begin{{aligned}}L &= 280.460^{{\circ}} + 0.9856474^{{\circ}}\cdot {tn(pos['n'])} = {tn(pos['L_deg'])}^{{\circ}}\\ g &= 357.528^{{\circ}} + 0.9856003^{{\circ}}\cdot {tn(pos['n'])} = {tn(pos['g_deg'])}^{{\circ}}\end{{aligned}}",
                 f"L = {sig(pos['L_deg'])}°, g = {sig(pos['g_deg'])}°"),
            step("Ecliptic longitude of the Sun (mean longitude plus the equation of centre)",
                 r"\lambda_{\odot} = L + 1.915^{\circ}\sin g + 0.020^{\circ}\sin 2g",
                 rf"\lambda_{{\odot}} = {tn(pos['L_deg'])}^{{\circ}} + 1.915^{{\circ}}\sin({tn(pos['g_deg'])}^{{\circ}}) + 0.020^{{\circ}}\sin(2\cdot {tn(pos['g_deg'])}^{{\circ}})",
                 f"{sig(deg(pos['lam']))}°"),
            step("Obliquity of the ecliptic and declination of the Sun",
                 r"\varepsilon = 23.439^{\circ} - 0.0000004^{\circ}\,n,\qquad \delta_{\odot} = \arcsin(\sin\varepsilon\,\sin\lambda_{\odot})",
                 rf"\varepsilon = {tn(deg(pos['eps']))}^{{\circ}},\qquad \delta_{{\odot}} = \arcsin(\sin({tn(deg(pos['eps']))}^{{\circ}})\sin({tn(deg(pos['lam']))}^{{\circ}}))",
                 f"ε = {sig(deg(pos['eps']))}°, δ = {sig(deg(pos['decl']))}°"),
            step("Equation of time (the difference between sundial time and clock time)",
                 r"\alpha = \operatorname{atan2}(\cos\varepsilon\,\sin\lambda_{\odot},\ \cos\lambda_{\odot}),\qquad \mathrm{EoT} = 4\,\tfrac{\text{min}}{^{\circ}}\,(L - 0.0057183^{\circ} - \alpha)",
                 rf"\alpha = {tn(deg(pos['ra']))}^{{\circ}},\qquad \mathrm{{EoT}} = 4\,(({tn(pos['L_deg'])} - 0.0057183) - ({tn(deg(pos['ra']))}))",
                 f"α = {sig(deg(pos['ra']))}°, EoT = {sig(s['eot_min'])} min"),
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
            steps.append(step("Day length", r"L_{\text{day}} = \frac{2\,\omega_0^{\circ}}{15^{\circ}/\text{h}}",
                              rf"\omega_0 = \arccos({tn(s['cos_w0'])}) = {tn(s['w0_deg'])}^{{\circ}},\quad L_{{\text{{day}}}} = \frac{{2\cdot {tn(s['w0_deg'])}}}{{15}}",
                              f"{sig(s['day_length_h'])} h = {hm(s['day_length_h'])}"))
        steps.append(step("Solar noon (UTC)", r"t_{\text{noon}} = 12 - \frac{\lambda^{\circ}}{15} - \frac{\mathrm{EoT}}{60}",
                          rf"t_{{\text{{noon}}}} = 12 - \frac{{{tn(lon_d)}}}{{15}} - \frac{{{tn(s['eot_min'])}}}{{60}}",
                          f"{sig(s['solar_noon_h'])} h = {utc_hm(s['solar_noon_h'])}"))
        if s["state"] == "normal":
            rise_jd = s["jd_noon"] - s["w0_deg"] / 360.0
            set_jd = s["jd_noon"] + s["w0_deg"] / 360.0
            steps.append(step("Sunrise and sunset (UTC)", r"t_{\text{rise,set}} = t_{\text{noon}} \mp \frac{\omega_0^{\circ}}{15}",
                              rf"t_{{\text{{rise}}}} = {tn(s['solar_noon_h'])} - \frac{{{tn(s['w0_deg'])}}}{{15}},\quad t_{{\text{{set}}}} = {tn(s['solar_noon_h'])} + \frac{{{tn(s['w0_deg'])}}}{{15}}",
                              f"sunrise {event_text(rise_jd)}, sunset {event_text(set_jd)}"))
            disp = hm(s["day_length_h"]) + " of daylight"
            sec = [f"sunrise {event_text(rise_jd)}", f"sunset {event_text(set_jd)}", f"solar noon {event_text(s['jd_noon'])}"]
            if s["day_length_h"] >= K.LONG_DAY_HINT_H:
                sec.append("very long day (near the midnight sun): sunrise and sunset may be off by several minutes, up to about 10")
        else:
            sec.append(f"solar noon {event_text(s['jd_noon'])}")
            sec.append("near the edge of the polar day or night the first and last day can be off by a day")
        metrics.append(_metric(
            key, "Sun & time", label, s["day_length_h"], "h", disp, sec,
            explanation(f"Sunrise, sunset and day length at {'A' if key == 'sun_a' else 'B'} on {day.isoformat()}, from the Sun's position.", steps,
                        [const("h₀", f"{K.SUN_ALTITUDE_DEG}°", "sun altitude at sunrise/sunset (standard refraction + solar disc)"),
                         const("JD(J2000.0)", "2451545.0", "Julian date of 2000-01-01 12:00, the reference moment of the Sun formulas")],
                        ["The Sun's position comes from low-precision formulas (mean longitude, mean anomaly, equation of centre, obliquity): declination good to about 0.005°, equation of time to about 0.1 min, valid for roughly 1950–2050. Sunrise and sunset are then typically within 1–2 minutes of an astronomical program at mid-latitudes.",
                         "Accuracy depends on the length of the day: up to about 8 hours of daylight the difference to an astronomical program is at most about 1 minute, up to 16 hours about 2 minutes, up to 21 hours about 5 minutes, and up to about 10 minutes (rarely 15) for days longer than 21 hours, near the midnight sun. There the day length changes very quickly from day to day, so the day of the first or last midnight sun can be off by a day.",
                         "Refraction is fixed at the standard −0.833° (refraction plus the solar disc). Real refraction depends on weather and temperature; the height of the observer, mountains and buildings are ignored. The Earth is a sphere here.",
                         "The chosen date is the local solar day at the place. All times are UTC clock times and can fall on the previous or the next UTC date (marked), for example sunrise in the Pacific."])))

    # ------------------------------------------------------------------ moon_phase
    t_moon = moon.centuries(jd_day)
    psi, d_moon, lam_m, beta_m, lam_s = moon.elongation(jd_day)
    m_lit = moon.illuminated_fraction(psi)
    m_name = moon.phase_name(d_moon)
    jd_new_next = moon.time_of_phase(jd_day, 0.0)
    jd_full_next = moon.time_of_phase(jd_day, 180.0)
    jd_new_prev = moon.time_of_phase(jd_day, 0.0, forward=False)
    m_age = jd_day - jd_new_prev

    def moon_when(jd_event):
        return f"{utc_date_of(jd_event).isoformat()} about {utc_hm(((jd_event - 0.5) % 1.0) * 24.0)}"

    def terms_tex(terms, first):
        parts = []
        for a, b, c in terms:
            sign = "-" if a < 0 else "+"
            parts.append(rf"{sign}{abs(a):g}^{{\circ}}\sin\!\left({b:g}^{{\circ}}{'-' if c < 0 else '+'}{abs(c):g}^{{\circ}}T\right)")
        text = "".join(parts)
        return text[1:] if first and text.startswith("+") else text

    lon_vals = moon.series_values(moon.LONGITUDE_TERMS, t_moon)
    lat_vals = moon.series_values(moon.LATITUDE_TERMS, t_moon)
    lon_sum = " ".join(f"{v:+.3f}" for v in lon_vals)
    lat_sum = " ".join(f"{v:+.3f}" for v in lat_vals)
    steps = [
        step("Julian centuries since J2000.0", r"T = \frac{\mathrm{JD} - 2451545.0}{36525},\quad \mathrm{JD} = N_{\text{ordinal}} + 1721425\ (12{:}00\ \mathrm{UTC})",
             rf"T = \frac{{{tn(jd_day, 9)} - 2451545.0}}{{36525}}", f"{day.isoformat()} → JD {sig(jd_day, 9)}, T = {sig(t_moon, 6)}"),
        step("Ecliptic longitude of the Moon (a short series of sine terms)",
             rf"\lambda_{{\mathrm{{M}}}} = {moon.LONGITUDE_BASE[0]:g}^{{\circ}} + {moon.LONGITUDE_BASE[1]:g}^{{\circ}}T " + terms_tex(moon.LONGITUDE_TERMS, False),
             rf"\lambda_{{\mathrm{{M}}}} = {moon.LONGITUDE_BASE[0]:g}^{{\circ}} + {tn(moon.LONGITUDE_BASE[1] * t_moon)}^{{\circ}}\ \text{{plus the terms}}\ ({lon_sum})^{{\circ}}",
             f"{sig(deg(lam_m))}°"),
        step("Ecliptic latitude of the Moon", r"\beta_{\mathrm{M}} = " + terms_tex(moon.LATITUDE_TERMS, True),
             rf"\beta_{{\mathrm{{M}}}}\ \text{{with the terms}}\ ({lat_sum})^{{\circ}}", f"{sig(deg(beta_m))}°"),
        step("Ecliptic longitude of the Sun (as in the sunrise calculation)", r"\lambda_{\odot} = L + 1.915^{\circ}\sin g + 0.020^{\circ}\sin 2g",
             None, f"{sig(deg(lam_s))}°"),
        step("Angle between Moon and Sun (elongation)", r"\cos\psi = \cos\beta_{\mathrm{M}}\,\cos(\lambda_{\mathrm{M}} - \lambda_{\odot})",
             rf"\cos\psi = \cos({tn(deg(beta_m))}^{{\circ}})\cos({tn(deg(lam_m))}^{{\circ}} - {tn(deg(lam_s))}^{{\circ}})", f"ψ = {sig(deg(psi))}°"),
        step("Lit fraction of the disc", r"\text{lit} = \frac{1-\cos\psi}{2}", rf"\text{{lit}} = \frac{{1-\cos({tn(deg(psi))}^{{\circ}})}}{{2}}",
             f"{sig(m_lit * 100.0, 3)} %"),
        step("Phase name (the longitude difference is cut into eight parts of 45°)",
             r"D = (\lambda_{\mathrm{M}} - \lambda_{\odot}) \bmod 360^{\circ},\qquad \text{index} = \left\lfloor \frac{D + 22.5^{\circ}}{45^{\circ}} \right\rfloor \bmod 8",
             rf"D = {tn(d_moon)}^{{\circ}}", f"D = {sig(d_moon)}° → {m_name}"),
        step("Age, next new moon and next full moon (found by repeating the calculation until D reaches 0° or 180°)",
             r"t \leftarrow t + \frac{D_{\text{target}} - D(t)}{12.19^{\circ}/\text{day}}",
             None,
             f"{sig(m_age, 3)} days since the last new moon · next new moon {moon_when(jd_new_next)} · next full moon {moon_when(jd_full_next)}"),
    ]
    metrics.append(_metric(
        "moon_phase", "Sun & time", "Moon phase", m_lit * 100.0, "%", f"{m_name} · {m_lit * 100.0:.0f} % lit",
        [f"age {m_age:.1f} days", f"next full moon {moon_when(jd_full_next)}", f"next new moon {moon_when(jd_new_next)}"],
        explanation(f"The phase of the Moon on {day.isoformat()}, from the positions of the Moon and the Sun.", steps,
                    [const("12.19°/day", f"{360.0 / K.SYNODIC_MONTH_DAYS:.2f}°/day", "mean rate at which the Moon gains on the Sun (360° per synodic month); only the starting guess of the search")],
                    ["The Moon's longitude and latitude come from a short series of sine terms (accuracy about 0.3°). The lit fraction is within about 0.3 percentage points of an astronomical program, and the times of new and full moon within about an hour.",
                     "The phase is the same for everyone on Earth on a given day (it only looks mirrored between the hemispheres), so it does not depend on A or B.",
                     "The lit fraction is computed for 12:00 UTC on the chosen date (1970 to 2049). The 'percent lit' ignores the small effect of the Moon's distance; eclipses and the exact libration are not modelled."])))

    # ------------------------------------------------------------------ distance_analysis
    if same:
        metrics.append(_undefined("distance_analysis", "Geometry", "Distance analysis", "undefined",
                                  "Identical points: every way of measuring gives 0, so there is nothing to compare."))
    else:
        by = {m["id"]: m for m in metrics}
        lam_km = by["ellipsoid_lambert"]["value"]
        if vin_km is not None:
            ref_id, ref_label, ref_km = "vincenty", "WGS84 ellipsoid (Vincenty)", vin_km
        elif lam_km is not None:
            ref_id, ref_label, ref_km = "lambert", "WGS84 ellipsoid (Lambert, because Vincenty does not converge here)", lam_km
        else:
            ref_id, ref_label, ref_km = "great_circle_mean", "great circle on the mean-radius sphere", d_km

        def signed(x, f):
            return f"{'+' if x >= 0 else '−'}{f(abs(x))}"

        def pct_text(p, digits=None):
            digits = digits if digits is not None else (3 if abs(p) < 0.01 else 2 if abs(p) < 0.1 else 1)     # tiny differences need more decimals
            return signed(p, lambda v: f"{v:.{digits}f} %")

        def diff_text(km):
            return signed(km, lambda v: f"{v * 1000.0:.0f} m" if v < 1.0 else fmt_dist(v, unit))      # below 1 km: metres

        # -- own calculations (rows that are not an existing metric)
        g_dphi, g_dlam, g_deg = spherical.plate_carree_distance(p1, l1, p2, l2)
        grid_km = K.KM_PER_DEGREE * g_deg
        e_dphi, e_dlam, e_phim, e_angle = spherical.equirectangular_distance(p1, l1, p2, l2)
        short_km = R * e_angle
        chord_ell, ecef_a, ecef_b = ellipsoid.ellipsoid_chord(p1, l1, p2, l2, K.WGS84_A_KM, K.WGS84_F)

        def vs_ref(km):
            return f"{(km - ref_km) / ref_km * 100.0:+.2f} % vs the reference".replace("-", "−")

        def sphere_expl(radius_km, radius_name, why):
            return explanation(
                f"The great-circle distance on a sphere with the {radius_name} radius: the same formula as everywhere else, only the radius differs.",
                [step("Central angle (the same δ for every sphere)", r"\delta = 2\operatorname{atan2}\left(\sqrt{a},\sqrt{1-a}\right)", rf"\delta = {tn(delta)}", f"δ = {sig(delta)} rad"),
                 step(f"Radius: {radius_name}", None, None, why),
                 step("Distance", r"d = R\,\delta", rf"d = {tn(radius_km)}\ \text{{km}}\cdot {tn(delta)}", f"{sig(radius_km * delta)} km ({vs_ref(radius_km * delta)})")],
                [const("R", f"{radius_km:.4f} km", f"{radius_name} radius")],
                ["The shape of the calculation does not change when you pick another sphere; only R does. The three spheres (polar, mean, equatorial) are all 'the Earth' in some sense, and the choice alone moves the answer by about 0.3 %."])
        polar_expl = sphere_expl(K.WGS84_B_KM, "polar", f"b = a(1 − f) = {K.WGS84_B_KM:.4f} km, the distance from the centre to a pole (WGS84).")
        equat_expl = sphere_expl(K.WGS84_A_KM, "equatorial", f"a = {K.WGS84_A_KM} km, the distance from the centre to the equator (WGS84).")
        tunnel_sph = chord_km
        tunnel_expl = explanation(
            "The straight line through the Earth between A and B, with both points on the WGS84 ellipsoid (Earth-centred coordinates).",
            [step("Earth-centred coordinates of each point", r"e^2=f(2-f),\quad N=\frac{a}{\sqrt{1-e^2\sin^2\varphi}},\quad X=N\cos\varphi\cos\lambda,\ Y=N\cos\varphi\sin\lambda,\ Z=N(1-e^2)\sin\varphi",
                  rf"A=({tn(ecef_a[0])},\ {tn(ecef_a[1])},\ {tn(ecef_a[2])})\ \text{{km}},\quad B=({tn(ecef_b[0])},\ {tn(ecef_b[1])},\ {tn(ecef_b[2])})\ \text{{km}}",
                  f"e² = {sig(K.WGS84_E2, 8)}"),
             step("Straight-line distance", r"c = \sqrt{\Delta X^2+\Delta Y^2+\Delta Z^2}",
                  rf"c = \sqrt{{({tn(ecef_b[0] - ecef_a[0])})^2+({tn(ecef_b[1] - ecef_a[1])})^2+({tn(ecef_b[2] - ecef_a[2])})^2}}", f"{sig(chord_ell)} km ({vs_ref(chord_ell)})"),
             step("Compare with the spherical chord", r"c_{\text{sphere}} = 2R\sin\frac{\delta}{2}", rf"c_{{\text{{sphere}}}} = 2\cdot {tn(R)}\cdot\sin\frac{{{tn(delta)}}}{{2}}",
                  f"{sig(tunnel_sph)} km on the sphere, {sig(chord_ell)} km on the ellipsoid: difference {sig(tunnel_sph - chord_ell, 3)} km")],
            [const("a", f"{K.WGS84_A_KM} km", "WGS84 equatorial radius"), const("f", "1/298.257223563", "WGS84 flattening")],
            ["The 'Straight tunnel & bulge' card keeps the spherical chord 2R·sin(δ/2); this row uses the ellipsoid, which is more accurate because the Earth is not round.",
             "The tunnel is not a travel distance: it only shows how much shorter a straight line through the Earth is than any path along the surface."])
        short_expl = explanation(
            "The 'programmer's shortcut': pretend the area around the route is flat, with longitude scaled by the cosine of the mean latitude.",
            [step("Differences and mean latitude (longitude the shorter way around)", r"\Delta\varphi=\varphi_2-\varphi_1,\quad \Delta\lambda\in[-\pi,\pi],\quad \varphi_m=\tfrac{\varphi_1+\varphi_2}{2}",
                  rf"\Delta\varphi = {tn(e_dphi)},\quad \Delta\lambda = {tn(e_dlam)},\quad \varphi_m = {tn(e_phim)}", f"Δφ = {sig(e_dphi)} rad, Δλ = {sig(e_dlam)} rad, φm = {sig(deg(e_phim))}°"),
             step("Distance", r"d = R\sqrt{\Delta\varphi^2+(\Delta\lambda\cos\varphi_m)^2}",
                  rf"d = {tn(R)}\sqrt{{{tp(e_dphi)}^2+({tp(e_dlam)}\cdot\cos({tn(e_phim)}))^2}}", f"{sig(short_km)} km ({vs_ref(short_km)})")],
            [C_R],
            ["Common in games and quick code: fine for short distances, increasingly wrong for long ones.",
             "It differs from the 'degrees as a flat grid' row because it corrects for the meridians converging towards the poles (cos φm), but it still uses one single scale for the whole route."])
        grid_expl = explanation(
            "Read latitude and longitude as flat x/y coordinates in degrees, like graph paper, and use Pythagoras.",
            [step("Differences in degrees (longitude the shorter way around)",
                  r"\Delta\varphi = \varphi_2-\varphi_1,\qquad \Delta\lambda = \lambda_2-\lambda_1\ \ (-180^{\circ}\dots180^{\circ})",
                  rf"\Delta\varphi = {tn(b_lat)}^{{\circ}}-{tp(a_lat)}^{{\circ}} = {tn(g_dphi)}^{{\circ}},\qquad \Delta\lambda = {tn(g_dlam)}^{{\circ}}",
                  f"Δφ = {sig(g_dphi)}°, Δλ = {sig(g_dlam)}°"),
             step("Length of one degree of arc", r"k = \frac{\pi R}{180^{\circ}}", rf"k = \frac{{\pi\cdot {tn(R)}\ \text{{km}}}}{{180}}", f"{sig(K.KM_PER_DEGREE, 6)} km per degree"),
             step("Distance on the grid", r"d_{\text{grid}} = k\sqrt{\Delta\varphi^2+\Delta\lambda^2}",
                  rf"d_{{\text{{grid}}}} = {tn(K.KM_PER_DEGREE)}\sqrt{{{tp(g_dphi)}^2+{tp(g_dlam)}^2}}", f"{sig(grid_km)} km ({vs_ref(grid_km)})"),
             step("Why this misleads", None, None,
                  "A degree of latitude is always 111.2 km, but a degree of longitude is only 111.2·cos(latitude) km: 71 km at 50°, 0 km at the pole. "
                  "The grid ignores this, so east-west distances are overstated away from the equator. Whether the total ends up too long or too short depends on the direction of the line.")],
            [C_R, const("k", f"{K.KM_PER_DEGREE:.3f} km/°", "length of one degree of arc on the sphere")],
            ["This is what you get by treating a latitude/longitude map (the 'plate carrée' projection) like graph paper.",
             "Along the equator and along a meridian it is exact. Elsewhere it can be too long or too short."])

        spec = [
            {"id": "tunnel", "label": "Straight tunnel through the Earth", "short": "straight tunnel", "model": "ellipsoid", "km": chord_ell, "metric_id": None, "own": tunnel_expl,
             "what": "A straight line through the Earth between two points on the ellipsoid (Earth-centred coordinates)", "tex": r"c=\sqrt{\Delta X^2+\Delta Y^2+\Delta Z^2}"},
            {"id": "sphere_polar", "label": "Great circle, polar radius", "short": "great circle (polar radius)", "model": "sphere", "km": K.WGS84_B_KM * delta, "metric_id": None, "own": polar_expl,
             "what": f"The great circle on a sphere with the polar radius b = {K.WGS84_B_KM:.3f} km", "tex": r"d=b\,\delta"},
            {"id": "vincenty", "label": "Ellipsoid, Vincenty", "short": "ellipsoid (Vincenty)", "model": "ellipsoid", "km": vin_km, "metric_id": "ellipsoid_vincenty", "own": None,
             "what": "The shortest path over the WGS84 ellipsoid, by Vincenty's iterative formula", "tex": r"s=b\,A\,(\sigma-\Delta\sigma)"},
            {"id": "lambert", "label": "Ellipsoid, Lambert (approximation)", "short": "ellipsoid (Lambert)", "model": "ellipsoid", "km": lam_km, "metric_id": "ellipsoid_lambert", "own": None,
             "what": "An approximation of the ellipsoid distance with sines and cosines only", "tex": r"d = a\left(\sigma-\tfrac{f}{2}(X+Y)\right)"},
            {"id": "great_circle_mean", "label": "Great circle, mean radius", "short": "great circle", "model": "sphere", "km": d_km, "metric_id": "distance_haversine", "own": None,
             "what": "The standard, conventional method: the shortest path over a sphere of mean radius R = 6371.0088 km", "tex": r"d=R\,\delta"},
            {"id": "sphere_equatorial", "label": "Great circle, equatorial radius", "short": "great circle (equatorial radius)", "model": "sphere", "km": K.WGS84_A_KM * delta, "metric_id": None, "own": equat_expl,
             "what": f"The great circle on a sphere with the equatorial radius a = {K.WGS84_A_KM} km", "tex": r"d=a\,\delta"},
            {"id": "rhumb", "label": "Rhumb line", "short": "rhumb line", "model": "sphere", "km": by["rhumb_line"]["value"], "metric_id": "rhumb_line", "own": None, "method": True,
             "what": "The path that keeps one constant compass bearing (a straight line on a Mercator map)", "tex": r"d_{\text{rhumb}} = R\sqrt{\Delta\varphi^2+q^2\Delta\lambda^2}"},
            {"id": "shortcut", "label": "Programmer's shortcut", "short": "programmer's shortcut", "model": "sphere", "km": short_km, "metric_id": None, "own": short_expl, "method": True,
             "what": "Equirectangular approximation: a flat map with longitude scaled by cos(mean latitude)", "tex": r"d = R\sqrt{\Delta\varphi^2+(\Delta\lambda\cos\varphi_m)^2}"},
            {"id": "grid", "label": "Degrees as a flat grid", "short": "degrees grid", "model": "sphere", "km": grid_km, "metric_id": None, "own": grid_expl, "method": True,
             "what": "Latitude and longitude read as graph-paper coordinates, 1° = 111.2 km both ways", "tex": r"d_{\text{grid}} = k\sqrt{\Delta\varphi^2+\Delta\lambda^2}"},
            {"id": "mercator", "label": "Ruler on a flat Mercator map", "short": "flat-map ruler", "model": "sphere", "km": by["mercator_distortion"]["value"], "metric_id": "mercator_distortion", "own": None, "method": True,
             "what": "A straight line on a flat Mercator map, measured with the map's scale at the equator", "tex": r"d_{\text{flat}} = R\sqrt{\Delta\lambda^2+\Delta\psi^2}"},
        ]
        for r in spec:
            r["is_reference"] = r["id"] == ref_id
            r["badges"] = (["reference"] if r["is_reference"] else []) + (["conventional"] if r["id"] == "great_circle_mean" else [])
            r["vs_sphere_km"] = r["vs_sphere_pct"] = r["vs_sphere_display"] = None
            if r["km"] is None:
                reason = by[r["metric_id"]]["display"] if r["metric_id"] else "undefined"
                r.update(display=reason, diff_km=None, diff_display=None, diff_pct=None)
            else:
                diff = r["km"] - ref_km
                r.update(display=fmt_dist(r["km"], unit), diff_km=diff, diff_pct=diff / ref_km * 100.0,
                         diff_display="reference" if r["is_reference"] else (diff_text(diff) if abs(diff / ref_km * 100.0) < 0.001 else f"{diff_text(diff)} ({pct_text(diff / ref_km * 100.0)})"))
                if r.get("method"):
                    sd = r["km"] - d_km
                    r.update(vs_sphere_km=sd, vs_sphere_pct=sd / d_km * 100.0,
                             vs_sphere_display=f"{diff_text(sd)} vs great circle on the same sphere")
        spec.sort(key=lambda r: (r["km"] is None, round(r["km"]) if r["km"] is not None else 0, not r["is_reference"],
                                 r["km"] if r["km"] is not None else 0.0))       # shortest first; the reference leads a group of equal values
        have = [r for r in spec if r["km"] is not None]
        steps = [step("Reference", None, None,
                      f"All differences are given relative to the {ref_label}: {fmt_dist(ref_km, unit)}."
                      + ("" if ref_id == "vincenty" else " (Vincenty's formula has no result for this pair.)"))]
        for r in spec:
            result = r["display"] if r["km"] is None else (r["display"] + ("" if r["is_reference"] else f" ({pct_text(r['diff_pct'], 2)} vs the reference)"))
            steps.append(step(f"{r['label']} [{r['model']}]", r["tex"], None, f"{result}: {r['what']}"))
        # -- the two effects: the Earth model and the method
        spheres = [r for r in spec if r["id"] in ("sphere_polar", "great_circle_mean", "sphere_equatorial")]
        sphere_methods = [r for r in spec if r["model"] == "sphere" and r["km"] is not None and (r["id"] == "great_circle_mean" or r.get("method"))]
        summary = []
        if len(spheres) == 3:
            lo, hi = min(r["km"] for r in spheres), max(r["km"] for r in spheres)
            summary.append(f"Same method, different Earth model: the great circle is {fmt_dist(lo, unit)} to {fmt_dist(hi, unit)} depending on the sphere "
                           f"(a spread of {(hi - lo) / d_km * 100.0:.2f} %), and {fmt_dist(ref_km, unit)} on the ellipsoid.")
        if len(sphere_methods) >= 2:
            lo, hi = min(r["km"] for r in sphere_methods), max(r["km"] for r in sphere_methods)
            summary.append(f"Same Earth model (the mean sphere), different method: {fmt_dist(lo, unit)} to {fmt_dist(hi, unit)}, up to {pct_text((hi - d_km) / d_km * 100.0)} compared with the great circle.")
        conv_pct = (d_km - ref_km) / ref_km * 100.0
        footnotes = ["Rows marked sphere use R = 6371.0088 km unless stated otherwise; their difference from the reference includes the sphere's own model error.",
                     f"The great circle on the mean-radius sphere is the standard, conventional method. Here it is {pct_text(conv_pct, 2)} off the reference; "
                     f"typically it is within {K.SPHERE_ERROR_TYPICAL_PCT:g} % and at most about {K.SPHERE_ERROR_MAX_PCT:g} % (see docs/ACCURACY.md)."]
        if ref_id != "vincenty":
            footnotes.append("Vincenty's formula does not converge for nearly antipodal points; Lambert is used as the reference, and its accuracy is reduced here as well.")
        others = [r for r in have if not r["is_reference"] and r["id"] not in ("sphere_polar", "sphere_equatorial", "lambert")]
        far_over = max(others, key=lambda r: r["diff_pct"], default=None)
        far_under = min(others, key=lambda r: r["diff_pct"], default=None)
        sec = []
        if far_over and far_over["diff_pct"] > 0.05:
            sec.append(f"{far_over['short']} {pct_text(far_over['diff_pct'])}")
        if far_under and far_under["diff_pct"] < -0.05:
            sec.append(f"{far_under['short']} {pct_text(far_under['diff_pct'])}")
        sec.append(f"great circle (conventional) {pct_text(conv_pct)}")
        notes = ["All of these describe the same two points. They differ for two different reasons: the method (a path over a surface, on a flat map, or through the Earth) and the model of the Earth (a sphere of some radius, or the ellipsoid).",
                 _detour_text(d_km, unit, cruise_kmh) + " Distances here are at sea level.",
                 f"The reference is the {ref_label}. Vincenty's formula agrees with Karney's algorithm to about 0.1 mm wherever it converges."] + footnotes + summary
        if path_sep_km is not None and path_sep_km >= 1.0:
            notes.append(f"The straight line on a Mercator map (the rhumb line) and the great circle are up to about {fmt_dist(path_sep_km, unit)} apart on the ground, although their lengths differ much less.")
        rows = [{k: r[k] for k in ("id", "label", "what", "km", "display", "diff_km", "diff_display", "diff_pct", "is_reference", "metric_id", "model", "badges",
                                    "vs_sphere_km", "vs_sphere_pct", "vs_sphere_display")} | {"explanation": r["own"]} for r in spec]
        metrics.append(_metric(
            "distance_analysis", "Geometry", "Distance analysis", float(len(have)), None,
            f"{fmt_dist(min(r['km'] for r in have), unit)} to {fmt_dist(max(r['km'] for r in have), unit)}", sec,
            explanation("The same two points, measured in different ways: the answer depends on the method and on the model of the Earth.", steps,
                        [C_R, const("a", f"{K.WGS84_A_KM} km", "WGS84 equatorial radius"), const("b", f"{K.WGS84_B_KM:.4f} km", "WGS84 polar radius")], notes),
            table=[{"label": f"{r['label']} [{r['model']}]", "display": f"{r['display']} — reference" if r["is_reference"]
                    else (r["display"] if r["diff_pct"] is None else (f"{r['display']} ({diff_text(r['diff_km'])})" if abs(r["diff_pct"]) < 0.001 else f"{r['display']} ({pct_text(r['diff_pct'])})"))} for r in spec],
            analysis={"reference_id": ref_id, "reference_label": ref_label, "rows": rows, "summary": summary, "footnotes": footnotes}))

    # ------------------------------------------------------------------ paths and markers
    paths = {"great_circle": [], "rhumb": [], "projection": proj_path}
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
                             for c in cross_found],
               "projected": proj_marker}

    # Circles of equal distance around A and B (radius = the route length unless given); cut at the antimeridian.
    circles = []
    radius_km = d_km if circle_km is None else circle_km
    if radius_km > 1e-6:
        for key, (c_lat, c_lon) in (("a", (p1, l1)), ("b", (p2, l2))):
            ring = [spherical.destination(c_lat, c_lon, K.TWO_PI * i / K.CIRCLE_SAMPLES, radius_km / R)
                    for i in range(K.CIRCLE_SAMPLES + 1)]
            circles.append({"center": key, "radius_km": round(radius_km, 3),
                            "segments": [[[round(deg(lo), 6), round(deg(la), 6)] for la, lo in seg]
                                         for seg in spherical.split_antimeridian(ring)]})

    if unit != "km":
        for m in metrics:
            if m["id"] in unit_conv:
                _add_unit_info(m, unit_conv[m["id"]], unit)
    metrics.sort(key=lambda m: ORDER.index(m["id"]))
    return {"a": {"lat": a_lat, "lon": a_lon}, "b": {"lat": b_lat, "lon": b_lon},
            "warnings": warnings, "paths": paths, "markers": markers, "circles": circles, "metrics": metrics}
