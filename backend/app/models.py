"""Pydantic request/response models for the API."""
import datetime as dt
import math
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .constants import DATE_MAX, DATE_MIN, R_KM


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
    # Direct problem: both must be given to get the "destination" metric (starting at A)
    project_bearing_deg: Optional[float] = Field(default=None, ge=0, le=360, allow_inf_nan=False)
    project_km: Optional[float] = Field(default=None, ge=0, le=1e5, allow_inf_nan=False)
    include_return: bool = False                 # adds the "return trip" metric
    # Radius of the circles of equal distance around A and B (default: the route length), up to half the circumference
    circle_km: Optional[float] = Field(default=None, ge=0, le=math.pi * R_KM, allow_inf_nan=False)
    units: Optional[Literal["km", "nm", "mi"]] = None   # distance/speed unit of the cards (calculations stay in km)


class Course(BaseModel):
    """Inverse mode: instead of a second point, a true bearing and a distance from A."""
    bearing_deg: float = Field(ge=0, le=360, allow_inf_nan=False)
    km: float = Field(ge=0, le=1e5, allow_inf_nan=False)


class CalculateRequest(BaseModel):
    a: Point
    b: Optional[Point] = None          # give B ...
    course: Optional[Course] = None    # ... or a course and distance from A (then B is computed and returned)
    options: Options = Field(default_factory=Options)

    @model_validator(mode="after")
    def exactly_one_of_b_and_course(self):
        if (self.b is None) == (self.course is None):
            raise ValueError("give either point b or a course (bearing and distance), not both and not neither")
        return self


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


class AnalysisRow(BaseModel):
    id: str
    label: str
    what: str                                  # one line: what this measure is
    km: Optional[float] = None                 # null when the measure is undefined for this pair (then `display` says why)
    display: str
    diff_km: Optional[float] = None            # difference to the reference
    diff_display: Optional[str] = None
    diff_pct: Optional[float] = None
    is_reference: bool = False
    model: str = "sphere"                       # "ellipsoid" or "sphere": which model of the Earth the row assumes
    badges: list[str] = []                     # "reference", "conventional"
    vs_sphere_km: Optional[float] = None       # sphere-based methods: difference to the great circle on the same sphere
    vs_sphere_pct: Optional[float] = None
    vs_sphere_display: Optional[str] = None
    metric_id: Optional[str] = None            # the metric whose calculation a click opens ...
    explanation: Optional[Explanation] = None  # ... or an own calculation (the grid measure)


class Analysis(BaseModel):
    reference_id: str
    reference_label: str
    rows: list[AnalysisRow]
    summary: list[str] = []                    # what changes the answer: the Earth model, the method
    footnotes: list[str] = []


class Metric(BaseModel):
    id: str
    group: str
    label: str
    value: Optional[float] = None  # primary scalar; null when undefined or when no single scalar exists
    unit: Optional[str] = None
    display: str
    secondary: list[str] = []
    table: Optional[list[TableRow]] = None
    analysis: Optional[Analysis] = None        # only the distance analysis metric
    explanation: Explanation


class Paths(BaseModel):
    great_circle: list[list[float]]
    rhumb: list[list[float]]
    projection: list[list[float]] = []      # A -> projected point (empty unless the projection options are set)


class Crossing(BaseModel):
    id: str
    label: str
    lat: float
    lon: float
    km_from_a: float
    fraction: float                         # share of the route length, 0..1
    course_deg: Optional[float] = None      # azimuth of the route at that point (null at a pole)


class Projected(BaseModel):
    lat: float
    lon: float
    bearing_deg: float
    km: float


class Circle(BaseModel):
    center: str                              # "a" or "b"
    radius_km: float
    segments: list[list[list[float]]]        # polylines of [lon, lat], cut at the antimeridian


class Place(BaseModel):
    kind: str                                # "airport" or "city"
    code: str                                # IATA code (airports) or ""
    name: str
    city: str
    country: str
    lat: float
    lon: float
    label: str
    detail: str


class Airport(BaseModel):
    code: str
    name: str
    city: str
    country: str
    lat: float
    lon: float


class NearPlace(Place):
    km: float


class Nearest(BaseModel):
    airport: Optional[NearPlace] = None
    city: Optional[NearPlace] = None


class UnitInfo(BaseModel):
    id: str
    label: str
    speed_label: str
    km_per_unit: float


class Terminator(BaseModel):
    date: str
    time: str
    subsolar: Point
    declination_deg: float
    eot_min: float
    polygon: list[list[float]]               # night side, [lon, lat]


class Markers(BaseModel):
    midpoint: Optional[Point] = None
    vertex: Optional[Point] = None
    antipode_a: Optional[Point] = None
    antipode_b: Optional[Point] = None
    crossings: list[Crossing] = []
    projected: Optional[Projected] = None


class CalculateResponse(BaseModel):
    a: Point
    b: Point
    warnings: list[str]
    paths: Paths
    markers: Markers
    circles: list[Circle] = []
    metrics: list[Metric]
