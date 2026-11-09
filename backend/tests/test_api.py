"""API tests: shape, validation, edge cases, timezones."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app import timezones
from app.main import app

client = TestClient(app)

IDS = ["distance_haversine", "distance_analysis", "ellipsoid_vincenty", "ellipsoid_lambert", "mercator_distortion", "midpoint", "vertex_latitude",
       "crossings", "rhumb_line", "rhumb_vs_great_circle", "antipodes", "earth_scale", "chord_and_bulge",
       "gravity_train", "flight_time", "bearing_initial", "bearing_final", "latency", "travel_times",
       "horizon_los", "solar_offset", "timezone_diff", "sun_a", "sun_b", "moon_phase"]
OPTIONAL = {"destination", "return_trip"}


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
    assert timezones.zone_info(0.0, -140.0, day) == {"tzid": None, "offset_h": -9.0, "nominal": True, "near_km": None}


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


CGN, SCL = (50.8659, 7.1427), (-33.393, -70.7858)


def test_optional_metrics_are_absent_by_default_and_present_with_options():
    body = post(CGN, SCL).json()
    assert OPTIONAL.isdisjoint(by_id(body))
    assert body["markers"]["projected"] is None and body["paths"]["projection"] == []
    body = post(CGN, SCL, project_bearing_deg=90, project_km=1000, include_return=True).json()
    ids = [m["id"] for m in body["metrics"]]
    assert set(ids) == set(IDS) | OPTIONAL
    assert ids.index("destination") == ids.index("earth_scale") + 1
    assert ids.index("return_trip") == ids.index("bearing_final") + 1
    only_one = post(CGN, SCL, project_bearing_deg=90).json()      # both fields are needed
    assert "destination" not in by_id(only_one)


def test_destination_metric_and_marker():
    body = post((0, 0), (0, 10), project_bearing_deg=90, project_km=10007.5604).json()   # a quarter of the equator
    m = body["markers"]["projected"]
    assert m["lat"] == pytest.approx(0, abs=1e-6) and m["lon"] == pytest.approx(90, abs=1e-4)
    assert by_id(body)["destination"]["display"].startswith("0.000°, 90.000°")
    assert len(body["paths"]["projection"]) == 65
    north = post((0, 0), (0, 10), project_bearing_deg=0, project_km=10007.5604).json()["markers"]["projected"]
    assert north["lat"] == pytest.approx(90, abs=1e-4)
    zero = post(CGN, SCL, project_bearing_deg=123, project_km=0).json()["markers"]["projected"]
    assert (zero["lat"], zero["lon"]) == pytest.approx(CGN, abs=1e-6)


def test_destination_from_the_route_bearing_and_distance_reaches_b():
    body = post(CGN, SCL).json()
    m = by_id(body)
    brg, dist_km = m["bearing_initial"]["value"], m["distance_haversine"]["value"]
    p = post(CGN, SCL, project_bearing_deg=brg, project_km=dist_km).json()["markers"]["projected"]
    assert p["lat"] == pytest.approx(SCL[0], abs=1e-3) and p["lon"] == pytest.approx(SCL[1], abs=1e-3)


@pytest.mark.parametrize("opts", [{"project_bearing_deg": -1}, {"project_bearing_deg": 361}, {"project_km": -5},
                                  {"circle_km": -1}, {"circle_km": 20016}])
def test_new_options_are_validated(opts):
    assert post(CGN, SCL, **opts).status_code == 422


def test_courses_have_radian_and_hour_angle_steps():
    m = by_id(post(CGN, SCL).json())
    for mid, deg_value in (("bearing_initial", 239.4), ("bearing_final", 220.6)):
        steps = m[mid]["explanation"]["steps"]
        assert [s["label"] for s in steps][-2:] == ["In radians", "As an hour angle (the Earth turns 15° per hour)"]
        assert f"{deg_value / 15:.2f}" in steps[-1]["result"] or f"{deg_value / 15:.1f}" in steps[-1]["result"]
        assert any("hour angle" in line for line in m[mid]["secondary"])
        assert any("not a travel time" in n for n in m[mid]["explanation"]["notes"])


def test_rhumb_comparison():
    m = by_id(post(CGN, SCL).json())["rhumb_vs_great_circle"]
    gc = by_id(post(CGN, SCL).json())["distance_haversine"]["value"]
    rh = by_id(post(CGN, SCL).json())["rhumb_line"]["value"]
    assert m["value"] == pytest.approx(rh - gc, abs=1e-6) and m["value"] > 0
    assert by_id(post((0, 10), (0, 80)).json())["rhumb_vs_great_circle"]["display"] == "no difference"
    assert by_id(post((10, 0), (50, 0)).json())["rhumb_vs_great_circle"]["display"] == "no difference"
    assert by_id(post((90, 0), (0, 0)).json())["rhumb_vs_great_circle"]["value"] is None
    assert by_id(post((10, 20), (10, 20)).json())["rhumb_vs_great_circle"]["value"] is None


def test_earth_scale():
    m = by_id(post((0, 0), (0, 180)).json())["earth_scale"]
    assert m["value"] == pytest.approx(50.0)
    assert m["display"].startswith("50.0 %")
    m = by_id(post((0, 0), (0, 90)).json())["earth_scale"]
    assert m["value"] == pytest.approx(25.0)
    same = by_id(post((5, 5), (5, 5)).json())["earth_scale"]
    assert same["value"] == 0 and not any("fit around" in s for s in same["secondary"])


def test_return_trip():
    body = post(CGN, SCL, include_return=True).json()
    m = by_id(body)
    back = m["return_trip"]
    assert back["value"] == pytest.approx((m["bearing_final"]["value"] + 180) % 360, abs=1e-6)
    assert back["display"].endswith(f"{(m['bearing_initial']['value'] + 180) % 360:.1f}°")
    assert m["flight_time"]["display"].split(" in the air")[0] in back["secondary"][1]
    # undefined where the bearings are
    assert by_id(post((10, 20), (10, 20), include_return=True).json())["return_trip"]["value"] is None


def test_circles_of_equal_distance():
    body = post(CGN, SCL).json()
    d = by_id(body)["distance_haversine"]["value"]
    assert [c["center"] for c in body["circles"]] == ["a", "b"]
    assert body["circles"][0]["radius_km"] == pytest.approx(d, abs=1e-2)
    circle_a = body["circles"][0]["segments"]
    import math as m_
    for seg in circle_a:                       # every vertex is the same distance from A as the route is long
        for lon, lat in seg[1:-1]:
            hav = lambda la1, lo1, la2, lo2: 6371.0088 * 2 * m_.asin(m_.sqrt(  # noqa: E731
                m_.sin(m_.radians(la2 - la1) / 2) ** 2 + m_.cos(m_.radians(la1)) * m_.cos(m_.radians(la2)) * m_.sin(m_.radians(lo2 - lo1) / 2) ** 2))
            assert hav(CGN[0], CGN[1], lat, lon) == pytest.approx(d, rel=1e-5)
    # the circle around A passes through B (to within the sampling)
    custom = post(CGN, SCL, circle_km=500).json()["circles"][0]
    assert custom["radius_km"] == 500
    assert post((10, 20), (10, 20)).json()["circles"] == []
    # a circle that crosses the date line twice is cut into three pieces that meet exactly at +/-180
    cut = post((0, 170), (0, 175), circle_km=2000).json()["circles"][0]["segments"]
    assert len(cut) == 3
    for left, right in zip(cut, cut[1:]):
        assert abs(left[-1][0]) == abs(right[0][0]) == 180.0 and left[-1][0] == -right[0][0]
        assert left[-1][1] == right[0][1]


def test_terminator_endpoint():
    t = client.get("/api/terminator", params={"date": "2026-06-21", "time": "12:00"}).json()
    assert t["declination_deg"] == pytest.approx(23.44, abs=0.1)
    assert t["subsolar"]["lat"] == pytest.approx(23.44, abs=0.1) and abs(t["subsolar"]["lon"]) < 5
    assert t["polygon"][0] == t["polygon"][-1] and len(t["polygon"]) == 184
    # the south pole is in the dark at the June solstice: the ring closes along it
    assert [-180.0, -89.9] in t["polygon"] and [180.0, -89.9] in t["polygon"]
    dec = client.get("/api/terminator", params={"date": "2026-12-21", "time": "00:00"}).json()
    assert [-180.0, 89.9] in dec["polygon"]
    assert abs(dec["subsolar"]["lon"] - 180) < 5 or abs(dec["subsolar"]["lon"] + 180) < 5
    assert client.get("/api/terminator", params={"date": "2050-01-01", "time": "12:00"}).status_code == 422
    assert client.get("/api/terminator", params={"date": "1969-12-31", "time": "12:00"}).status_code == 422
    assert client.get("/api/terminator", params={"date": "2026-06-21", "time": "25:00"}).status_code == 422


def test_moon_phase_metric():
    new = by_id(post(CGN, SCL, date="2026-11-09").json())["moon_phase"]       # new moon on 9 Nov 2026 (about 08:00 UTC)
    assert new["display"].startswith("New moon") and new["value"] < 1
    full = by_id(post(CGN, SCL, date="2000-01-21").json())["moon_phase"]       # total lunar eclipse, full moon
    assert full["display"].startswith("Full moon") and full["value"] > 99
    steps = [s["label"] for s in full["explanation"]["steps"]]
    assert steps[0].startswith("Julian centuries") and len(steps) == 8
    assert any("about 0.3" in n for n in full["explanation"]["notes"])
    assert "UTC" in full["secondary"][1] and "2000-02-" in full["secondary"][1]       # next full moon: 19 Feb 2000
    assert by_id(post((0, 0), (0, 0)).json())["moon_phase"]["group"] == "Sun & time"


def test_sun_card_steps_and_utc_day_shift():
    m = by_id(post(CGN, SCL, date="2026-06-21").json())
    steps = [s["label"] for s in m["sun_a"]["explanation"]["steps"]]
    assert steps[:2] == ["Julian date of local solar noon", "Days since J2000.0"] and "Equation of time" in steps[5]
    assert "(previous day)" not in " ".join(m["sun_a"]["secondary"])
    # sunrise in New Zealand is on the previous UTC date
    nz = by_id(post((-36.85, 174.76), (-33.393, -70.7858), date="2026-06-21").json())["sun_a"]
    assert any("(previous day)" in s for s in nz["secondary"])


def test_units_change_the_cards_but_not_the_values():
    km = by_id(post(CGN, SCL).json())
    mi = by_id(post(CGN, SCL, units="mi").json())
    nm = by_id(post(CGN, SCL, units="nm").json())
    d = km["distance_haversine"]["value"]
    assert km["distance_haversine"]["display"].replace("\u00a0", " ") == "12 061 km"
    assert mi["distance_haversine"]["value"] == nm["distance_haversine"]["value"] == d
    assert mi["distance_haversine"]["display"].replace("\u00a0", " ") == f"{d / 1.609344:,.0f} mi".replace(",", " ")
    assert nm["distance_haversine"]["display"].replace("\u00a0", " ") == f"{d / 1.852:,.0f} nm".replace(",", " ")
    assert "km" in " ".join(mi["distance_haversine"]["secondary"])
    assert km["flight_time"]["secondary"][1].endswith("850 km/h + 15 min climb & descent")
    assert "528 mph" in mi["flight_time"]["secondary"][1] and "459 kn" in nm["flight_time"]["secondary"][1]
    # km is untouched (no extra step or note); mi/nm add a conversion step and a note, calculations stay in km
    assert len(km["distance_haversine"]["explanation"]["steps"]) == 7
    steps = mi["distance_haversine"]["explanation"]["steps"]
    assert len(steps) == 8 and steps[-1]["label"] == "Convert to mi for the card" and "7494" in steps[-1]["result"]
    assert any(n.startswith("Calculations are done in km") for n in mi["distance_haversine"]["explanation"]["notes"])
    assert "mi" in mi["crossings"]["table"][0]["display"] and "km" in km["crossings"]["table"][0]["display"]
    assert post(CGN, SCL, units="parsec").status_code == 422


def test_units_endpoint():
    body = client.get("/api/units").json()
    assert [u["id"] for u in body] == ["km", "nm", "mi"]
    assert body[0] == {"id": "km", "label": "km", "speed_label": "km/h", "km_per_unit": 1.0}
    assert body[1]["km_per_unit"] == 1.852 and body[2]["speed_label"] == "mph"


def test_places_search():
    def labels(q, **kw):
        return [p["label"] for p in client.get("/api/places", params={"q": q, **kw}).json()]
    assert labels("CGN")[0].startswith("CGN")
    assert labels("cgn")[0] == labels("CGN")[0]
    assert labels("koln")[0].startswith("CGN")                    # accents and case ignored: city "Köln (Cologne)"
    assert labels("santiago de chile") == [] or labels("scl")[0].startswith("SCL")
    assert any(l.startswith("SCL") for l in labels("santiago"))
    assert labels("zzzzzz") == []
    assert len(labels("a", limit=3)) <= 3
    assert client.get("/api/places", params={"q": ""}).status_code == 422
    assert client.get("/api/places", params={"q": "x" * 81}).status_code == 422


def test_nearest_place():
    body = client.get("/api/nearest", params={"lat": 50.8659, "lon": 7.1427}).json()
    assert body["airport"]["code"] == "CGN" and body["airport"]["km"] < 0.5
    assert body["city"]["km"] > 0
    far = client.get("/api/nearest", params={"lat": 51.0, "lon": 7.1}).json()["airport"]
    from app.geo import spherical
    import math
    _, delta = spherical.haversine(math.radians(51.0), math.radians(7.1), math.radians(far["lat"]), math.radians(far["lon"]))
    assert far["km"] == pytest.approx(6371.0088 * delta, abs=0.01)
    assert client.get("/api/nearest", params={"lat": 91, "lon": 0}).status_code == 422
    assert client.get("/api/nearest", params={"lat": 0, "lon": 181}).status_code == 422
    assert client.get("/api/nearest", params={"lat": 0}).status_code == 422


def post_course(a, bearing, km, **options):
    return client.post("/api/calculate", json={"a": {"lat": a[0], "lon": a[1]}, "course": {"bearing_deg": bearing, "km": km},
                                               "options": options})


def test_inverse_mode_computes_b_from_a_course_and_distance():
    body = post_course((0, 0), 90, 10007.5604).json()                     # a quarter of the equator
    assert body["b"]["lat"] == pytest.approx(0, abs=1e-6) and body["b"]["lon"] == pytest.approx(90, abs=1e-4)
    m = by_id(body)
    assert m["distance_haversine"]["value"] == pytest.approx(10007.5604, abs=0.01)
    assert m["bearing_initial"]["value"] == pytest.approx(90, abs=1e-3)
    assert "destination" in m and body["markers"]["projected"] is not None          # the destination card comes for free
    # the same scene given as two points gives the same metrics
    two = by_id(post((0, 0), (body["b"]["lat"], body["b"]["lon"])).json())
    assert two["distance_haversine"]["display"] == m["distance_haversine"]["display"]


def test_inverse_mode_round_trip_through_the_route_metrics():
    base = by_id(post(CGN, SCL).json())
    body = post_course(CGN, base["bearing_initial"]["value"], base["distance_haversine"]["value"]).json()
    assert body["b"]["lat"] == pytest.approx(SCL[0], abs=1e-3) and body["b"]["lon"] == pytest.approx(SCL[1], abs=1e-3)


def test_request_needs_exactly_one_of_b_and_course():
    a = {"lat": 10, "lon": 20}
    assert client.post("/api/calculate", json={"a": a}).status_code == 422
    assert client.post("/api/calculate", json={"a": a, "b": a, "course": {"bearing_deg": 1, "km": 1}}).status_code == 422
    for course in ({"bearing_deg": -1, "km": 5}, {"bearing_deg": 361, "km": 5}, {"bearing_deg": 10, "km": -5}, {"bearing_deg": 10}):
        assert client.post("/api/calculate", json={"a": a, "course": course}).status_code == 422


def test_inverse_mode_edge_cases():
    zero = post_course((10, 20), 45, 0).json()                              # no distance: B = A, undefined bearings
    assert (zero["b"]["lat"], zero["b"]["lon"]) == (10, 20) and by_id(zero)["bearing_initial"]["value"] is None
    anti = post_course((10, 20), 45, 20015.0868).json()                      # half the Earth: B is (about) the antipode
    assert anti["b"]["lat"] == pytest.approx(-10, abs=1e-3)
    far = post_course((10, 20), 45, 30000).json()                            # past the antipode: the note explains it
    assert any("antipode" in n for n in by_id(far)["destination"]["explanation"]["notes"])
    mi = by_id(post_course((0, 0), 90, 1000, units="mi").json())
    assert mi["destination"]["secondary"][0].startswith("621 mi")


def test_airports_endpoint():
    body = client.get("/api/airports").json()
    assert len(body) > 3000
    by_code = {a["code"]: a for a in body}
    assert len(by_code) == len(body)                       # unique codes
    assert all(len(a["code"]) == 3 and a["name"] for a in body)
    assert all(-90 <= a["lat"] <= 90 and -180 <= a["lon"] <= 180 for a in body)
    assert (by_code["CGN"]["lat"], by_code["CGN"]["lon"]) == (50.8659, 7.1427)
    assert (by_code["SCL"]["lat"], by_code["SCL"]["lon"]) == (-33.393, -70.7858)
    assert by_code["GRQ"]["name"] == "Groningen Airport Eelde" and by_code["GRQ"]["country"] == "Netherlands"


def test_timezone_lookup_edge_cases():
    day = dt.date(2026, 7, 15)
    # overlapping polygons: Xinjiang is inside Asia/Shanghai's polygon too, the more specific Asia/Urumqi wins
    assert timezones.find_zone(43.807, 87.5731) == "Asia/Urumqi"
    assert timezones.find_zone(31.2, 121.5) == "Asia/Shanghai"
    # a small enclave that a coarse simplification would lose
    assert timezones.find_zone(35.2798, -2.9563) == "Africa/Ceuta"                       # Melilla
    assert timezones.zone_info(35.2798, -2.9563, day)["offset_h"] == 2.0                  # CEST, not Morocco's +1
    # a land point in no polygon (a gap at the border) gets the nearest zone, with the distance noted
    zi = timezones.zone_info(23.887, 91.2404, day)                                        # Agartala, next to Bangladesh
    assert zi["tzid"] is not None and not zi["nominal"] and zi["offset_h"] == 5.5
    # open ocean far from any coast: nominal zone, no tzid
    ocean = timezones.zone_info(0.0, -140.0, day)
    assert ocean["tzid"] is None and ocean["nominal"] and ocean["offset_h"] == -9.0
    body = post((23.887, 91.2404), (0, -140), date="2026-07-15").json()
    notes = by_id(body)["timezone_diff"]["explanation"]["notes"]
    assert any("nearest zone" in n for n in notes) or zi["near_km"] is None
    assert any("open ocean" in n for n in notes)


def test_every_bundled_place_resolves_to_a_zone():
    """Airports and cities are on land: none may fall into the 'open ocean' fallback."""
    import json
    import os
    path = os.path.join(os.path.dirname(timezones.__file__), "data", "places.json")
    missing = [p["name"] for p in json.load(open(path, encoding="utf-8"))["places"]
               if timezones.zone_info(p["lat"], p["lon"], dt.date(2026, 1, 15))["nominal"]]
    assert len(missing) <= 3, missing


def test_lambert_card_warns_for_almost_antipodal_pairs():
    quito, singapore = (-0.14, -78.49), (1.35, 103.82)                      # 177.4 degrees apart, Lambert is 1.4 km off
    card = by_id(post(quito, singapore).json())["ellipsoid_lambert"]
    assert any("almost antipodal (177.4°)" in s and "up to about 2.5 km" in s for s in card["secondary"])
    assert any("This pair is almost antipodal" in n and "177.4°" in n for n in card["explanation"]["notes"])
    plain = by_id(post(CGN, SCL).json())["ellipsoid_lambert"]               # 108 degrees: no warning
    assert not any("antipodal" in s for s in plain["secondary"])
    assert not any("This pair is almost antipodal" in n for n in plain["explanation"]["notes"])
    close = by_id(post((10, 20), (-10, -159.5)).json())["ellipsoid_lambert"]      # 179.5 degrees
    assert any("tens of km" in s for s in close["secondary"])


def test_sun_card_hints_for_very_long_days_and_polar_edges():
    tromso, dusseldorf = (69.65, 18.96), (51.2277, 6.7735)
    long_day = by_id(post(tromso, dusseldorf, date="2026-05-14").json())["sun_a"]               # 21 h 43 min of daylight
    assert any("very long day" in s and "up to about 10" in s for s in long_day["secondary"])
    polar = by_id(post(tromso, dusseldorf, date="2026-06-05").json())["sun_a"]
    assert any("can be off by a day" in s for s in polar["secondary"])
    for date in ("2026-11-25", "2026-11-09", "2026-06-21"):                  # short winter day, long but normal days: no hint
        card = by_id(post(tromso, dusseldorf, date=date).json())["sun_a"]
        assert not any("very long day" in s for s in card["secondary"]) or date == "2026-06-21"
    assert not any("very long day" in s for s in by_id(post(dusseldorf, tromso, date="2026-06-21").json())["sun_a"]["secondary"])
    notes = " ".join(long_day["explanation"]["notes"])
    assert "up to 16 hours about 2 minutes" in notes


AMS, EZE = (52.3086, 4.7639), (-34.8222, -58.5358)


def analysis_rows(body):
    return {r["id"]: r for r in by_id(body)["distance_analysis"]["analysis"]["rows"]}


# Reference values for CGN -> SCL (A = 50.8659, 7.1427; B = -33.3930, -70.7858), computed independently with GeographicLib
# (Karney's algorithm) and a separate Vincenty implementation: (label, model, km, tolerance in km)
CGN_SCL_ROWS = [
    ("Straight tunnel through the Earth", "ellipsoid", 10319.7456, 0.001),
    ("Great circle, polar radius", "sphere", 12033.7, 0.1),
    ("Ellipsoid, Vincenty", "ellipsoid", 12040.7751, 0.001),
    ("Ellipsoid, Lambert (approximation)", "ellipsoid", 12040.7751 - 0.0128, 0.001),
    ("Great circle, mean radius", "sphere", 12060.7, 0.1),
    ("Great circle, equatorial radius", "sphere", 12074.2, 0.1),
    ("Rhumb line", "sphere", 12132.1, 0.1),
    ("Programmer's shortcut", "sphere", 12693.9, 0.1),
    ("Degrees as a flat grid", "sphere", 12762.0, 0.1),
    ("Ruler on a flat Mercator map", "sphere", 13639.6, 0.1),
]


def test_distance_analysis_for_cologne_to_santiago():
    body = post(CGN, SCL).json()
    card = by_id(body)["distance_analysis"]
    rows = card["analysis"]["rows"]
    assert [(r["label"], r["model"]) for r in rows] == [(l, m) for l, m, _, _ in CGN_SCL_ROWS]       # shortest first, with the model
    for r, (_, _, km, tol) in zip(rows, CGN_SCL_ROWS):
        assert r["km"] == pytest.approx(km, abs=tol), r["label"]
        assert r["explanation"] is not None or r["metric_id"], r["label"]                              # every row can show its calculation
    assert [round(r["km"]) for r in rows] == sorted(round(r["km"]) for r in rows)           # shortest first (the reference leads equal values)
    reference = [r for r in rows if r["is_reference"]]
    assert len(reference) == 1 and reference[0]["id"] == "vincenty" and card["analysis"]["reference_id"] == "vincenty"
    conventional = [r for r in rows if "conventional" in r["badges"]]
    assert len(conventional) == 1 and conventional[0]["id"] == "great_circle_mean"
    by_row = {r["id"]: r for r in rows}
    for r in rows:                                                                                    # differences follow from the km values
        if r["km"] is not None:
            assert r["diff_pct"] == pytest.approx((r["km"] - by_row["vincenty"]["km"]) / by_row["vincenty"]["km"] * 100)
    # sphere-based methods also show their difference to the great circle on the same sphere
    assert by_row["rhumb"]["diff_display"].replace("\u00a0", " ").startswith("+91 km (+0.8 %)")
    assert by_row["rhumb"]["vs_sphere_display"].replace("\u00a0", " ") == "+71 km vs great circle on the same sphere"
    assert by_row["great_circle_mean"]["vs_sphere_display"] is None and by_row["vincenty"]["vs_sphere_display"] is None
    assert by_row["lambert"]["diff_display"].startswith("−13 m")
    summary = " ".join(card["analysis"]["summary"]).replace("\u00a0", " ")
    assert "12 034 km to 12 074 km" in summary and "spread of 0.34 %" in summary and "12 061 km to 13 640 km" in summary and "+13.1 %" in summary
    foot = " ".join(card["analysis"]["footnotes"])
    assert "unless stated otherwise" in foot and "conventional method" in foot and "+0.17 %" in foot and "at most about 0.5 %" in foot
    assert card["display"].replace("\u00a0", " ") == "10 320 km to 13 640 km"
    assert len(card["table"]) == 10 and "[sphere]" in card["table"][1]["label"]
    # the great-circle card names the method as the conventional one and gives its error margin
    gc = by_id(body)["distance_haversine"]["secondary"][-1].replace("\u00a0", " ")
    assert "conventional method" in gc and "typically within 0.2 %" in gc and "+0.17 %" in gc


def test_distance_analysis_for_amsterdam_to_buenos_aires():
    rows = analysis_rows(post(AMS, EZE).json())
    assert rows["vincenty"]["km"] == pytest.approx(11437.2, abs=0.05)
    assert rows["mercator"]["diff_pct"] == pytest.approx(14.1, abs=0.1) and rows["tunnel"]["km"] < rows["vincenty"]["km"]
    assert rows["grid"]["explanation"]["steps"][2]["label"] == "Distance on the grid"
    assert all(r["explanation"] is None for k, r in rows.items() if r["metric_id"])


def test_every_analysis_row_has_a_model_and_a_calculation():
    for a, b in ((CGN, SCL), (AMS, EZE), ((0, 0), (0, 90)), ((60, 170), (-20, -160))):
        card = by_id(post(a, b).json())["distance_analysis"]
        for r in card["analysis"]["rows"]:
            assert r["model"] in ("sphere", "ellipsoid")
            steps = r["explanation"]["steps"] if r["explanation"] else None
            assert steps is None or len(steps) >= 1
        assert card["explanation"]["steps"][0]["label"] == "Reference" and len(card["explanation"]["steps"]) == 11


def test_vincenty_card_lists_the_iterations():
    card = by_id(post(CGN, SCL).json())["ellipsoid_vincenty"]
    labels = [s["label"] for s in card["explanation"]["steps"]]
    assert labels[0] == "Reduced latitudes and longitude difference" and sum(1 for l in labels if l.startswith("Round ")) == 5
    assert "Converged: the change of λ is below the tolerance" in labels and labels[-1] == "Difference to the spherical result"
    assert card["value"] == pytest.approx(12040.7751, abs=0.001) and "5 iterations" in card["secondary"]
    lam = by_id(post(CGN, SCL).json())["ellipsoid_lambert"]
    assert lam["label"] == "Ellipsoid distance, Lambert (approximation)" and "−12.8 m vs Vincenty" in " ".join(lam["secondary"]).replace("\u00a0", " ")
    quito = by_id(post((-0.18, -78.47), (1.35, 103.82)).json())["ellipsoid_vincenty"]               # converges in 11 rounds although lambda > pi on the way
    assert quito["value"] == pytest.approx(19743.3064, abs=0.001) and "11 iterations" in quito["secondary"]
    assert "Round 11: improve λ" in [s["label"] for s in quito["explanation"]["steps"]]
    slow = by_id(post((0, 0), (0.2, 179.0)).json())["ellipsoid_vincenty"]                          # 15 rounds: the middle ones are summarised
    labels = [s["label"] for s in slow["explanation"]["steps"]]
    assert "15 iterations" in slow["secondary"] and "… 3 more rounds …" in labels and labels.count("Round 15: improve λ") == 1 and "Round 11: improve λ" not in labels


def test_distance_analysis_units_and_edge_cases():
    mi = analysis_rows(post(AMS, EZE, units="mi").json())
    assert mi["vincenty"]["display"].endswith(" mi") and mi["vincenty"]["km"] == pytest.approx(11437.2, abs=0.05)
    assert by_id(post((10, 20), (10, 20)).json())["distance_analysis"]["value"] is None            # identical points
    assert by_id(post((10, 20), (10, 20)).json())["ellipsoid_vincenty"]["value"] is None
    near_pole = analysis_rows(post((89.5, 0), (10, 30)).json())                                     # |lat| > 85.05: no Mercator distance
    assert near_pole["mercator"]["km"] is None and near_pole["mercator"]["display"] == "off the map"
    assert near_pole["mercator"]["diff_display"] is None
    pole = analysis_rows(post((90, 0), (10, 30)).json())
    assert pole["rhumb"]["km"] is None and pole["rhumb"]["display"] == "undefined"
    exact = by_id(post((0, 0), (0, 180)).json())["distance_analysis"]                              # exactly antipodal: no ellipsoid distance at all
    assert exact["analysis"]["reference_id"] == "great_circle_mean"
    assert by_id(post((0, 0), (0, 180)).json())["ellipsoid_vincenty"]["display"] == "undefined"


def test_nearly_antipodal_pair_warns_and_falls_back_to_lambert():
    body = post((0, 0), (0.5, 179.7)).json()                                                        # Vincenty does not converge here
    assert any("does not converge for nearly antipodal points; Lambert is used as the reference" in w for w in body["warnings"])
    card = by_id(body)["distance_analysis"]
    assert card["analysis"]["reference_id"] == "lambert"
    assert [r["id"] for r in card["analysis"]["rows"] if r["is_reference"]] == ["lambert"]
    assert by_id(body)["ellipsoid_vincenty"]["display"] == "no convergence"
    assert any("Lambert is used as the reference" in f for f in card["analysis"]["footnotes"])
    vin = [r for r in card["analysis"]["rows"] if r["id"] == "vincenty"][0]
    assert vin["km"] is None and vin["display"] == "no convergence"


def test_paths_apart_line_for_amsterdam_to_buenos_aires():
    card = by_id(post(AMS, EZE).json())["rhumb_vs_great_circle"]
    line = [s for s in card["secondary"] if "apart" in s][0]
    assert "up to about 450 km apart" in line.replace("\u00a0", " ") and "27.1°N" in line
    assert any(s["label"] == "How far apart are the two paths?" for s in card["explanation"]["steps"])
    assert not any("apart" in s for s in by_id(post((0, 10), (0, 80)).json())["rhumb_vs_great_circle"]["secondary"])    # equator: same path
    assert not any("apart" in s for s in by_id(post((10, 0), (50, 0)).json())["rhumb_vs_great_circle"]["secondary"])    # meridian


def test_tiny_angles_never_make_a_double_superscript_in_tex():
    from app.explain import step
    s = step("x", None, r"\theta = (-7.1247\times 10^{-15}^{\circ}+360^{\circ}) \bmod 360^{\circ}")
    assert s["substituted_tex"] == r"\theta = ((-7.1247\times 10^{-15})^{\circ}+360^{\circ}) \bmod 360^{\circ}"
    assert step("x", r"\theta = 5.1^{\circ}")["tex"] == r"\theta = 5.1^{\circ}"
