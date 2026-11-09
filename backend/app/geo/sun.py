"""Approximate sunrise/sunset and day length. `math` only; angles in radians unless named *_deg.

Accuracy: a few minutes. Day of year N is an integer (1 = 1 January), supplied by the caller.
"""
import math


def declination(n, tilt_deg):
    """Solar declination (radians): decl = -tilt * cos(360/365 (N + 10))."""
    return -math.radians(tilt_deg) * math.cos(math.radians(360.0 / 365.0 * (n + 10)))


def equation_of_time_min(n):
    """Equation of time in minutes: B = 360/365 (N - 81); EoT = 9.87 sin 2B - 7.53 cos B - 1.5 sin B."""
    b = math.radians(360.0 / 365.0 * (n - 81))
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def sun_times(lat, lon, n, tilt_deg, h0_deg):
    """Sunrise/sunset for latitude lat, longitude lon (radians) on day n.

    Returns a dict: decl, eot_min, cos_w0 (None at a pole), state ('normal' | 'polar_day' | 'polar_night'),
    w0_deg, day_length_h, solar_noon_h, sunrise_h, sunset_h (UTC hours in [0, 24), None if no event).

        cos(w0) = (sin(h0) - sin(phi) sin(decl)) / (cos(phi) cos(decl))
    cos(w0) < -1 -> polar day; > 1 -> polar night. At exactly +/-90 deg the quotient is replaced by
    the sign test sin(phi) sin(decl) > sin(h0).
    """
    decl = declination(n, tilt_deg)
    eot = equation_of_time_min(n)
    sin_h0 = math.sin(math.radians(h0_deg))
    noon = (12.0 - math.degrees(lon) / 15.0 - eot / 60.0) % 24.0
    out = {"decl": decl, "eot_min": eot, "cos_w0": None, "w0_deg": None,
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
