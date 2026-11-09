"""Spherical-Earth geometry. Pure functions, `math` only, angles in radians."""
import math

TWO_PI = 2.0 * math.pi


def wrap_pi(x):
    """Normalize an angle to [-pi, pi)."""
    return (x + math.pi) % TWO_PI - math.pi


def wrap_2pi(x):
    """Normalize an angle to [0, 2*pi)."""
    return x % TWO_PI


def haversine(lat1, lon1, lat2, lon2):
    """Haversine formula. Returns (a, delta) with the central angle delta in radians.

        a     = sin^2(dphi/2) + cos(phi1) cos(phi2) sin^2(dlam/2)
        delta = 2 atan2(sqrt(a), sqrt(1 - a))
    """
    dphi = lat2 - lat1
    dlam = lon2 - lon1
    a = math.sin(dphi / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlam / 2) ** 2
    a = min(1.0, max(0.0, a))
    delta = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return a, delta


def law_of_cosines(lat1, lon1, lat2, lon2):
    """Spherical law of cosines. Returns (cos_delta, delta).

        delta = acos(sin(phi1) sin(phi2) + cos(phi1) cos(phi2) cos(dlam))
    Numerically poor for very small distances (acos near 1).
    """
    c = math.sin(lat1) * math.sin(lat2) + math.cos(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return c, math.acos(min(1.0, max(-1.0, c)))


def initial_bearing(lat1, lon1, lat2, lon2):
    """Initial bearing from point 1 to point 2, radians in [0, 2*pi). Returns (y, x, theta).

        theta = atan2(sin(dlam) cos(phi2), cos(phi1) sin(phi2) - sin(phi1) cos(phi2) cos(dlam))
    """
    dlam = lon2 - lon1
    y = math.sin(dlam) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlam)
    return y, x, wrap_2pi(math.atan2(y, x))


def final_bearing(lat1, lon1, lat2, lon2):
    """Bearing of travel on arrival at point 2: (initial bearing from 2 to 1 + 180 deg) mod 360."""
    _, _, back = initial_bearing(lat2, lon2, lat1, lon1)
    return wrap_2pi(back + math.pi)


def midpoint(lat1, lon1, lat2, lon2):
    """Great-circle midpoint. Returns (Bx, By, lat_m, lon_m); lon_m in [-pi, pi).

        Bx = cos(phi2) cos(dlam),  By = cos(phi2) sin(dlam)
        phi_m = atan2(sin(phi1) + sin(phi2), sqrt((cos(phi1) + Bx)^2 + By^2))
        lam_m = lam1 + atan2(By, cos(phi1) + Bx)
    """
    dlam = lon2 - lon1
    bx = math.cos(lat2) * math.cos(dlam)
    by = math.cos(lat2) * math.sin(dlam)
    lat_m = math.atan2(math.sin(lat1) + math.sin(lat2),
                       math.sqrt((math.cos(lat1) + bx) ** 2 + by ** 2))
    lon_m = wrap_pi(lon1 + math.atan2(by, math.cos(lat1) + bx))
    return bx, by, lat_m, lon_m


def intermediate_point(lat1, lon1, lat2, lon2, delta, f):
    """Point at fraction f of the way along the great circle (spherical interpolation).

        A = sin((1-f) delta)/sin(delta), B = sin(f delta)/sin(delta)
        x = A cos(phi1) cos(lam1) + B cos(phi2) cos(lam2)   (similarly y, z)
        phi = atan2(z, sqrt(x^2 + y^2)), lam = atan2(y, x)
    """
    sd = math.sin(delta)
    a = math.sin((1.0 - f) * delta) / sd
    b = math.sin(f * delta) / sd
    x = a * math.cos(lat1) * math.cos(lon1) + b * math.cos(lat2) * math.cos(lon2)
    y = a * math.cos(lat1) * math.sin(lon1) + b * math.cos(lat2) * math.sin(lon2)
    z = a * math.sin(lat1) + b * math.sin(lat2)
    return math.atan2(z, math.sqrt(x * x + y * y)), math.atan2(y, x)


def unwrap_longitudes(lons):
    """Make a sequence of longitudes (radians) continuous by adding/subtracting 2*pi."""
    out = []
    for lon in lons:
        if out:
            lon += TWO_PI * round((out[-1] - lon) / TWO_PI)
        out.append(lon)
    return out


def sample_path(lat1, lon1, lat2, lon2, delta, n=128):
    """n+1 points (lat, lon) along the great circle, longitudes unwrapped across the antimeridian."""
    pts = [intermediate_point(lat1, lon1, lat2, lon2, delta, i / n) for i in range(n + 1)]
    pts[0] = (lat1, lon1)
    pts[-1] = (lat2, lon2)
    lons = unwrap_longitudes([p[1] for p in pts])
    return [(p[0], lon) for p, lon in zip(pts, lons)]


def plate_carree_distance(lat1, lon1, lat2, lon2):
    """The 'graph paper' distance: read latitude and longitude as flat x/y coordinates in degrees.

        dphi = phi2 - phi1,  dlam = lam2 - lam1 (the shorter way around, within +/-180 deg)
        d    = sqrt(dphi^2 + dlam^2)           in degrees; multiply by 111.195 km per degree
    Longitude degrees shrink towards the poles, so this overstates east-west distances away from the equator.
    Returns (dphi_deg, dlam_deg, d_deg).
    """
    dphi = math.degrees(lat2 - lat1)
    dlam = (math.degrees(lon2 - lon1) + 180.0) % 360.0 - 180.0
    return dphi, dlam, math.hypot(dphi, dlam)


def equirectangular_distance(lat1, lon1, lat2, lon2):
    """The 'programmer's shortcut': treat the surface near the route as flat, with longitude scaled by cos(mean latitude).

        phi_m = (phi1 + phi2) / 2,   dlam wrapped to [-pi, pi]
        d = R sqrt(dphi^2 + (dlam cos phi_m)^2)        (angle returned; multiply by R)
    Good for short distances, increasingly wrong for long ones. Returns (dphi, dlam, phi_m, angle).
    """
    dphi = lat2 - lat1
    dlam = wrap_pi(lon2 - lon1)
    phi_m = (lat1 + lat2) / 2.0
    return dphi, dlam, phi_m, math.hypot(dphi, dlam * math.cos(phi_m))


def _unit_vector(lat, lon):
    return (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))


def max_separation(points_a, points_b):
    """Largest distance from a point of path A to the nearest point of path B (lists of (lat, lon) in radians).

    For every point of A the closest point of B is found with unit vectors (angle = atan2(|cross|, dot)), then
    the largest of these distances is returned: (separation in radians, point of A, nearest point of B).
    The result is accurate to about half the spacing of the points of B.
    """
    vb = [_unit_vector(*p) for p in points_b]
    best = (-1.0, None, None)
    for pa in points_a:
        ax, ay, az = _unit_vector(*pa)
        closest, j_best = 4.0, 0
        for j, (bx, by, bz) in enumerate(vb):
            cx, cy, cz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
            ang = math.atan2(math.sqrt(cx * cx + cy * cy + cz * cz), ax * bx + ay * by + az * bz)
            if ang < closest:
                closest, j_best = ang, j
        if closest > best[0]:
            best = (closest, pa, points_b[j_best])
    return best


def split_antimeridian(points):
    """Cut a closed or open curve of (lat, lon) points (lon in [-pi, pi]) into pieces at the antimeridian.

    Where consecutive points jump by more than pi in longitude, the latitude at lon = +/-pi is found by linear
    interpolation and added to both pieces, so the pieces meet exactly at the edge of the map.
    """
    segments, current = [], [points[0]]
    for (la0, lo0), (la1, lo1) in zip(points, points[1:]):
        if abs(lo1 - lo0) > math.pi:
            lo1_unwrapped = lo1 + 2.0 * math.pi if lo1 < lo0 else lo1 - 2.0 * math.pi
            edge = math.pi if lo0 > 0 else -math.pi
            t = (edge - lo0) / (lo1_unwrapped - lo0)
            la_edge = la0 + t * (la1 - la0)
            current.append((la_edge, edge))
            segments.append(current)
            current = [(la_edge, -edge), (la1, lo1)]
        else:
            current.append((la1, lo1))
    segments.append(current)
    return segments


def destination(lat1, lon1, bearing, sigma):
    """Point reached from (lat1, lon1) travelling angular distance sigma on the given bearing.

        phi2 = asin(sin(phi1) cos(sigma) + cos(phi1) sin(sigma) cos(theta))
        lam2 = lam1 + atan2(sin(theta) sin(sigma) cos(phi1), cos(sigma) - sin(phi1) sin(phi2))
    """
    s = math.sin(lat1) * math.cos(sigma) + math.cos(lat1) * math.sin(sigma) * math.cos(bearing)
    lat2 = math.asin(min(1.0, max(-1.0, s)))
    lon2 = lon1 + math.atan2(math.sin(bearing) * math.sin(sigma) * math.cos(lat1),
                             math.cos(sigma) - math.sin(lat1) * math.sin(lat2))
    return lat2, wrap_pi(lon2)


def vertex_of_route(lat1, lon1, theta1, theta_final, delta):
    """Extreme-latitude point of the great circle, if it lies on the segment A->B.

    Clairaut: the vertex latitude of the full circle is phi_v = acos(|sin(theta1) cos(phi1)|).
    The northern vertex is on the segment iff the route heads north at A (cos theta1 > 0) and
    south at B (cos theta_final < 0); the southern one mirrors this.
    Returns None if the vertex is not on the segment, else a dict:
        phi_v (abs latitude of vertex), north (bool), sigma (distance A->vertex), lat, lon.
    """
    c1 = math.cos(theta1)
    cf = math.cos(theta_final)
    north = c1 > 0 and cf < 0
    south = c1 < 0 and cf > 0
    if not (north or south):
        return None
    phi_v = math.acos(min(1.0, abs(math.sin(theta1) * math.cos(lat1))))
    sign = 1.0 if north else -1.0
    sigma = math.atan2(abs(c1), sign * math.tan(lat1))
    lat_v, lon_v = destination(lat1, lon1, theta1, sigma)
    return {"phi_v": phi_v, "north": north, "sigma": sigma, "lat": lat_v, "lon": lon_v}


def antipode(lat, lon):
    """Antipodal point: phi_a = -phi, lam_a = lam +/- pi (normalized)."""
    return -lat, wrap_pi(lon + math.pi)


def chord_length(radius, delta):
    """Straight-line (tunnel) distance between two surface points: 2 R sin(delta/2)."""
    return 2.0 * radius * math.sin(delta / 2.0)


def sagitta(radius, delta):
    """Maximum depth of the straight tunnel = bulge of the surface above it: R (1 - cos(delta/2))."""
    return radius * (1.0 - math.cos(delta / 2.0))
