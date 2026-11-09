"""One-time data preparation (needs internet; the app itself never does).

Downloads and builds the bundled data files, which are then committed:

  frontend/public/data/countries.json   Natural Earth 50m country polygons (public domain)
  frontend/public/data/labels.json      one label point per country
  frontend/public/fonts/Noto Sans Regular/*.pbf   glyph ranges for map labels (SIL OFL)
  backend/app/data/timezones.json       simplified timezone-boundary-builder polygons (ODbL)
  backend/app/data/places.json          airports (OurAirports, public domain) and larger cities (Natural Earth)

Usage:  python3 tools/fetch_data.py [countries] [fonts] [timezones] [places]   (default: all)
Only the standard library is used. Polygon simplification (Douglas-Peucker) is hand-written.
"""
import csv
import io
import json
import math
import os
import sys
import urllib.parse
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NE_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
          "geojson/ne_50m_admin_0_countries.geojson")
TZ_URL = ("https://github.com/evansiroky/timezone-boundary-builder/releases/download/"
          "2026f/timezones.geojson.zip")
AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
CITIES_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
              "geojson/ne_10m_populated_places_simple.geojson")
CITY_MIN_POPULATION = 300000
FONT_BASE = "https://demotiles.maplibre.org/font/"
FONT_STACK = "Noto Sans Regular"
FONT_RANGES = ["0-255", "256-511", "512-767", "7680-7935"]

TZ_TOLERANCE_DEG = 0.03   # Douglas-Peucker tolerance for timezone polygons (~3 km)
TZ_SMALL_RING_FRACTION = 20   # a ring is never simplified more coarsely than 1/20 of its own size (keeps small enclaves like Melilla)
NE_DECIMALS = 3
TZ_DECIMALS = 3


def download(url):
    print("downloading", url, flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "great-circle-explorer-data-prep"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


def douglas_peucker(points, tol):
    """Iterative Douglas-Peucker on a list of (x, y); returns the simplified list."""
    n = len(points)
    if n < 3:
        return list(points)
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        x1, y1 = points[i]
        x2, y2 = points[j]
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy
        best, idx = -1.0, -1
        for k in range(i + 1, j):
            px, py = points[k]
            if seg2 == 0:
                d = math.hypot(px - x1, py - y1)
            else:
                t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg2))
                d = math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
            if d > best:
                best, idx = d, k
        if best > tol:
            keep[idx] = True
            stack.append((i, idx))
            stack.append((idx, j))
    return [p for p, k in zip(points, keep) if k]


def simplify_ring(ring, tol, decimals):
    pts = [(p[0], p[1]) for p in ring]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    tol = min(tol, max(max(xs) - min(xs), max(ys) - min(ys)) / TZ_SMALL_RING_FRACTION)   # small rings keep their shape
    # anchor DP on the two points farthest apart so closed rings simplify well
    far = max(range(len(pts)), key=lambda k: (pts[k][0] - pts[0][0]) ** 2 + (pts[k][1] - pts[0][1]) ** 2)
    a = douglas_peucker(pts[: far + 1], tol)
    b = douglas_peucker(pts[far:] + [pts[0]], tol)
    out = a[:-1] + b[:-1]
    out = [[round(x, decimals), round(y, decimals)] for x, y in out]
    # drop consecutive duplicates created by rounding
    ded = [out[0]]
    for p in out[1:]:
        if p != ded[-1]:
            ded.append(p)
    if len(ded) < 3:
        return None
    return ded + [ded[0]]


def round_coords(coords, decimals):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], decimals), round(coords[1], decimals)]
    return [round_coords(c, decimals) for c in coords]


def build_countries():
    data = json.loads(download(NE_URL))
    features, labels = [], []
    for f in data["features"]:
        p = f["properties"]
        name = p.get("NAME_EN") or p.get("NAME") or p.get("ADMIN")
        features.append({
            "type": "Feature",
            "properties": {"name": name},
            "geometry": {"type": f["geometry"]["type"],
                         "coordinates": round_coords(f["geometry"]["coordinates"], NE_DECIMALS)},
        })
        lx, ly = p.get("LABEL_X"), p.get("LABEL_Y")
        if lx is None or ly is None:
            continue
        labels.append({
            "type": "Feature",
            "properties": {"name": name, "rank": p.get("LABELRANK", 5),
                           "minzoom": p.get("MIN_LABEL", 3)},
            "geometry": {"type": "Point", "coordinates": [round(lx, 3), round(ly, 3)]},
        })
    out = os.path.join(ROOT, "frontend", "public", "data")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "countries.json"), "w") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh, separators=(",", ":"))
    with open(os.path.join(out, "labels.json"), "w") as fh:
        json.dump({"type": "FeatureCollection", "features": labels}, fh, separators=(",", ":"), ensure_ascii=False)
    print("countries:", len(features), "labels:", len(labels))


def build_fonts():
    out = os.path.join(ROOT, "frontend", "public", "fonts", FONT_STACK)
    os.makedirs(out, exist_ok=True)
    for r in FONT_RANGES:
        url = FONT_BASE + urllib.parse.quote(FONT_STACK) + "/" + r + ".pbf"
        with open(os.path.join(out, r + ".pbf"), "wb") as fh:
            fh.write(download(url))
    print("fonts done")


def build_timezones():
    raw = download(TZ_URL)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = next(n for n in z.namelist() if n.endswith(".json") or n.endswith(".geojson"))
        data = json.loads(z.read(name))
    zones = []
    before = after = 0
    for f in data["features"]:
        tzid = f["properties"]["tzid"]
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        out_polys = []
        for poly in polys:
            rings = []
            for i, ring in enumerate(poly):
                before += len(ring)
                s = simplify_ring(ring, TZ_TOLERANCE_DEG, TZ_DECIMALS)
                if s is None:
                    if i == 0:
                        break          # outer ring vanished: drop the whole polygon
                    continue           # tiny hole: drop it
                after += len(s)
                rings.append(s)
            if rings:
                out_polys.append(rings)
        if out_polys:
            zones.append({"tzid": tzid, "polygons": out_polys})
        print(" ", tzid, flush=True) if len(zones) % 100 == 0 else None
    out = os.path.join(ROOT, "backend", "app", "data")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "timezones.json"), "w") as fh:
        json.dump({"zones": zones}, fh, separators=(",", ":"))
    print("timezones:", len(zones), "points", before, "->", after)


def build_places():
    """Airports with an IATA code and scheduled service (large and medium) plus cities of >= 300 000 people."""
    cities_raw = json.loads(download(CITIES_URL))["features"]
    country_names = {}
    for f in cities_raw:                                   # ISO code -> country name, from the same file
        p = f["properties"]
        if p.get("iso_a2") and p["iso_a2"] != "-99" and p.get("adm0name"):
            country_names.setdefault(p["iso_a2"], p["adm0name"])
    places = []
    reader = csv.DictReader(io.StringIO(download(AIRPORTS_URL).decode("utf-8")))
    for row in reader:
        if (row["type"] in ("large_airport", "medium_airport") and row["iata_code"]
                and row["scheduled_service"] == "yes"):
            places.append({"kind": "airport", "code": row["iata_code"], "name": row["name"],
                           "city": row["municipality"], "country": country_names.get(row["iso_country"], row["iso_country"]),
                           "lat": round(float(row["latitude_deg"]), 4), "lon": round(float(row["longitude_deg"]), 4)})
    n_airports = len(places)
    for f in cities_raw:
        p = f["properties"]
        if (p.get("pop_max") or 0) >= CITY_MIN_POPULATION:
            places.append({"kind": "city", "code": "", "name": p["name"], "city": "", "country": p.get("adm0name") or "",
                           "lat": round(p["latitude"], 4), "lon": round(p["longitude"], 4)})
    out = os.path.join(ROOT, "backend", "app", "data")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "places.json"), "w", encoding="utf-8") as fh:
        json.dump({"places": places}, fh, separators=(",", ":"), ensure_ascii=False)
    print("places:", n_airports, "airports,", len(places) - n_airports, "cities")


if __name__ == "__main__":
    what = sys.argv[1:] or ["countries", "fonts", "timezones", "places"]
    if "countries" in what:
        build_countries()
    if "fonts" in what:
        build_fonts()
    if "timezones" in what:
        build_timezones()
    if "places" in what:
        build_places()
