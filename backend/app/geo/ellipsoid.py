"""Lambert's formula for long lines on an ellipsoid. `math` only, radians."""
import math

from .spherical import haversine


def lambert_distance(lat1, lon1, lat2, lon2, a, f):
    """Lambert (1942) geodesic distance on an ellipsoid with semi-major axis a and flattening f.

        beta = atan((1-f) tan(phi))                 reduced latitudes
        sigma = central angle between (beta1, lam1) and (beta2, lam2)
        P = (beta1+beta2)/2, Q = (beta2-beta1)/2
        X = (sigma - sin sigma) sin^2 P cos^2 Q / cos^2(sigma/2)
        Y = (sigma + sin sigma) cos^2 P sin^2 Q / sin^2(sigma/2)
        d = a (sigma - f/2 (X + Y))
    Returns a dict (beta1, beta2, sigma, P, Q, X, Y, dist) or None if sigma is 0 or pi.
    """
    b1 = math.atan((1.0 - f) * math.tan(lat1))
    b2 = math.atan((1.0 - f) * math.tan(lat2))
    _, sigma = haversine(b1, lon1, b2, lon2)
    if sigma < 1e-9 or abs(sigma - math.pi) < 1e-9:
        return None
    p = (b1 + b2) / 2.0
    q = (b2 - b1) / 2.0
    x = (sigma - math.sin(sigma)) * math.sin(p) ** 2 * math.cos(q) ** 2 / math.cos(sigma / 2.0) ** 2
    y = (sigma + math.sin(sigma)) * math.cos(p) ** 2 * math.sin(q) ** 2 / math.sin(sigma / 2.0) ** 2
    dist = a * (sigma - f / 2.0 * (x + y))
    return {"beta1": b1, "beta2": b2, "sigma": sigma, "P": p, "Q": q, "X": x, "Y": y, "dist": dist}
