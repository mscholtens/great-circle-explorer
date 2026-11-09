"""Distances on an ellipsoid: Vincenty's inverse formula, Lambert's formula for long lines, and the straight chord. `math` only, radians."""
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


def vincenty_inverse(lat1, lon1, lat2, lon2, a, f, tol=1e-12, max_iter=200):
    """Vincenty's inverse formula (1975): geodesic distance on an ellipsoid with semi-major axis a and flattening f.

        U = atan((1-f) tan(phi)),  L = lam2 - lam1,  lam = L
        repeat until lam stops changing:
            sin(s) = sqrt((cos U2 sin lam)^2 + (cos U1 sin U2 - sin U1 cos U2 cos lam)^2)
            cos(s) = sin U1 sin U2 + cos U1 cos U2 cos lam,           s = atan2(sin s, cos s)
            sin(al) = cos U1 cos U2 sin lam / sin s,   cos^2(al) = 1 - sin^2(al)
            cos(2sm) = cos s - 2 sin U1 sin U2 / cos^2(al)            (0 along the equator)
            C = f/16 cos^2(al) (4 + f (4 - 3 cos^2(al)))
            lam = L + (1-C) f sin(al) (s + C sin s (cos 2sm + C cos s (-1 + 2 cos^2 2sm)))
        u^2 = cos^2(al) (a^2 - b^2) / b^2
        A = 1 + u^2/16384 (4096 + u^2 (-768 + u^2 (320 - 175 u^2)))
        B = u^2/1024 (256 + u^2 (-128 + u^2 (74 - 47 u^2)))
        ds = B sin s (cos 2sm + B/4 (cos s (-1 + 2 cos^2 2sm) - B/6 cos 2sm (-3 + 4 sin^2 s)(-3 + 4 cos^2 2sm)))
        distance = b A (s - ds)

    Accurate to about 0.1 mm wherever it converges. Does not converge for nearly antipodal points (and is undefined
    for exactly antipodal ones): then None is returned. Identical points give distance 0.
    Returns a dict (b, U1, U2, L, log, iterations, sigma, sin_sigma, cos_sigma, sin_alpha, cos2_alpha, cos_2sigma_m,
    C, u2, A, B, delta_sigma, dist); `log` has one entry per round (lam, sigma, cos2_alpha, cos_2sigma_m, C, new_lam).
    """
    b = a * (1.0 - f)
    u1 = math.atan((1.0 - f) * math.tan(lat1))
    u2_ = math.atan((1.0 - f) * math.tan(lat2))
    big_l = lon2 - lon1
    lam = big_l
    s_u1, c_u1, s_u2, c_u2 = math.sin(u1), math.cos(u1), math.sin(u2_), math.cos(u2_)
    log = []
    for iteration in range(1, max_iter + 1):
        s_lam, c_lam = math.sin(lam), math.cos(lam)
        sin_sigma = math.sqrt((c_u2 * s_lam) ** 2 + (c_u1 * s_u2 - s_u1 * c_u2 * c_lam) ** 2)
        cos_sigma = s_u1 * s_u2 + c_u1 * c_u2 * c_lam
        if sin_sigma < 1e-15:
            if cos_sigma > 0:                     # identical points
                return {"dist": 0.0, "iterations": 0, "log": [], "b": b}
            return None                           # antipodal: infinitely many geodesics, no unique distance
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = c_u1 * c_u2 * s_lam / sin_sigma
        cos2_alpha = 1.0 - sin_alpha ** 2
        cos_2sm = cos_sigma - 2.0 * s_u1 * s_u2 / cos2_alpha if cos2_alpha != 0.0 else 0.0
        c = f / 16.0 * cos2_alpha * (4.0 + f * (4.0 - 3.0 * cos2_alpha))
        new_lam = big_l + (1.0 - c) * f * sin_alpha * (
            sigma + c * sin_sigma * (cos_2sm + c * cos_sigma * (-1.0 + 2.0 * cos_2sm ** 2)))
        log.append({"lam": lam, "sigma": sigma, "cos2_alpha": cos2_alpha, "cos_2sigma_m": cos_2sm, "C": c, "new_lam": new_lam})
        if not math.isfinite(new_lam):
            return None
        converged = abs(new_lam - lam) < tol
        lam = new_lam
        if converged:
            break
    else:
        return None                               # no convergence: nearly antipodal points
    u2 = cos2_alpha * (a * a - b * b) / (b * b)
    big_a = 1.0 + u2 / 16384.0 * (4096.0 + u2 * (-768.0 + u2 * (320.0 - 175.0 * u2)))
    big_b = u2 / 1024.0 * (256.0 + u2 * (-128.0 + u2 * (74.0 - 47.0 * u2)))
    delta_sigma = big_b * sin_sigma * (cos_2sm + big_b / 4.0 * (
        cos_sigma * (-1.0 + 2.0 * cos_2sm ** 2)
        - big_b / 6.0 * cos_2sm * (-3.0 + 4.0 * sin_sigma ** 2) * (-3.0 + 4.0 * cos_2sm ** 2)))
    return {"b": b, "U1": u1, "U2": u2_, "L": big_l, "log": log, "iterations": iteration, "sigma": sigma,
            "sin_sigma": sin_sigma, "cos_sigma": cos_sigma, "sin_alpha": sin_alpha, "cos2_alpha": cos2_alpha,
            "cos_2sigma_m": cos_2sm, "C": c, "u2": u2, "A": big_a, "B": big_b, "delta_sigma": delta_sigma,
            "dist": b * big_a * (sigma - delta_sigma)}


def ecef(lat, lon, a, f):
    """Earth-centred coordinates (X, Y, Z) of a point on the ellipsoid surface (geodetic latitude, longitude).

        e^2 = f (2 - f),  N = a / sqrt(1 - e^2 sin^2 phi)
        X = N cos(phi) cos(lam),  Y = N cos(phi) sin(lam),  Z = N (1 - e^2) sin(phi)
    """
    e2 = f * (2.0 - f)
    n = a / math.sqrt(1.0 - e2 * math.sin(lat) ** 2)
    return (n * math.cos(lat) * math.cos(lon), n * math.cos(lat) * math.sin(lon), n * (1.0 - e2) * math.sin(lat))


def ellipsoid_chord(lat1, lon1, lat2, lon2, a, f):
    """Straight-line distance through the Earth between two points on the ellipsoid: sqrt(dX^2 + dY^2 + dZ^2).

    Returns (chord, p1, p2) with p1 and p2 the Earth-centred coordinates of the two points.
    """
    p1 = ecef(lat1, lon1, a, f)
    p2 = ecef(lat2, lon2, a, f)
    return math.sqrt(sum((q - p) ** 2 for p, q in zip(p1, p2))), p1, p2
