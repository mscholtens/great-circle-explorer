"""Pydantic request/response models for the API."""
import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field

from .constants import DATE_MAX, DATE_MIN


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)


class Options(BaseModel):
    cruise_kmh: Optional[float] = Field(default=None, gt=0, le=1e6, allow_inf_nan=False)
    climb_descent_min: Optional[float] = Field(default=None, ge=0, le=1e4, allow_inf_nan=False)
    taxi_min: Optional[float] = Field(default=None, ge=0, le=1e4, allow_inf_nan=False)
    # Sun and time-zone metrics: 1 Jan 1970 .. 31 Dec 2049 (time-zone rules are extrapolated beyond today)
    date: Optional[dt.date] = Field(default=None, ge=DATE_MIN, le=DATE_MAX)
    height_a_m: Optional[float] = Field(default=None, ge=0, le=1e7, allow_inf_nan=False)
    height_b_m: Optional[float] = Field(default=None, ge=0, le=1e7, allow_inf_nan=False)


class CalculateRequest(BaseModel):
    a: Point
    b: Point
    options: Options = Field(default_factory=Options)


class Step(BaseModel):
    label: str
    tex: Optional[str] = None
    substituted_tex: Optional[str] = None
    result: Optional[str] = None


class ConstantRef(BaseModel):
    symbol: str
    value: str
    meaning: str


class Explanation(BaseModel):
    summary: str
    steps: list[Step]
    constants: list[ConstantRef] = []
    notes: list[str] = []


class TableRow(BaseModel):
    label: str
    display: str


class Metric(BaseModel):
    id: str
    group: str
    label: str
    value: Optional[float] = None  # primary scalar; null when undefined or when no single scalar exists
    unit: Optional[str] = None
    display: str
    secondary: list[str] = []
    table: Optional[list[TableRow]] = None
    explanation: Explanation


class Paths(BaseModel):
    great_circle: list[list[float]]
    rhumb: list[list[float]]


class Crossing(BaseModel):
    id: str
    label: str
    lat: float
    lon: float
    km_from_a: float
    fraction: float                         # share of the route length, 0..1
    course_deg: Optional[float] = None      # azimuth of the route at that point (null at a pole)


class Markers(BaseModel):
    midpoint: Optional[Point] = None
    vertex: Optional[Point] = None
    antipode_a: Optional[Point] = None
    antipode_b: Optional[Point] = None
    crossings: list[Crossing] = []


class CalculateResponse(BaseModel):
    a: Point
    b: Point
    warnings: list[str]
    paths: Paths
    markers: Markers
    metrics: list[Metric]
