"""Bundled airports and cities: search by code/name and nearest place to a point. Offline (data/places.json).

Lives outside geo/ (it loads a file); the distances use the hand-written haversine from geo/spherical.py.
"""
import json
import math
import os
import unicodedata

from . import constants as K
from .geo import spherical

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "places.json")
_PLACES = None


def _norm(text):
    """Lower-case without accents: 'Köln' -> 'koln'."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def _load():
    global _PLACES
    if _PLACES is None:
        with open(_PATH, encoding="utf-8") as fh:
            raw = json.load(fh)["places"]
        _PLACES = []
        for p in raw:
            q = dict(p)
            q["label"] = f"{p['code']} · {p['name']}" if p["kind"] == "airport" else p["name"]
            q["detail"] = ", ".join(x for x in (p["city"], p["country"]) if x)
            q["_code"] = p["code"].lower()
            q["_name"] = _norm(p["name"])
            q["_city"] = _norm(p["city"])
            q["_lat"], q["_lon"] = math.radians(p["lat"]), math.radians(p["lon"])
            _PLACES.append(q)
    return _PLACES


def _public(p, km=None):
    out = {k: p[k] for k in ("kind", "code", "name", "city", "country", "lat", "lon", "label", "detail")}
    if km is not None:
        out["km"] = round(km, 3)
    return out


def _score(p, q):
    """Lower is better; None = no match. Exact code, code prefix, name/city prefix, word prefix, substring."""
    if p["_code"] and p["_code"] == q:
        return 0
    if p["_code"] and len(q) >= 2 and p["_code"].startswith(q):
        return 1
    for field in (p["_name"], p["_city"]):
        if field.startswith(q):
            return 2
    for field in (p["_name"], p["_city"]):
        if any(w.startswith(q) for w in field.replace("-", " ").split()):
            return 3
    if len(q) >= 3 and (q in p["_name"] or q in p["_city"]):
        return 4
    return None


def airports():
    """All bundled airports (for the airports layer on the map): code, name, city, country, lat, lon."""
    return [{k: p[k] for k in ("code", "name", "city", "country", "lat", "lon")} for p in _load() if p["kind"] == "airport"]


def search(query, limit=8):
    """Best matches for a code, airport name or city name (accents and case ignored)."""
    q = _norm(query)
    if not q:
        return []
    scored = []
    for p in _load():
        s = _score(p, q)
        if s is not None:
            scored.append((s, 0 if p["kind"] == "airport" else 1, p["name"], p))
    scored.sort(key=lambda t: t[:3])
    return [_public(t[3]) for t in scored[:limit]]


def nearest(lat_deg, lon_deg):
    """Nearest airport and nearest city to a point, each with the distance in km (haversine)."""
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    best = {"airport": (None, 1e18), "city": (None, 1e18)}
    for p in _load():
        _, delta = spherical.haversine(lat, lon, p["_lat"], p["_lon"])
        if delta < best[p["kind"]][1]:
            best[p["kind"]] = (p, delta)
    return {kind: (None if p is None else _public(p, K.R_KM * delta)) for kind, (p, delta) in best.items()}
