"""Map overlays that do not belong to a pair of points: the day/night boundary (terminator)."""
import math

from . import constants as K
from .geo import sun

deg = math.degrees


def terminator(day, utc_time):
    """Day/night boundary for a UTC date and time: sub-solar point and the polygon of the night side ([lon, lat])."""
    hours = utc_time.hour + utc_time.minute / 60.0 + utc_time.second / 3600.0
    jd = day.toordinal() + K.JD_AT_ORDINAL_ZERO_NOON + (hours - 12.0) / 24.0          # Julian date of that instant
    decl, lon_sub, eot = sun.subsolar_point(jd)
    ring = sun.night_ring(decl, lon_sub, K.TERMINATOR_SAMPLES)
    return {
        "date": day.isoformat(),
        "time": utc_time.strftime("%H:%M"),
        "subsolar": {"lat": round(deg(decl), 6), "lon": round(deg(lon_sub), 6)},
        "declination_deg": round(deg(decl), 4),
        "eot_min": round(eot, 3),
        "polygon": [[round(deg(lon), 6), round(max(-89.9, min(89.9, deg(lat))), 6)] for lat, lon in ring],
    }
