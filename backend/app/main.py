"""FastAPI application: health check, /api/calculate, /api/terminator, /api/places, /api/airports, /api/nearest, /api/units."""
import datetime as dt

from fastapi import FastAPI, Query

from . import places
from .constants import DATE_MAX, DATE_MIN, UNIT_ORDER, UNITS
from .metrics import calculate, destination_point
from .models import Airport, CalculateRequest, CalculateResponse, Nearest, Place, Point, Terminator, UnitInfo
from .overlays import terminator

app = FastAPI(title="Great Circle Explorer", version="0.1.0")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/calculate", response_model=CalculateResponse)
def calculate_endpoint(req: CalculateRequest):
    o = req.options
    b, project_bearing, project_km = req.b, o.project_bearing_deg, o.project_km
    if req.course is not None:        # inverse mode: B is computed from A, the bearing and the distance
        b_lat, b_lon = destination_point(req.a.lat, req.a.lon, req.course.bearing_deg, req.course.km)
        b = Point(lat=b_lat, lon=b_lon)
        project_bearing, project_km = req.course.bearing_deg, req.course.km
    return calculate(req.a.lat, req.a.lon, b.lat, b.lon,
                     cruise_kmh=o.cruise_kmh, climb_descent_min=o.climb_descent_min, taxi_min=o.taxi_min, day=o.date,
                     height_a_m=o.height_a_m, height_b_m=o.height_b_m,
                     project_bearing_deg=project_bearing, project_km=project_km,
                     include_return=o.include_return, circle_km=o.circle_km, units=o.units)


@app.get("/api/terminator", response_model=Terminator)
def terminator_endpoint(date: dt.date = Query(ge=DATE_MIN, le=DATE_MAX), time: dt.time = Query()):
    """Night side of the Earth at a UTC date and time (sun on the horizon along the boundary)."""
    return terminator(date, time)


@app.get("/api/places", response_model=list[Place])
def places_endpoint(q: str = Query(min_length=1, max_length=80), limit: int = Query(8, ge=1, le=20)):
    """Airports (IATA code) and cities matching a code or name, best first."""
    return places.search(q, limit)


@app.get("/api/nearest", response_model=Nearest)
def nearest_endpoint(lat: float = Query(ge=-90, le=90, allow_inf_nan=False),
                     lon: float = Query(ge=-180, le=180, allow_inf_nan=False)):
    """Nearest airport and nearest city to a point, with the distance in km."""
    return places.nearest(lat, lon)


@app.get("/api/units", response_model=list[UnitInfo])
def units_endpoint():
    """Distance/speed units and their size in km (so the frontend never repeats a conversion factor)."""
    return [{"id": u, **UNITS[u]} for u in UNIT_ORDER]


@app.get("/api/airports", response_model=list[Airport])
def airports_endpoint():
    """Every bundled airport (IATA code, name, city, country, coordinates), for the airports layer on the map."""
    return places.airports()
