"""Distance measured on a flat Mercator map. `math` only, radians."""
import math

from .rhumb import isometric_lat


def scale_factor(lat):
    """Local Mercator scale factor: sec(phi) = 1 / cos(phi)."""
    return 1.0 / math.cos(lat)


def flat_map_distance(lat1, lon1, lat2, lon2):
    """Straight-line distance on the Mercator plane x = lam, y = psi(phi), as an angle (multiply by R).

        dlam wrapped to [-pi, pi]
        d_flat = sqrt(dlam^2 + dpsi^2)
    Returns a dict with dlam, dpsi, dist.
    """
    dlam = lon2 - lon1
    if abs(dlam) > math.pi:
        dlam -= math.copysign(2.0 * math.pi, dlam)
    dpsi = isometric_lat(lat2) - isometric_lat(lat1)
    return {"dlam": dlam, "dpsi": dpsi, "dist": math.sqrt(dlam ** 2 + dpsi ** 2)}
