"""All physical and model constants. Nothing numeric is hidden elsewhere."""
import datetime as dt
import math

# Mean Earth radius (IUGG), km
R_KM = 6371.0088
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
# Axial tilt used in the declination approximation, degrees (it drifts by about 0.5 arc-second per year)
AXIAL_TILT_DEG = 23.44
# Tropics of Cancer / Capricorn lie at +/- the axial tilt, degrees
TROPIC_LAT_DEG = AXIAL_TILT_DEG
# Arctic / Antarctic circles lie at +/- (90 deg - axial tilt), degrees
POLAR_CIRCLE_LAT_DEG = 90.0 - AXIAL_TILT_DEG
# WGS84 equatorial radius, km
WGS84_A_KM = 6378.137
# WGS84 flattening
WGS84_F = 1.0 / 298.257223563
# Typical airliner cruise altitude, m
CRUISE_ALTITUDE_M = 11000.0
# Default observer eye height, m
EYE_HEIGHT_M_DEFAULT = 1.7
# Web Mercator latitude limit (atan(sinh(pi))), degrees
MERCATOR_MAX_LAT_DEG = 85.0511

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
TWO_PI = 2.0 * math.pi
