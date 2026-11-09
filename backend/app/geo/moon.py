"""Phase of the Moon from low-precision lunar and solar longitudes. `math` only.

The Moon's ecliptic longitude and latitude come from a short series of sine terms (a low-precision formula of the
kind published in the Astronomical Almanac; about 0.3 degrees, i.e. well under an hour of the Moon's motion), the
Sun's longitude from geo/sun.py. The lit fraction follows from the angle between them (the elongation).
Checked against PyEphem: the lit fraction is within 0.3 percentage points, new and full moon within about an hour.

Angles are radians unless the name ends in *_deg. `jd` is a Julian date (x.0 = 12:00 UTC).
"""
import math

from .sun import JD_J2000, sun_position

PHASE_NAMES = ["New moon", "Waxing crescent", "First quarter", "Waxing gibbous",
               "Full moon", "Waning gibbous", "Last quarter", "Waning crescent"]

# Ecliptic longitude of the Moon, degrees, T in Julian centuries since J2000.0:
#   lam = 218.32 + 481267.881 T + sum( a * sin(b + c T) )        terms (a, b, c)
LONGITUDE_BASE = (218.32, 481267.881)
LONGITUDE_TERMS = ((6.29, 135.0, 477198.87), (-1.27, 259.3, -413335.36), (0.66, 235.7, 890534.22),
                   (0.21, 269.9, 954397.74), (-0.19, 357.5, 35999.05), (-0.11, 186.5, 966404.03))
# Ecliptic latitude of the Moon, degrees:   beta = sum( a * sin(b + c T) )
LATITUDE_TERMS = ((5.13, 93.3, 483202.02), (0.28, 228.2, 960400.89), (-0.28, 318.3, 6003.15), (-0.17, 217.6, -407332.21))


def centuries(jd):
    """T = (JD - 2451545.0) / 36525: Julian centuries since J2000.0."""
    return (jd - JD_J2000) / 36525.0


def _series(terms, t):
    return sum(a * math.sin(math.radians(b + c * t)) for a, b, c in terms)


def series_values(terms, t):
    """The individual terms a * sin(b + c T), in degrees (for showing the calculation step by step)."""
    return [a * math.sin(math.radians(b + c * t)) for a, b, c in terms]


def moon_position(jd):
    """Ecliptic (longitude, latitude) of the Moon in radians at Julian date jd."""
    t = centuries(jd)
    lon = LONGITUDE_BASE[0] + LONGITUDE_BASE[1] * t + _series(LONGITUDE_TERMS, t)
    lat = _series(LATITUDE_TERMS, t)
    return math.radians(lon % 360.0), math.radians(lat)


def elongation(jd):
    """Angular distance between Moon and Sun. Returns (psi, d_deg, lam_moon, beta, lam_sun):

        cos(psi) = cos(beta) cos(lam_moon - lam_sun)          psi in [0, pi]  (0 = new moon, pi = full moon)
        d = (lam_moon - lam_sun) mod 360 degrees                0 new, 90 first quarter, 180 full, 270 last quarter
    """
    lam_m, beta = moon_position(jd)
    lam_s = sun_position(jd)["lam"]
    psi = math.acos(max(-1.0, min(1.0, math.cos(beta) * math.cos(lam_m - lam_s))))
    return psi, math.degrees(lam_m - lam_s) % 360.0, lam_m, beta, lam_s


def illuminated_fraction(psi):
    """Fraction of the disc that is lit:  (1 - cos psi) / 2."""
    return (1.0 - math.cos(psi)) / 2.0


def phase_name(d_deg):
    """One of eight names; each covers 45 degrees of the longitude difference, centred on 0, 45, 90, ..."""
    return PHASE_NAMES[int((d_deg + 22.5) // 45.0) % 8]


def time_of_phase(jd, target_deg, forward=True, mean_rate_deg_per_day=360.0 / 29.530588861, iterations=8):
    """Julian date of the next (or previous) moment the longitude difference d equals target_deg (0 new, 180 full).

    Starts from the mean motion of the Moon relative to the Sun (about 12.19 degrees per day) and corrects:
        t <- t + (target - d(t)) / rate           (wrapped to +/-180 degrees), repeated
    forward=True gives a time >= jd, forward=False a time <= jd.
    """
    d0 = elongation(jd)[1]
    gap = (target_deg - d0) % 360.0 if forward else -((d0 - target_deg) % 360.0)
    t = jd + gap / mean_rate_deg_per_day
    for _ in range(iterations):
        diff = (target_deg - elongation(t)[1] + 180.0) % 360.0 - 180.0
        t += diff / mean_rate_deg_per_day
    return t
