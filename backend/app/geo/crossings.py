"""Where does the great-circle route cross a circle of latitude or a meridian? `math` only, radians.

Everything is done with unit vectors, so it works for any route (also through a pole):

    A  = (cos(phi) cos(lam), cos(phi) sin(lam), sin(phi))   unit vector of the start point
    n  = A x B / |A x B|                                    normal of the plane of the route
    e2 = n x A                                              unit vector in the plane, perpendicular to A, towards B
    P(sigma) = A cos(sigma) + e2 sin(sigma)                 the point sigma radians along the route from A

The route runs from sigma = 0 (A) to sigma = delta (B, the central angle).
"""
import math

EPS = 1e-9


def _vec(lat, lon):
    return (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def route_frame(lat1, lon1, lat2, lon2):
    """Returns (A, e2, n) for the route A -> B, or None if A and B are identical or antipodal."""
    a = _vec(lat1, lon1)
    b = _vec(lat2, lon2)
    n = _cross(a, b)
    length = _norm(n)
    if length < 1e-12:
        return None
    n = tuple(c / length for c in n)
    return a, _cross(n, a), n


def point_at(a, e2, sigma):
    """(lat, lon) of P(sigma)."""
    p = tuple(a[i] * math.cos(sigma) + e2[i] * math.sin(sigma) for i in range(3))
    # atan2 on the horizontal part stays accurate near the poles (asin would lose precision there)
    return math.atan2(p[2], math.hypot(p[0], p[1])), math.atan2(p[1], p[0])


def course_at(a, e2, sigma):
    """Course (azimuth, radians in [0, 2*pi), 0 = north) of the route at P(sigma); None at a pole.

    The direction of travel is T = -A sin(sigma) + e2 cos(sigma); the course is its angle from local
    north towards local east.
    """
    lat, lon = point_at(a, e2, sigma)
    p = tuple(a[i] * math.cos(sigma) + e2[i] * math.sin(sigma) for i in range(3))
    if math.hypot(p[0], p[1]) < 1e-9:            # at a pole every direction is south (or north)
        return None
    t = tuple(-a[i] * math.sin(sigma) + e2[i] * math.cos(sigma) for i in range(3))
    east = (-math.sin(lon), math.cos(lon), 0.0)
    north = (-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat))
    return math.atan2(_dot(t, east), _dot(t, north)) % (2.0 * math.pi)


def latitude_info(a, e2):
    """C = hypot(A_z, e2_z) and sigma0 = atan2(e2_z, A_z), so that z(sigma) = C cos(sigma - sigma0).

    The full great circle never goes beyond latitude asin(C).
    """
    return math.hypot(a[2], e2[2]), math.atan2(e2[2], a[2])


def latitude_crossings(a, e2, delta, lat_c):
    """Distances sigma (radians from A, ascending) where the route is at latitude lat_c.

        z(sigma) = A_z cos(sigma) + e2_z sin(sigma) = sin(lat_c)
        sigma = sigma0 +/- acos(sin(lat_c) / C),   C = hypot(A_z, e2_z),  sigma0 = atan2(e2_z, A_z)
    Returns the string 'along' if the whole route lies on that latitude (only the equator can), else a list.
    """
    c, sigma0 = latitude_info(a, e2)
    if c < 1e-12:                                   # the great circle is the equator itself
        return "along" if abs(math.sin(lat_c)) < 1e-12 else []
    s = math.sin(lat_c) / c
    if abs(s) > 1.0 + 1e-12:
        return []
    s = max(-1.0, min(1.0, s))
    hits = []
    for sign in (1.0, -1.0):
        sigma = (sigma0 + sign * math.acos(s)) % (2.0 * math.pi)
        if sigma > 2.0 * math.pi - EPS:
            sigma = 0.0
        if sigma <= delta + EPS and all(abs(sigma - h) > EPS for h in hits):   # tangent: one point only
            hits.append(sigma)
    return sorted(hits)


def meridian_crossing(a, e2, n, delta, lon_c):
    """Distance sigma (radians from A) where the route is on the meridian lon_c, or None.

        P = +/-(n x m),  m = (-sin(lon_c), cos(lon_c), 0)   (intersection of two planes through the Earth's centre)
    The sign is chosen so that P really has longitude lon_c (not the opposite meridian).
    Returns 'along' if the route lies in that meridian's plane.
    """
    m = (-math.sin(lon_c), math.cos(lon_c), 0.0)
    p = _cross(n, m)
    length = _norm(p)
    if length < 1e-9:
        return "along"
    p = tuple(c / length for c in p)
    if p[0] * math.cos(lon_c) + p[1] * math.sin(lon_c) < 0:
        p = tuple(-c for c in p)
    sigma = math.atan2(_dot(p, e2), _dot(p, a)) % (2.0 * math.pi)
    if sigma > 2.0 * math.pi - EPS:
        sigma = 0.0
    return sigma if sigma <= delta + EPS else None
