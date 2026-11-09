"""All physical and model constants. Nothing numeric is hidden elsewhere."""
import datetime as dt
import math

# Mean Earth radius (IUGG), km
R_KM = 6371.0088
# Length of one degree of arc on the sphere (pi R / 180), km. Used by the "degrees as a flat grid" measure
KM_PER_DEGREE = R_KM * math.pi / 180.0
# Standard gravity, m/s^2
G = 9.80665
# Speed of light in vacuum, km/s
C_KM_S = 299792.458
# Typical refractive index of single-mode optical fiber
FIBER_INDEX = 1.468
# International nautical mile, km
KM_PER_NM = 1.852
# International statute mile, km
KM_PER_MI = 1.609344
# Typical airliner cruise ground speed with no wind, km/h
CRUISE_KMH_DEFAULT = 850.0
# Extra airborne time for climb and descent (slower than cruise), minutes. Assumption, adjustable in the UI.
CLIMB_DESCENT_MIN_DEFAULT = 15.0
# Taxiing at both airports together (gate to take-off and landing to gate), minutes. Not part of airborne time.
TAXI_MIN_DEFAULT = 15.0
# Sun altitude at sunrise/sunset (atmospheric refraction + solar disc radius), degrees
SUN_ALTITUDE_DEG = -0.833
# Axial tilt used for the tropics and the polar circles, degrees (it drifts by about 0.5 arc-second per year;
# the Sun's declination uses the obliquity formula in geo/sun.py instead)
AXIAL_TILT_DEG = 23.44
# Tropics of Cancer / Capricorn lie at +/- the axial tilt, degrees
TROPIC_LAT_DEG = AXIAL_TILT_DEG
# Arctic / Antarctic circles lie at +/- (90 deg - axial tilt), degrees
POLAR_CIRCLE_LAT_DEG = 90.0 - AXIAL_TILT_DEG
# Largest error of Lambert's formula for pairs of points that are nearly antipodal, by central angle:
# (smallest central angle in degrees, size of the largest error), most severe first. Measured against the exact WGS84
# geodesic (GeographicLib) with 60 000 near-antipodal pairs, see tools/verify_accuracy.py and docs/ACCURACY.md.
# Below 170 degrees the error stays under 0.5 km (typically about 10 m).
LAMBERT_ERROR_TIERS = [
    (178.0, "tens of km"),
    (176.0, "up to about 2.5 km"),
    (174.0, "up to about 1.2 km"),
    (172.0, "up to about 0.8 km"),
    (170.0, "up to about 0.6 km"),
]
# Day length (hours) from which sunrise and sunset can be several minutes off (midnight-sun edge), see docs/ACCURACY.md
LONG_DAY_HINT_H = 21.0

# WGS84 equatorial radius, km
WGS84_A_KM = 6378.137
# WGS84 flattening
WGS84_F = 1.0 / 298.257223563
# WGS84 polar radius b = a (1 - f), km (6356.752...)
WGS84_B_KM = WGS84_A_KM * (1.0 - WGS84_F)
# WGS84 first eccentricity squared e^2 = f (2 - f), used for Earth-centred (ECEF) coordinates
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)
# Vincenty's iteration stops when lambda changes by less than this (radians; about 6 micrometres on the ground)
VINCENTY_TOLERANCE = 1e-12
# Vincenty's iteration gives up after this many rounds: for nearly antipodal points it does not converge.
# There is deliberately NO "give up as soon as |lambda| > pi" shortcut: many implementations have one, but it
# wrongly rejects pairs that do converge (Quito -> Singapore needs lambda > pi on the way and converges in 11 rounds).
VINCENTY_MAX_ITERATIONS = 200
# How far the conventional method (great circle on the sphere of mean radius) is from the WGS84 ellipsoid, percent:
# typical (about 90 % of random pairs) and largest (a meridian arc across the equator), see docs/ACCURACY.md
SPHERE_ERROR_TYPICAL_PCT = 0.2
SPHERE_ERROR_MAX_PCT = 0.5
# Typical airliner cruise altitude, m
CRUISE_ALTITUDE_M = 11000.0
# How much longer real flights are than the great-circle distance (average lengthening, percent), by flight class.
# Source: Dobruszkes F., Peeters D. (2019), "The magnitude of detours faced by commercial flights: A global assessment",
# Journal of Transport Geography 79, 102465 (https://doi.org/10.1016/j.jtrangeo.2019.102465), Table 2: 393 360 flights
# (Flightradar24 traces, 3-9 November 2017) against the great-circle distance, weighted by distance. The classes are
# defined by the shortest route: short haul up to 1000 km, medium haul 1001-4000 km, long haul more than 4000 km.
# The authors call it a conservative estimate (median 8.2 %, standard deviation 11.9 %).
FLIGHT_DETOUR_LIMITS_KM = (1000.0, 4000.0)
FLIGHT_DETOUR_PCT = {"all": 7.6, "short": 14.3, "medium": 7.3, "long": 4.8}
FLIGHT_DETOUR_SAMPLE = 393360
# Default observer eye height, m
EYE_HEIGHT_M_DEFAULT = 1.7
# Web Mercator latitude limit (atan(sinh(pi))), degrees
MERCATOR_MAX_LAT_DEG = 85.0511

# A point that lies in no time-zone polygon but within this distance of one (a coast, or a gap left by the
# simplified borders) is given the nearest zone; further out it counts as open ocean (nominal zone), km
TZ_NEAR_BORDER_KM = 15.0

# Dates accepted for the sun and time-zone metrics (the time-zone rules are extrapolated beyond today)
DATE_MIN = dt.date(1970, 1, 1)
DATE_MAX = dt.date(2049, 12, 31)

# Reference speeds for the "how long at..." metric: (label, km/h)
REFERENCE_SPEEDS = [
    ("Walking", 5.0),
    ("Car", 100.0),
    ("High-speed train", 300.0),
    ("Airliner (cruise)", CRUISE_KMH_DEFAULT),
    ("Concorde", 2180.0),
    ("ISS (orbital speed)", 27600.0),
    ("Light in vacuum", C_KM_S * 3600.0),
]

# Numerical tolerances (radians)
EPS_SAME = 1e-12            # points considered identical below this central angle
EPS_ANTIPODAL = 1e-9        # warning threshold: central angle within this of pi
EPS_PATH_ANTIPODAL = 1e-6   # path interpolation refused this close to pi (sin(delta) ~ 0)
EPS_POLE = 1e-9             # |lat| within this of 90 deg counts as a pole

COMPASS_16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

PATH_SAMPLES = 128
SEPARATION_GC_SAMPLES = 48       # points of the great circle used to measure how far it is from the rhumb line
SEPARATION_RHUMB_SAMPLES = 720   # points of the rhumb line (spacing about 16 km on a long route)
TWO_PI = 2.0 * math.pi

# Hour angle: the Earth turns 360 degrees in 24 h, so an angle of 15 degrees corresponds to one hour.
EARTH_ROTATION_DEG_PER_H = 15.0

# Samples for the map overlays (points per curve)
PROJECTION_SAMPLES = 64     # path from A to the projected point
CIRCLE_SAMPLES = 180        # circle of equal distance (one point every 2 degrees of bearing)
TERMINATOR_SAMPLES = 180    # day/night boundary (one point every 2 degrees of longitude)

# Units for the metric cards, inputs and the PDF (calculations and pop-up steps stay in km)
UNITS = {
    "km": {"label": "km", "speed_label": "km/h", "km_per_unit": 1.0},
    "nm": {"label": "nm", "speed_label": "kn", "km_per_unit": KM_PER_NM},      # nautical mile, knot
    "mi": {"label": "mi", "speed_label": "mph", "km_per_unit": KM_PER_MI},     # statute mile
}
UNIT_ORDER = ("km", "nm", "mi")

# Moon phase: the mean synodic month only supplies the starting guess when searching for the next new/full moon
SYNODIC_MONTH_DAYS = 29.530588861     # mean time between two new moons
JD_AT_ORDINAL_ZERO_NOON = 1721425.0   # JD of 12:00 UTC on day 0 of Python's proleptic Gregorian ordinal (date.toordinal())
