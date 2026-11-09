"""Civil time zones: which IANA zone is a point in, and what is its UTC offset on a date.

Zone lookup uses the hand-written ray casting in geo/pip.py over bundled, simplified
timezone-boundary-builder polygons (backend/app/data/timezones.json). UTC offsets (with daylight
saving) come from the standard library's zoneinfo (+ the tzdata package).
"""
import datetime as dt
import json
import os
import zoneinfo
from functools import lru_cache
from zoneinfo import ZoneInfo

import tzdata

from .geo.pip import bbox_of, point_in_polygon

# Always use the bundled `tzdata` package (a known IANA release) instead of whatever tz database the
# operating system happens to have, so results are reproducible on every machine.
zoneinfo.reset_tzpath(to=[])

_DATA = os.path.join(os.path.dirname(__file__), "data", "timezones.json")


@lru_cache(maxsize=1)
def _load():
    """Returns a list of (tzid, [(bbox, rings), ...])."""
    with open(_DATA, encoding="utf-8") as fh:
        raw = json.load(fh)
    zones = []
    for z in raw["zones"]:
        zones.append((z["tzid"], [(bbox_of(rings), rings) for rings in z["polygons"]]))
    return zones


def tz_database_version():
    """IANA tz database release the offsets come from, e.g. '2026f'."""
    return tzdata.IANA_VERSION


def find_zone(lat_deg, lon_deg):
    """IANA zone id containing the point, or None (open ocean / outside all polygons)."""
    for tzid, polys in _load():
        for (x0, y0, x1, y1), rings in polys:
            if x0 <= lon_deg <= x1 and y0 <= lat_deg <= y1 and point_in_polygon(lon_deg, lat_deg, rings):
                return tzid
    return None


def utc_offset_hours(tzid, day):
    """UTC offset in hours of zone tzid at 12:00 UTC on the given date (daylight saving included)."""
    when = dt.datetime(day.year, day.month, day.day, 12, 0, tzinfo=dt.timezone.utc)
    off = when.astimezone(ZoneInfo(tzid)).utcoffset()
    return off.total_seconds() / 3600.0


def zone_info(lat_deg, lon_deg, day):
    """Returns dict: tzid (or None), offset_h, nominal (True if the ocean fallback round(lon/15) was used)."""
    tzid = find_zone(lat_deg, lon_deg)
    if tzid is None:
        return {"tzid": None, "offset_h": float(round(lon_deg / 15.0)), "nominal": True}
    return {"tzid": tzid, "offset_h": utc_offset_hours(tzid, day), "nominal": False}
