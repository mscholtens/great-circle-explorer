"""FastAPI application: health check and the /api/calculate endpoint."""
from fastapi import FastAPI

from .metrics import calculate
from .models import CalculateRequest, CalculateResponse

app = FastAPI(title="Great Circle Explorer", version="0.1.0")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/calculate", response_model=CalculateResponse)
def calculate_endpoint(req: CalculateRequest):
    o = req.options
    return calculate(req.a.lat, req.a.lon, req.b.lat, req.b.lon,
                     cruise_kmh=o.cruise_kmh, climb_descent_min=o.climb_descent_min, taxi_min=o.taxi_min, day=o.date,
                     height_a_m=o.height_a_m, height_b_m=o.height_b_m)
