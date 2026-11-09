"""Position of the Sun, sunrise/sunset, sub-solar point and day/night boundary. `math` only.

The Sun's position uses the low-precision formulas of the kind published in the Astronomical Almanac (mean
longitude, mean anomaly, equation of centre, obliquity). Valid for roughly 1950-2050, where the declination is
good to about 0.005 degrees and the equation of time to about 0.1 minute (checked against PyEphem).

Angles are radians unless the name ends in *_deg. `jd` is a Julian date (days; x.0 = 12:00 UTC).
"""
import math

JD_J2000 = 2451545.0     # Julian date of 2000-01-01 12:00 (J2000.0); the Sun formulas count days from it


def sun_position(jd):
    """Low-precision position of the Sun at Julian date jd. Returns a dict:

        n      days since J2000.0                           n = JD - 2451545.0
        L_deg  mean longitude                               L = 280.460 + 0.9856474 n          (degrees, mod 360)
        g_deg  mean anomaly                                 g = 357.528 + 0.9856003 n          (degrees, mod 360)
        lam    ecliptic longitude of the Sun                lam = L + 1.915 sin g + 0.020 sin 2g
        eps    obliquity of the ecliptic                    eps = 23.439 - 0.0000004 n         (degrees)
        ra     right ascension                              ra = atan2(cos eps sin lam, cos lam)
        decl   declination                                  decl = asin(sin eps sin lam)
        eot_min  equation of time (apparent - mean solar time), minutes
                                                            EoT = 4 min/deg (L - 0.0057183 - ra)   (angle wrapped to +/-180)
    """
    n = jd - JD_J2000
    l_deg = (280.460 + 0.9856474 * n) % 360.0
    g_deg = (357.528 + 0.9856003 * n) % 360.0
    g = math.radians(g_deg)
    lam = math.radians(l_deg + 1.915 * math.sin(g) + 0.020 * math.sin(2.0 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    decl = math.asin(math.sin(eps) * math.sin(lam))
    eot_deg = (l_deg - 0.0057183 - math.degrees(ra) + 180.0) % 360.0 - 180.0
    return {"n": n, "L_deg": l_deg, "g_deg": g_deg, "lam": lam, "eps": eps, "ra": ra, "decl": decl,
            "eot_min": 4.0 * eot_deg}


def sun_times(lat, lon, jd_day, h0_deg):
    """Sunrise/sunset for latitude lat, longitude lon (radians) on the local solar day whose noon is
    nearest to jd_day (the Julian date of 12:00 UTC of the chosen calendar date).

    The Sun's declination and the equation of time are taken at the moment of local solar noon (jd_day - lon/2pi,
    corrected once for the equation of time), so the longitude does not matter for which day is meant.

    Returns a dict: pos (sun_position at local noon), jd_noon, eot_first_min (the correction used to find it), decl, eot_min, cos_w0 (None at a pole),
    state ('normal' | 'polar_day' | 'polar_night'), w0_deg, day_length_h, solar_noon_h, sunrise_h, sunset_h
    (UTC clock hours in [0, 24), None if no event; they can fall on the previous or next UTC date).

        cos(w0) = (sin(h0) - sin(phi) sin(decl)) / (cos(phi) cos(decl))
    cos(w0) < -1 -> polar day; > 1 -> polar night. At exactly +/-90 deg the quotient is replaced by
    the sign test sin(phi) sin(decl) > sin(h0).
    """
    jd_noon = jd_day - lon / (2.0 * math.pi)
    eot_first = sun_position(jd_noon)["eot_min"]
    jd_noon = jd_day - lon / (2.0 * math.pi) - eot_first / 1440.0                 # the true moment of local solar noon
    pos = sun_position(jd_noon)
    decl, eot = pos["decl"], pos["eot_min"]
    sin_h0 = math.sin(math.radians(h0_deg))
    noon = (12.0 - math.degrees(lon) / 15.0 - eot / 60.0) % 24.0
    out = {"pos": pos, "jd_noon": jd_noon, "eot_first_min": eot_first, "decl": decl, "eot_min": eot, "cos_w0": None, "w0_deg": None,
           "solar_noon_h": noon, "sunrise_h": None, "sunset_h": None}
    denom = math.cos(lat) * math.cos(decl)
    if abs(math.cos(lat)) < 1e-12:
        day = math.sin(lat) * math.sin(decl) > sin_h0
        out.update(state="polar_day" if day else "polar_night", day_length_h=24.0 if day else 0.0)
        return out
    cos_w0 = (sin_h0 - math.sin(lat) * math.sin(decl)) / denom
    out["cos_w0"] = cos_w0
    if cos_w0 < -1.0:
        out.update(state="polar_day", day_length_h=24.0)
    elif cos_w0 > 1.0:
        out.update(state="polar_night", day_length_h=0.0)
    else:
        w0 = math.degrees(math.acos(cos_w0))
        out.update(state="normal", w0_deg=w0, day_length_h=2.0 * w0 / 15.0,
                   sunrise_h=(noon - w0 / 15.0) % 24.0, sunset_h=(noon + w0 / 15.0) % 24.0)
    return out


def subsolar_point(jd):
    """Point where the Sun is straight overhead at Julian date jd: (declination, longitude, equation of time in min).

        latitude = decl;   longitude = -15 deg * (t_UTC - 12 h) - EoT / 4     (EoT in minutes, 4 min = 1 deg)
    """
    pos = sun_position(jd)
    utc_hours = ((jd - 0.5) % 1.0) * 24.0
    lon = math.radians(-15.0 * (utc_hours - 12.0) - pos["eot_min"] / 4.0)
    return pos["decl"], math.atan2(math.sin(lon), math.cos(lon)), pos["eot_min"]


def terminator_latitude(decl, lon, lon_sub):
    """Latitude of the day/night boundary (Sun on the horizon) at longitude lon, radians.

    The Sun's altitude h satisfies sin h = sin(phi) sin(decl) + cos(phi) cos(decl) cos(H) with the hour angle
    H = lon - lon_sub. Setting h = 0 gives tan(phi) = -cos(H) / tan(decl). Written with atan2 so that a
    declination of exactly 0 (equinox) gives +/-90 deg instead of a division by zero.
    """
    sign = 1.0 if decl >= 0 else -1.0
    return math.atan2(-math.cos(lon - lon_sub) * math.cos(decl) * sign, max(abs(math.sin(decl)), 1e-12))


def night_ring(decl, lon_sub, n=180):
    """Closed ring of (lat, lon) points (radians) enclosing the night side: the boundary curve from -180 to
    +180 degrees longitude, closed along the pole that is in darkness (the south pole when decl >= 0)."""
    ring = []
    for i in range(n + 1):
        lon = -math.pi + 2.0 * math.pi * i / n
        ring.append((terminator_latitude(decl, lon, lon_sub), lon))
    pole = -math.pi / 2 if decl >= 0 else math.pi / 2
    ring.append((pole, math.pi))
    ring.append((pole, -math.pi))
    ring.append(ring[0])
    return ring
