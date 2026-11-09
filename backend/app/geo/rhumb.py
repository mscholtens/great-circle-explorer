"""Rhumb lines (constant compass bearing) on a sphere. `math` only, radians."""
import math

from .spherical import wrap_2pi


def isometric_lat(lat):
    """Mercator 'stretched' latitude: psi = ln(tan(pi/4 + phi/2))."""
    return math.log(math.tan(math.pi / 4.0 + lat / 2.0))


def rhumb(lat1, lon1, lat2, lon2):
    """Rhumb-line geometry from point 1 to point 2 on the unit sphere.

        dpsi = ln(tan(pi/4 + phi2/2) / tan(pi/4 + phi1/2))
        q    = dphi / dpsi  (cos(phi1) if dpsi ~ 0)
        dlam wrapped to [-pi, pi]  (shorter way around)
        dist = sqrt(dphi^2 + q^2 dlam^2)   (angular, multiply by R)
        theta = atan2(dlam, dpsi)
    Returns a dict with dphi, dpsi, q, dlam, dist, theta. Undefined (ValueError) at a pole.
    """
    if abs(lat1) >= math.pi / 2 - 1e-12 or abs(lat2) >= math.pi / 2 - 1e-12:
        raise ValueError("rhumb line undefined at a pole")
    dphi = lat2 - lat1
    dpsi = isometric_lat(lat2) - isometric_lat(lat1)
    q = dphi / dpsi if abs(dpsi) > 1e-12 else math.cos(lat1)
    dlam = lon2 - lon1
    if abs(dlam) > math.pi:
        dlam -= math.copysign(2.0 * math.pi, dlam)
    dist = math.sqrt(dphi ** 2 + (q * dlam) ** 2)
    theta = wrap_2pi(math.atan2(dlam, dpsi))
    return {"dphi": dphi, "dpsi": dpsi, "q": q, "dlam": dlam, "dist": dist, "theta": theta}


def sample_rhumb(lat1, lon1, r, n=128):
    """n+1 points (lat, lon) along the rhumb line; longitudes continuous (no wrapping jumps).

        phi_f = phi1 + f dphi;  lam_f = lam1 + dlam (psi(phi_f) - psi(phi1)) / dpsi
    """
    psi1 = isometric_lat(lat1)
    pts = []
    for i in range(n + 1):
        f = i / n
        lat = lat1 + f * r["dphi"]
        if abs(r["dpsi"]) > 1e-12:
            lon = lon1 + r["dlam"] * (isometric_lat(lat) - psi1) / r["dpsi"]
        else:
            lon = lon1 + f * r["dlam"]
        pts.append((lat, lon))
    return pts
