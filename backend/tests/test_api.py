"""API tests: shape, validation, edge cases, timezones."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app import timezones
from app.main import app

client = TestClient(app)

IDS = ["distance_haversine", "ellipsoid_lambert", "mercator_distortion", "midpoint", "vertex_latitude",
       "crossings", "rhumb_line", "antipodes", "chord_and_bulge", "gravity_train", "flight_time",
       "bearing_initial", "bearing_final", "latency", "travel_times", "horizon_los", "solar_offset",
       "timezone_diff", "sun_a", "sun_b"]


def post(a, b, **options):
    return client.post("/api/calculate", json={"a": {"lat": a[0], "lon": a[1]}, "b": {"lat": b[0], "lon": b[1]},
                                               "options": options})


def by_id(body):
    return {m["id"]: m for m in body["metrics"]}


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_dusseldorf_new_york_full_shape():
    r = post((51.2277, 6.7735), (40.6413, -73.7781), date="2026-11-09")
    assert r.status_code == 200
    body = r.json()
    assert [m["id"] for m in body["metrics"]] == IDS
    for m in body["metrics"]:
        assert len(m["explanation"]["steps"]) >= 1, m["id"]
        assert m["display"], m["id"]
    m = by_id(body)
    assert 6000 < m["distance_haversine"]["value"] < 6300
    assert m["vertex_latitude"]["value"] > 51.2277           # route arcs north
    assert body["markers"]["vertex"] is not None
    assert len(body["paths"]["great_circle"]) == 129
    assert body["warnings"] == []
    assert by_id(body)["timezone_diff"]["value"] == -6.0       # CET -> EST in November
    tz = m["timezone_diff"]["secondary"]
    assert "Europe/Berlin" in tz[0] and "America/New_York" in tz[1]


@pytest.mark.parametrize("a,b", [((91, 0), (0, 0)), ((0, 0), (0, 181)), ((-91, 0), (0, 0)), ((0, -181), (0, 0))])
def test_out_of_range_is_422(a, b):
    assert post(a, b).status_code == 422


def test_identical_points():
    body = post((10, 20), (10, 20)).json()
    m = by_id(body)
    assert m["distance_haversine"]["value"] == 0
    assert m["bearing_initial"]["value"] is None
    assert body["paths"]["great_circle"] == [] and body["paths"]["rhumb"] == []
    assert body["warnings"]
    for x in body["metrics"]:
        assert len(x["explanation"]["steps"]) >= 1


def test_antipodal_points():
    body = post((0, 0), (0, 180)).json()
    m = by_id(body)
    import math
    assert m["distance_haversine"]["value"] == pytest.approx(math.pi * 6371.0088, abs=1e-3)
    assert m["bearing_initial"]["value"] is None
    assert m["midpoint"]["value"] is None
    assert body["markers"]["midpoint"] is None
    assert body["paths"]["great_circle"] == []
    assert any("antipodal" in w for w in body["warnings"])
    assert m["chord_and_bulge"]["value"] == pytest.approx(2 * 6371.0088)


def test_pole_points():
    body = post((90, 0), (0, 0)).json()
    m = by_id(body)
    assert m["bearing_initial"]["value"] is None
    assert m["rhumb_line"]["value"] is None
    assert m["mercator_distortion"]["value"] is None
    assert m["sun_a"]["value"] is not None
    assert body["paths"]["rhumb"] == []
    assert len(body["paths"]["great_circle"]) == 129


def test_antimeridian_path_continuous():
    body = post((35.7, 139.7), (37.8, -122.4)).json()
    lons = [p[0] for p in body["paths"]["great_circle"]]
    assert all(abs(b - a) < 20 for a, b in zip(lons, lons[1:]))
    lons = [p[0] for p in body["paths"]["rhumb"]]
    assert all(abs(b - a) < 20 for a, b in zip(lons, lons[1:]))


def test_options_are_used():
    slow = by_id(post((0, 0), (0, 90), cruise_kmh=500, climb_descent_min=0, taxi_min=0).json())["flight_time"]["value"]
    assert slow == pytest.approx(10007.56 / 500, rel=1e-4)


def test_sun_polar_states():
    m = by_id(post((80, 0), (80, 10), date="2026-06-21").json())
    assert "polar day" in m["sun_a"]["display"]
    m = by_id(post((80, 0), (80, 10), date="2026-12-21").json())
    assert "polar night" in m["sun_a"]["display"]


def test_timezone_lookup():
    day = dt.date(2026, 1, 15)
    assert timezones.find_zone(51.2277, 6.7735) == "Europe/Berlin"
    assert timezones.find_zone(35.68, 139.69) == "Asia/Tokyo"
    assert timezones.find_zone(-33.87, 151.21) == "Australia/Sydney"
    assert timezones.find_zone(0.0, -140.0) is None          # open Pacific
    assert timezones.zone_info(0.0, -140.0, day) == {"tzid": None, "offset_h": -9.0, "nominal": True}


def test_dst_changes_offset():
    jan = timezones.zone_info(52.52, 13.4, dt.date(2026, 1, 15))["offset_h"]
    jul = timezones.zone_info(52.52, 13.4, dt.date(2026, 7, 15))["offset_h"]
    assert (jan, jul) == (1.0, 2.0)


def test_geo_package_imports_only_math():
    import pathlib
    import re
    geo = pathlib.Path(__file__).resolve().parents[1] / "app" / "geo"
    for f in geo.glob("*.py"):
        for line in f.read_text().splitlines():
            m = re.match(r"\s*(?:import|from)\s+([\w.]+)", line)
            if m:
                mod = m.group(1)
                assert mod == "math" or mod.startswith("."), f"{f.name}: {line}"


# ---------------------------------------------------------------- crossings, flight time, courses, dates
def test_cologne_to_santiago_crossings():
    body = post((50.8659, 7.1427), (-33.393, -70.7858), date="2026-11-09").json()
    m = by_id(body)["crossings"]
    rows = {r["label"]: r["display"] for r in m["table"]}
    assert set(rows) == {"Prime meridian (0°)", "Tropic of Cancer", "Equator", "Tropic of Capricorn"}
    assert m["display"] == "4 crossings"
    assert "Arctic Circle" in m["secondary"][0] and "180° meridian" in m["secondary"][0]
    cr = {c["id"]: c for c in body["markers"]["crossings"]}
    assert [c["id"] for c in body["markers"]["crossings"]] == ["prime_meridian", "tropic_cancer", "equator", "tropic_capricorn"]
    assert cr["equator"]["lat"] == pytest.approx(0.0, abs=1e-6) and cr["equator"]["lon"] == pytest.approx(-45.54, abs=0.05)
    assert cr["equator"]["km_from_a"] == pytest.approx(7506, abs=5)
    assert cr["tropic_cancer"]["lat"] == pytest.approx(23.44, abs=1e-6)
    assert cr["prime_meridian"]["lon"] == pytest.approx(0.0, abs=1e-9) and cr["prime_meridian"]["lat"] == pytest.approx(47.80, abs=0.01)
    assert all(0 < c["fraction"] < 1 and 180 < c["course_deg"] < 270 for c in cr.values())
    assert all(len(s["label"]) > 0 for s in m["explanation"]["steps"]) and len(m["explanation"]["steps"]) >= 8


def test_polar_route_crosses_the_polar_circle_and_tokyo_the_date_line():
    body = post((52.4, 4.9), (61.2, -149.9)).json()          # Amsterdam -> Anchorage goes far north
    ids = [c["id"] for c in body["markers"]["crossings"]]
    assert "arctic_circle" in ids
    body = post((35.7, 139.7), (37.8, -122.4)).json()
    assert [c["id"] for c in body["markers"]["crossings"]].count("antimeridian") == 1


def test_crossings_undefined_for_identical_and_antipodal_points():
    for a, b in [((10, 20), (10, 20)), ((0, 0), (0, 180))]:
        body = post(a, b).json()
        m = by_id(body)["crossings"]
        assert m["value"] is None and m["display"] == "undefined" and body["markers"]["crossings"] == []


def test_route_along_the_equator_is_reported_as_along():
    body = post((0, 10), (0, 80)).json()
    m = by_id(body)["crossings"]
    assert any(r["label"] == "Equator" and "along" in r["display"] for r in m["table"])


def test_route_from_a_pole_still_has_crossings():
    body = post((90, 0), (-30, 40)).json()                   # north pole -> southern hemisphere
    ids = [c["id"] for c in body["markers"]["crossings"]]
    assert "arctic_circle" in ids and "equator" in ids and "tropic_cancer" in ids


def test_flight_time_is_split_into_airborne_and_gate_to_gate():
    m = by_id(post((0, 0), (0, 90), cruise_kmh=500, climb_descent_min=20, taxi_min=10).json())["flight_time"]
    cruise_h = 10007.56 / 500
    assert m["value"] == pytest.approx(cruise_h + 20 / 60, rel=1e-4)            # airborne, no taxiing
    assert "in the air" in m["display"]
    gate = [s for s in m["secondary"] if s.startswith("gate to gate")][0]
    total_min = round((cruise_h + 30 / 60) * 60)
    assert f"{total_min // 60} h {total_min % 60:02d} min" in gate
    assert len(m["explanation"]["steps"]) == 3
    default = by_id(post((0, 0), (0, 90)).json())["flight_time"]
    assert default["value"] == pytest.approx(10007.56 / 850 + 15 / 60, rel=1e-4)


def test_courses_sit_in_travel_after_the_flight_time():
    body = post((50.8659, 7.1427), (-33.393, -70.7858)).json()
    ids = [m["id"] for m in body["metrics"]]
    assert ids[ids.index("flight_time") + 1:ids.index("flight_time") + 3] == ["bearing_initial", "bearing_final"]
    m = by_id(body)
    assert m["bearing_initial"]["group"] == m["bearing_final"]["group"] == "Travel"
    assert m["bearing_initial"]["label"].startswith("Course after take-off")
    assert m["bearing_final"]["label"].startswith("Course before landing")
    assert m["bearing_initial"]["value"] == pytest.approx(239.4, abs=0.1)
    assert m["bearing_final"]["value"] == pytest.approx(220.6, abs=0.1)
    assert "to the left" in m["bearing_final"]["secondary"][1]
    assert any("runway" in n.lower() for n in m["bearing_initial"]["explanation"]["notes"])


def test_date_is_limited_to_1970_2049():
    for d in ("1970-01-01", "2049-12-31", "2026-11-09"):
        assert post((51, 7), (40, -73), date=d).status_code == 200
    for d in ("1969-12-31", "2050-01-01"):
        assert post((51, 7), (40, -73), date=d).status_code == 422


def test_time_zone_offsets_over_the_years_and_the_future():
    cases = {"1970-07-15": 1.0, "1985-07-15": 2.0, "2049-07-15": 2.0, "2049-12-31": 1.0}   # Berlin
    for d, off in cases.items():
        assert timezones.zone_info(52.52, 13.4, dt.date.fromisoformat(d))["offset_h"] == off
    assert timezones.zone_info(-33.45, -70.67, dt.date(2026, 1, 15))["offset_h"] == -3.0       # Santiago, southern summer
    assert timezones.zone_info(-33.45, -70.67, dt.date(2026, 7, 15))["offset_h"] == -4.0


def test_time_zone_card_states_that_rules_are_todays_and_may_change():
    m = by_id(post((51.2277, 6.7735), (40.6413, -73.7781), date="2049-07-15").json())["timezone_diff"]
    notes = " ".join(m["explanation"]["notes"])
    assert timezones.tz_database_version() in notes and "today's rules" in notes
    assert "political decisions" in notes and "1 January 1970 to 31 December 2049" in notes
    assert "2049-07-15" in m["secondary"][2] and "future changes unknown" in m["secondary"][2]
    assert m["value"] == -6.0


def test_system_tz_database_is_not_used():
    import zoneinfo
    assert zoneinfo.TZPATH == ()


def test_coordinates_at_zero_have_no_hemisphere_letter():
    from app.explain import latlon_text
    assert latlon_text(0.0, 0.0) == "0.0000°, 0.0000°"
    assert latlon_text(-1e-14, 1e-14, 3) == "0.000°, 0.000°"
    assert latlon_text(47.803, 0.0, 2) == "47.80°N, 0.00°"
    assert latlon_text(-33.393, -180.0, 2) == "33.39°S, 180.00°"
    assert latlon_text(51.2277, 6.7735) == "51.2277°N, 6.7735°E"
    body = post((50.8659, 7.1427), (-33.393, -70.7858)).json()
    steps = by_id(body)["crossings"]["explanation"]["steps"]
    prime = [s for s in steps if s["label"].startswith("Prime meridian")][0]
    assert "°N, 0.000° ·" in prime["result"]          # no stray "0.000°W"
    equator = [s for s in steps if s["label"] == "Equator"][0]
    assert equator["result"].startswith("0.000°, 45.5")
