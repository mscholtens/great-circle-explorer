"""Tests for the hand-written geo functions, against analytic values."""
import datetime
import math
import random

import pytest

from app import constants as K
from app.geo import crossings, ellipsoid, mercator, moon, pip, rhumb, spherical, sun, travel

R = K.R_KM
rad = math.radians
deg = math.degrees


def dist(la1, lo1, la2, lo2):
    return R * spherical.haversine(rad(la1), rad(lo1), rad(la2), rad(lo2))[1]


def test_quarter_circle_along_equator():
    assert dist(0, 0, 0, 90) == pytest.approx(math.pi * R / 2, abs=1e-6)
    assert dist(0, 0, 0, 90) == pytest.approx(10007.56, abs=0.01)
    _, _, th = spherical.initial_bearing(0, 0, 0, rad(90))
    assert deg(th) == pytest.approx(90)


def test_pole_quarter_circle():
    assert dist(0, 0, 90, 0) == pytest.approx(math.pi * R / 2, abs=1e-6)
    _, _, th = spherical.initial_bearing(0, 0, rad(90), 0)
    assert deg(th) == pytest.approx(0)


def test_antipodal_and_identical():
    assert dist(0, 0, 0, 180) == pytest.approx(math.pi * R, abs=1e-6)
    assert dist(12.3, 45.6, 12.3, 45.6) == 0.0


def test_haversine_matches_law_of_cosines():
    rnd = random.Random(1)
    for _ in range(200):
        p = [rad(rnd.uniform(-80, 80)), rad(rnd.uniform(-179, 179)), rad(rnd.uniform(-80, 80)), rad(rnd.uniform(-179, 179))]
        d = spherical.haversine(*p)[1]
        if 0.05 < d < 3.0:
            assert spherical.law_of_cosines(*p)[1] == pytest.approx(d, rel=1e-9)


def test_symmetry_and_bearing_relation():
    rnd = random.Random(2)
    for _ in range(100):
        p1, l1, p2, l2 = (rad(rnd.uniform(-80, 80)), rad(rnd.uniform(-179, 179)),
                          rad(rnd.uniform(-80, 80)), rad(rnd.uniform(-179, 179)))
        assert spherical.haversine(p1, l1, p2, l2)[1] == pytest.approx(spherical.haversine(p2, l2, p1, l1)[1])
        back = spherical.initial_bearing(p2, l2, p1, l1)[2]
        fin = spherical.final_bearing(p1, l1, p2, l2)
        assert deg(fin) == pytest.approx(deg((back + math.pi) % (2 * math.pi)))


def test_midpoint_equidistant():
    rnd = random.Random(3)
    for _ in range(100):
        p1, l1, p2, l2 = (rad(rnd.uniform(-80, 80)), rad(rnd.uniform(-179, 179)),
                          rad(rnd.uniform(-80, 80)), rad(rnd.uniform(-179, 179)))
        if spherical.haversine(p1, l1, p2, l2)[1] > 3.1:
            continue
        _, _, pm, lm = spherical.midpoint(p1, l1, p2, l2)
        d1 = R * spherical.haversine(p1, l1, pm, lm)[1]
        d2 = R * spherical.haversine(p2, l2, pm, lm)[1]
        assert d1 == pytest.approx(d2, abs=1e-6)


def test_intermediate_points():
    p1, l1, p2, l2 = rad(51.2), rad(6.8), rad(40.6), rad(-73.8)
    delta = spherical.haversine(p1, l1, p2, l2)[1]
    lat0, lon0 = spherical.intermediate_point(p1, l1, p2, l2, delta, 0.0)
    lat1, lon1 = spherical.intermediate_point(p1, l1, p2, l2, delta, 1.0)
    assert (lat0, lon0) == pytest.approx((p1, l1))
    assert (lat1, lon1) == pytest.approx((p2, l2))
    for lat, lon in spherical.sample_path(p1, l1, p2, l2, delta, 32):
        # each sample lies on the great circle: d(A,P) + d(P,B) = d(A,B)
        s = spherical.haversine(p1, l1, lat, lon)[1] + spherical.haversine(lat, lon, p2, l2)[1]
        assert s == pytest.approx(delta, abs=1e-9)


def test_antimeridian_unwrapped_monotonic():
    p1, l1, p2, l2 = 0.0, rad(170), 0.0, rad(-170)
    delta = spherical.haversine(p1, l1, p2, l2)[1]
    path = spherical.sample_path(p1, l1, p2, l2, delta, 64)
    lons = [deg(p[1]) for p in path]
    assert all(b > a for a, b in zip(lons, lons[1:]))
    assert lons[0] == pytest.approx(170) and lons[-1] == pytest.approx(190)


def test_chord_and_sagitta():
    assert spherical.chord_length(R, math.pi) == pytest.approx(2 * R)
    assert spherical.sagitta(R, math.pi) == pytest.approx(R)
    assert spherical.chord_length(R, 0.0) == 0.0


def test_antipode():
    lat, lon = spherical.antipode(rad(10), rad(20))
    assert (deg(lat), deg(lon)) == pytest.approx((-10, -160))
    lat, lon = spherical.antipode(rad(-33), rad(-170))
    assert (deg(lat), deg(lon)) == pytest.approx((33, 10))


def test_vertex_on_transatlantic_route():
    p1, l1, p2, l2 = rad(51.2), rad(6.8), rad(40.6), rad(-73.8)
    _, _, th1 = spherical.initial_bearing(p1, l1, p2, l2)
    thf = spherical.final_bearing(p1, l1, p2, l2)
    v = spherical.vertex_of_route(p1, l1, th1, thf, spherical.haversine(p1, l1, p2, l2)[1])
    assert v is not None and v["north"]
    assert deg(v["phi_v"]) > 51.2          # further north than both endpoints
    # the vertex is an extreme: nearby points on the circle are lower
    delta = spherical.haversine(p1, l1, p2, l2)[1]
    best = max(spherical.intermediate_point(p1, l1, p2, l2, delta, i / 400)[0] for i in range(401))
    assert best == pytest.approx(v["lat"], abs=1e-4)


def test_vertex_absent_for_meridian_route():
    p1, l1, p2, l2 = rad(10), 0.0, rad(50), 0.0
    _, _, th1 = spherical.initial_bearing(p1, l1, p2, l2)
    thf = spherical.final_bearing(p1, l1, p2, l2)
    assert spherical.vertex_of_route(p1, l1, th1, thf, spherical.haversine(p1, l1, p2, l2)[1]) is None


def test_rhumb_equator_and_meridian_equal_great_circle():
    r = rhumb.rhumb(0.0, 0.0, 0.0, rad(60))
    assert R * r["dist"] == pytest.approx(dist(0, 0, 0, 60))
    r = rhumb.rhumb(rad(10), 0.0, rad(50), 0.0)
    assert R * r["dist"] == pytest.approx(dist(10, 0, 50, 0))


def test_rhumb_never_shorter_than_great_circle():
    rnd = random.Random(4)
    for _ in range(300):
        p1, l1, p2, l2 = (rad(rnd.uniform(-85, 85)), rad(rnd.uniform(-179, 179)),
                          rad(rnd.uniform(-85, 85)), rad(rnd.uniform(-179, 179)))
        gc = spherical.haversine(p1, l1, p2, l2)[1]
        assert rhumb.rhumb(p1, l1, p2, l2)["dist"] >= gc - 1e-12


def test_rhumb_pole_is_undefined():
    with pytest.raises(ValueError):
        rhumb.rhumb(rad(90), 0.0, 0.0, 0.0)


def test_rhumb_path_endpoints():
    p1, l1, p2, l2 = rad(35), rad(139), rad(37), rad(-122)
    r = rhumb.rhumb(p1, l1, p2, l2)
    path = rhumb.sample_rhumb(p1, l1, r, 50)
    assert path[0] == pytest.approx((p1, l1))
    assert path[-1][0] == pytest.approx(p2)
    assert (path[-1][1] - l2) % (2 * math.pi) == pytest.approx(0, abs=1e-9) or \
        (path[-1][1] - l2) % (2 * math.pi) == pytest.approx(2 * math.pi, abs=1e-9)


def test_mercator():
    m = mercator.flat_map_distance(0.0, 0.0, 0.0, rad(60))
    assert R * m["dist"] == pytest.approx(dist(0, 0, 0, 60))
    # same latitude away from equator: flat map overstates by sec(lat) ~ 1/cos
    m = mercator.flat_map_distance(rad(60), 0.0, rad(60), rad(10))
    assert m["dist"] > spherical.haversine(rad(60), 0.0, rad(60), rad(10))[1]
    assert mercator.scale_factor(rad(60)) == pytest.approx(2.0)


def test_lambert_close_to_sphere():
    rnd = random.Random(5)
    for _ in range(100):
        p1, l1, p2, l2 = (rad(rnd.uniform(-80, 80)), rad(rnd.uniform(-179, 179)),
                          rad(rnd.uniform(-80, 80)), rad(rnd.uniform(-179, 179)))
        d = R * spherical.haversine(p1, l1, p2, l2)[1]
        lam = ellipsoid.lambert_distance(p1, l1, p2, l2, K.WGS84_A_KM, K.WGS84_F)
        if lam is None or d < 100:
            continue
        assert abs(lam["dist"] - d) / d < 0.01


def test_lambert_equator_quarter():
    lam = ellipsoid.lambert_distance(0.0, 0.0, 0.0, rad(90), K.WGS84_A_KM, K.WGS84_F)
    assert lam["dist"] == pytest.approx(K.WGS84_A_KM * math.pi / 2)   # along the equator the ellipsoid arc is a*sigma
    assert ellipsoid.lambert_distance(0.1, 0.2, 0.1, 0.2, K.WGS84_A_KM, K.WGS84_F) is None


def test_gravity_train_period():
    omega, t, v = travel.gravity_train(R * 1000.0, K.G, 2 * R * 1000.0)
    assert t / 60 == pytest.approx(42.2, abs=0.1)
    assert v == pytest.approx(omega * R * 1000.0)


def test_light_and_flight():
    t_vac, t_fib, rtt = travel.light_times_s(299792.458, K.C_KM_S, K.FIBER_INDEX)
    assert t_vac == pytest.approx(1.0)
    assert t_fib == pytest.approx(K.FIBER_INDEX)
    assert rtt == pytest.approx(2 * K.FIBER_INDEX)
    assert travel.flight_time_h(850, 850, 30) == pytest.approx(1.5)


def test_horizon():
    assert travel.horizon_distance_exact_km(R, 0.0) == 0.0
    for h in (1.7, 100.0, 11000.0):
        ex = travel.horizon_distance_exact_km(R, h)
        ap = travel.horizon_distance_approx_km(R, h)
        assert ex == pytest.approx(ap, rel=0.01)
    # a 1.7 m observer sees about 4.7 km
    assert travel.horizon_distance_approx_km(R, 1.7) == pytest.approx(4.65, abs=0.05)


def jd12(year, month, day):
    """Julian date of 12:00 UTC on a calendar date."""
    return datetime.date(year, month, day).toordinal() + K.JD_AT_ORDINAL_ZERO_NOON


# Reference values from PyEphem (an independent astronomy library; used once to generate these numbers, not a dependency)
SUN_DECL_EOT = {   # date at 12:00 UTC: (declination in degrees, equation of time in minutes)
    (1975, 7, 4): (22.9092, -4.237), (2000, 1, 1): (-23.0334, -3.286), (2026, 3, 20): (-0.0454, -7.437),
    (2026, 6, 21): (23.4388, -1.817), (2026, 10, 12): (-7.5096, 13.514), (2026, 12, 21): (-23.4379, 1.935),
    (2045, 11, 9): (-17.0492, 16.176),
}
SUN_TIMES_REF = [  # (lat, lon, date, sunrise UTC h, sunset UTC h), centre of the Sun at -0.833 degrees
    (50.8659, 7.1427, (2026, 3, 1), 6.266, 17.206), (50.8659, 7.1427, (2026, 6, 21), 3.292, 19.816),
    (50.8659, 7.1427, (2026, 12, 21), 7.524, 15.458), (-33.393, -70.7858, (2026, 3, 1), 10.525, 23.312),
    (-33.393, -70.7858, (2026, 6, 21), 11.781, 21.719), (-33.393, -70.7858, (2026, 12, 21), 9.503, 23.873),
    (-33.87, 151.21, (2026, 3, 1), 19.71, 8.531), (-33.87, 151.21, (2026, 6, 21), 20.999, 6.897),
    (-33.87, 151.21, (2026, 12, 21), 18.677, 9.09), (64.13, -21.9, (2026, 3, 1), 8.587, 18.765),
    (64.13, -21.9, (2026, 6, 21), 2.924, 0.056), (64.13, -21.9, (2026, 12, 21), 11.365, 15.491),
    (-0.14, -78.49, (2026, 3, 1), 11.38, 23.493), (-0.14, -78.49, (2026, 12, 21), 11.136, 23.269),
]


def test_sun_declination_and_equation_of_time_match_an_ephemeris():
    for (y, mo, d), (decl_ref, eot_ref) in SUN_DECL_EOT.items():
        pos = sun.sun_position(jd12(y, mo, d))
        assert deg(pos["decl"]) == pytest.approx(decl_ref, abs=0.01), (y, mo, d)
        assert pos["eot_min"] == pytest.approx(eot_ref, abs=0.15), (y, mo, d)


def test_sunrise_and_sunset_match_an_ephemeris_to_two_minutes():
    for lat, lon, (y, mo, d), rise, sset in SUN_TIMES_REF:
        s = sun.sun_times(rad(lat), rad(lon), jd12(y, mo, d), K.SUN_ALTITUDE_DEG)
        assert s["state"] == "normal"
        assert abs((s["sunrise_h"] - rise + 12) % 24 - 12) * 60 < 2.5, (lat, lon, y, mo, d, "sunrise")
        assert abs((s["sunset_h"] - sset + 12) % 24 - 12) * 60 < 2.5, (lat, lon, y, mo, d, "sunset")


def test_sun_equinox_equator():
    s = sun.sun_times(0.0, 0.0, jd12(2026, 3, 20), K.SUN_ALTITUDE_DEG)
    assert 12.0 <= s["day_length_h"] <= 12.2
    assert s["state"] == "normal"


def test_sun_polar_day_and_night():
    assert sun.sun_times(rad(80), 0.0, jd12(2026, 6, 21), K.SUN_ALTITUDE_DEG)["state"] == "polar_day"
    s = sun.sun_times(rad(80), 0.0, jd12(2026, 12, 21), K.SUN_ALTITUDE_DEG)
    assert s["state"] == "polar_night" and s["day_length_h"] == 0.0


def test_sun_at_pole_does_not_divide_by_zero():
    assert sun.sun_times(rad(90), 0.0, jd12(2026, 6, 21), K.SUN_ALTITUDE_DEG)["state"] == "polar_day"
    assert sun.sun_times(rad(-90), 0.0, jd12(2026, 6, 21), K.SUN_ALTITUDE_DEG)["state"] == "polar_night"


def test_sun_noon_follows_longitude():
    s0 = sun.sun_times(0.0, 0.0, jd12(2026, 4, 10), K.SUN_ALTITUDE_DEG)["solar_noon_h"]
    s1 = sun.sun_times(0.0, rad(15), jd12(2026, 4, 10), K.SUN_ALTITUDE_DEG)["solar_noon_h"]
    assert (s0 - s1) % 24 == pytest.approx(1.0, abs=0.01)         # the equation of time changes a little over an hour


def test_solstice_and_equinox_dates():
    # the declination is about +/-23.44 degrees at the solstices and crosses zero at the March equinox (20 Mar 2026, 14:46 UTC)
    assert deg(sun.sun_position(jd12(2026, 6, 21))["decl"]) == pytest.approx(23.44, abs=0.01)
    assert deg(sun.sun_position(jd12(2026, 12, 21))["decl"]) == pytest.approx(-23.44, abs=0.01)
    assert deg(sun.sun_position(jd12(2026, 3, 20) + 14.77 / 24 - 0.5)["decl"]) == pytest.approx(0.0, abs=0.01)


def test_point_in_polygon():
    square = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hole = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
    assert pip.point_in_polygon(1, 1, [square])
    assert not pip.point_in_polygon(11, 5, [square])
    assert not pip.point_in_polygon(5, 5, [square, hole])
    assert pip.point_in_polygon(2, 2, [square, hole])


# ---------------------------------------------------------------- crossings
def frame(la1, lo1, la2, lo2):
    f = crossings.route_frame(rad(la1), rad(lo1), rad(la2), rad(lo2))
    delta = spherical.haversine(rad(la1), rad(lo1), rad(la2), rad(lo2))[1]
    return f, delta


def test_equator_crossing_on_a_meridian():
    (a, e2, n), delta = frame(10, 0, -50, 0)
    hits = crossings.latitude_crossings(a, e2, delta, 0.0)
    assert len(hits) == 1 and hits[0] == pytest.approx(rad(10))        # 10 degrees south of the start
    lat, lon = crossings.point_at(a, e2, hits[0])
    assert (deg(lat), deg(lon)) == pytest.approx((0.0, 0.0), abs=1e-9)


def test_polar_circle_on_a_meridian_and_course_north():
    (a, e2, n), delta = frame(60, 0, 80, 0)
    (sigma,) = crossings.latitude_crossings(a, e2, delta, rad(K.POLAR_CIRCLE_LAT_DEG))
    assert sigma == pytest.approx(rad(K.POLAR_CIRCLE_LAT_DEG - 60))
    assert deg(crossings.course_at(a, e2, sigma)) == pytest.approx(0.0, abs=1e-6)


def test_prime_meridian_crossing_on_the_equator_and_course_east():
    (a, e2, n), delta = frame(0, -10, 0, 10)
    sigma = crossings.meridian_crossing(a, e2, n, delta, 0.0)
    assert sigma == pytest.approx(rad(10))
    lat, lon = crossings.point_at(a, e2, sigma)
    assert (deg(lat), deg(lon)) == pytest.approx((0.0, 0.0), abs=1e-9)
    assert deg(crossings.course_at(a, e2, sigma)) == pytest.approx(90.0)


def test_route_along_the_equator_or_a_meridian_is_reported_as_along():
    (a, e2, n), delta = frame(0, 10, 0, 80)
    assert crossings.latitude_crossings(a, e2, delta, 0.0) == "along"
    assert crossings.latitude_crossings(a, e2, delta, rad(23.44)) == []
    (a, e2, n), delta = frame(10, 0, 50, 0)
    assert crossings.meridian_crossing(a, e2, n, delta, 0.0) == "along"


def test_no_crossing_when_the_circle_is_not_reached_or_beyond_the_segment():
    (a, e2, n), delta = frame(51, 7, 40, -74)                          # highest latitude about 54 N
    assert crossings.latitude_crossings(a, e2, delta, rad(K.POLAR_CIRCLE_LAT_DEG)) == []
    assert crossings.latitude_crossings(a, e2, delta, 0.0) == []        # both ends north of the equator
    assert crossings.meridian_crossing(a, e2, n, delta, math.pi) is None


def test_crossings_lie_on_the_route_at_the_requested_place():
    rnd = random.Random(21)
    found = 0
    for _ in range(400):
        la1, la2 = rnd.uniform(-85, 85), rnd.uniform(-85, 85)
        lo1, lo2 = rnd.uniform(-179, 179), rnd.uniform(-179, 179)
        f, delta = frame(la1, lo1, la2, lo2)
        if f is None or delta > 3.1:
            continue
        a, e2, n = f
        p1, l1, p2, l2 = rad(la1), rad(lo1), rad(la2), rad(lo2)
        lat_list = [("eq", 0.0), ("tc", K.TROPIC_LAT_DEG), ("tcap", -K.TROPIC_LAT_DEG),
                    ("ac", K.POLAR_CIRCLE_LAT_DEG), ("anc", -K.POLAR_CIRCLE_LAT_DEG)]
        for _, lat_c in lat_list:
            for sigma in crossings.latitude_crossings(a, e2, delta, rad(lat_c)):
                lat, lon = crossings.point_at(a, e2, sigma)
                assert deg(lat) == pytest.approx(lat_c, abs=1e-7)
                # on the route: d(A,P) + d(P,B) = d(A,B), and sigma really is the distance from A
                d1 = spherical.haversine(p1, l1, lat, lon)[1]
                d2 = spherical.haversine(lat, lon, p2, l2)[1]
                assert d1 + d2 == pytest.approx(delta, abs=1e-8)
                assert d1 == pytest.approx(sigma, abs=1e-8)
                found += 1
        for lon_c in (0.0, math.pi):
            sigma = crossings.meridian_crossing(a, e2, n, delta, lon_c)
            if isinstance(sigma, float):
                lat, lon = crossings.point_at(a, e2, sigma)
                assert math.cos(lon - lon_c) == pytest.approx(1.0, abs=1e-9)
                d1 = spherical.haversine(p1, l1, lat, lon)[1]
                d2 = spherical.haversine(lat, lon, p2, l2)[1]
                assert d1 + d2 == pytest.approx(delta, abs=1e-8)
                found += 1
    assert found > 300


def test_tokyo_to_san_francisco_crosses_180_once_and_cologne_to_santiago_does_not():
    (a, e2, n), delta = frame(35.7, 139.7, 37.8, -122.4)
    sigma = crossings.meridian_crossing(a, e2, n, delta, math.pi)
    assert isinstance(sigma, float)
    lat, lon = crossings.point_at(a, e2, sigma)
    assert abs(abs(deg(lon)) - 180) < 1e-9 and 40 < deg(lat) < 55
    (a, e2, n), delta = frame(50.8659, 7.1427, -33.393, -70.7858)
    assert crossings.meridian_crossing(a, e2, n, delta, math.pi) is None


def test_cologne_to_santiago_equator_crossing_matches_the_prototype():
    (a, e2, n), delta = frame(50.8659, 7.1427, -33.393, -70.7858)
    (sigma,) = crossings.latitude_crossings(a, e2, delta, 0.0)
    lat, lon = crossings.point_at(a, e2, sigma)
    assert deg(lon) == pytest.approx(-45.54, abs=0.05)
    assert R * sigma == pytest.approx(7506, abs=5)


def test_route_through_the_pole_has_a_frame_and_no_course_at_the_pole():
    (a, e2, n), delta = frame(80, 0, 80, 180)                          # over the north pole
    assert delta == pytest.approx(rad(20))
    (sigma,) = crossings.latitude_crossings(a, e2, delta, rad(85))[:1]
    assert crossings.course_at(a, e2, rad(10)) is None                 # exactly at the pole
    assert crossings.route_frame(0.0, 0.0, 0.0, math.pi) is None       # antipodal: no unique route
    assert crossings.route_frame(0.3, 0.4, 0.3, 0.4) is None           # identical


def test_direct_problem_matches_known_cases():
    lat, lon = spherical.destination(0, 0, rad(90), math.pi / 2)
    assert (deg(lat), deg(lon)) == pytest.approx((0, 90), abs=1e-9)
    lat, lon = spherical.destination(rad(45), rad(10), rad(0), rad(45))
    assert (deg(lat), deg(lon)) == pytest.approx((90, 10), abs=1e-6) or deg(lat) == pytest.approx(90, abs=1e-6)


def test_direct_problem_inverts_the_inverse_problem():
    rng = random.Random(7)
    for _ in range(200):
        la1, lo1 = rad(rng.uniform(-80, 80)), rad(rng.uniform(-180, 180))
        la2, lo2 = rad(rng.uniform(-80, 80)), rad(rng.uniform(-180, 180))
        _, delta = spherical.haversine(la1, lo1, la2, lo2)
        if delta < 1e-3 or math.pi - delta < 1e-3:
            continue
        _, _, th = spherical.initial_bearing(la1, lo1, la2, lo2)
        la, lo = spherical.destination(la1, lo1, th, delta)
        assert la == pytest.approx(la2, abs=1e-9)
        assert spherical.wrap_pi(lo - lo2) == pytest.approx(0, abs=1e-9)


def test_split_antimeridian_meets_at_the_edge():
    pts = [(0.0, rad(170)), (rad(10), rad(179)), (rad(20), rad(-179)), (rad(30), rad(-170))]
    segs = spherical.split_antimeridian(pts)
    assert len(segs) == 2
    assert segs[0][-1][1] == pytest.approx(math.pi) and segs[1][0][1] == pytest.approx(-math.pi)
    assert segs[0][-1][0] == segs[1][0][0] == pytest.approx(rad(15))
    assert len(spherical.split_antimeridian([(0, 0), (0, 1), (0, 2)])) == 1


def test_subsolar_point_and_terminator():
    decl, lon, eot = sun.subsolar_point(jd12(2026, 6, 21))                    # June solstice, noon UTC
    assert deg(decl) == pytest.approx(23.44, abs=0.01) and deg(lon) == pytest.approx(-eot / 4, abs=1e-9)
    decl, lon, _ = sun.subsolar_point(jd12(2026, 3, 20) + 6 / 24)               # 18:00 UTC: the Sun is about 90 degrees west
    assert deg(lon) == pytest.approx(-90, abs=2)
    # every boundary point has the Sun on the horizon; the dark pole is below it
    rng = random.Random(3)
    for _ in range(100):
        d, ls = rad(rng.uniform(-23.4, 23.4)), rad(rng.uniform(-180, 180))
        for lam in (rad(rng.uniform(-180, 180)), ls, ls + math.pi):
            phi = sun.terminator_latitude(d, lam, ls)
            alt = math.sin(phi) * math.sin(d) + math.cos(phi) * math.cos(d) * math.cos(lam - ls)
            assert alt == pytest.approx(0, abs=1e-9)
        ring = sun.night_ring(d, ls)
        pole_lat = ring[-3][0]
        assert math.sin(pole_lat) * math.sin(d) < 0                           # the closing pole is in darkness
    # at the equinox (decl = 0) the boundary is the meridian 90 degrees from the Sun
    assert abs(deg(sun.terminator_latitude(0.0, rad(10), rad(10)))) == pytest.approx(90)


MOON_LIT_REF = {(2000, 1, 21): 0.9986, (2026, 11, 9): 0.0023, (2026, 11, 17): 0.5021, (2026, 11, 24): 0.9979,
                (2030, 5, 5): 0.074, (1985, 3, 15): 0.3171}        # PyEphem, 12:00 UTC
FULL_MOONS_REF = [((2026, 11, 9), 2461369.1205), ((2000, 1, 10), 2451564.6948), ((2040, 7, 1), 2466359.5870)]   # next full moon (JD)
NEW_MOONS_REF = [((2026, 11, 12), 2461383.5360), ((2000, 1, 10), 2451580.0439), ((2040, 7, 1), 2466344.8850)]   # next new moon (JD)


def test_moon_phase_matches_an_ephemeris():
    for (y, mo, d), ref in MOON_LIT_REF.items():
        psi = moon.elongation(jd12(y, mo, d))[0]
        assert moon.illuminated_fraction(psi) == pytest.approx(ref, abs=0.01), (y, mo, d)
    for (y, mo, d), ref_jd in FULL_MOONS_REF:
        assert abs(moon.time_of_phase(jd12(y, mo, d), 180.0) - ref_jd) * 24 < 1.5
    for (y, mo, d), ref_jd in NEW_MOONS_REF:
        assert abs(moon.time_of_phase(jd12(y, mo, d), 0.0) - ref_jd) * 24 < 1.5


def test_moon_phase_names_and_searches():
    assert [moon.phase_name(x) for x in (0, 45, 90, 135, 180, 225, 270, 315, 359, 22, 23)] == [
        "New moon", "Waxing crescent", "First quarter", "Waxing gibbous", "Full moon", "Waning gibbous",
        "Last quarter", "Waning crescent", "New moon", "New moon", "Waxing crescent"]
    assert moon.illuminated_fraction(0.0) == pytest.approx(0) and moon.illuminated_fraction(math.pi) == pytest.approx(1)
    assert moon.illuminated_fraction(math.pi / 2) == pytest.approx(0.5)
    for y, mo, d in [(2026, 11, 9), (1999, 3, 3), (2044, 8, 30)]:
        jd = jd12(y, mo, d)
        nxt, full, prev = (moon.time_of_phase(jd, 0.0), moon.time_of_phase(jd, 180.0), moon.time_of_phase(jd, 0.0, forward=False))
        assert prev <= jd + 1e-9 <= nxt and 0 <= full - jd <= 30.0
        assert 28.5 < nxt - prev < 30.7                                       # one lunation, from new moon to new moon
        for t, target in ((nxt, 0.0), (full, 180.0), (prev, 0.0)):             # the search really lands on the phase
            assert abs((moon.elongation(t)[1] - target + 180) % 360 - 180) < 0.01


def test_moon_series_values_add_up():
    t = moon.centuries(jd12(2026, 11, 9))
    lam, beta = moon.moon_position(jd12(2026, 11, 9))
    base = moon.LONGITUDE_BASE[0] + moon.LONGITUDE_BASE[1] * t + sum(moon.series_values(moon.LONGITUDE_TERMS, t))
    assert deg(lam) == pytest.approx(base % 360, abs=1e-9)
    assert deg(beta) == pytest.approx(sum(moon.series_values(moon.LATITUDE_TERMS, t)), abs=1e-9)


# Exact WGS84 geodesic lengths (GeographicLib), for pairs close to antipodal: Lambert's formula loses accuracy there
NEAR_ANTIPODAL_REF = [  # (lat1, lon1, lat2, lon2, exact distance in km)
    (-0.14, -78.49, 1.35, 103.82, 19739.015),      # Quito -> Singapore, 177.4 degrees
    (40, 10, -38, -165, 19533.100),                # 175.6 degrees
    (10, 20, -10, -159.5, 19980.862),              # 179.5 degrees
    (30, 0, -30, 178.0, 19836.182),
]


def test_lambert_error_stays_inside_the_documented_tiers():
    for la1, lo1, la2, lo2, exact_km in NEAR_ANTIPODAL_REF:
        p = [rad(x) for x in (la1, lo1, la2, lo2)]
        delta = deg(spherical.haversine(*p)[1])
        err_km = abs(ellipsoid.lambert_distance(*p, K.WGS84_A_KM, K.WGS84_F)["dist"] - exact_km)
        tier = next((t for limit, t in K.LAMBERT_ERROR_TIERS if delta >= limit), None)
        assert tier is not None, delta
        if tier != "tens of km":
            assert err_km <= float(tier.split("about ")[1].split(" km")[0]), (delta, err_km, tier)
    # away from the antipode it is accurate to well under a kilometre (here: a typical long route)
    p = [rad(x) for x in (50.8659, 7.1427, -33.393, -70.7858)]
    assert abs(ellipsoid.lambert_distance(*p, K.WGS84_A_KM, K.WGS84_F)["dist"] - 12040.775) < 0.1


def test_plate_carree_distance():
    quarter = math.pi * R / 2
    for p in ((0.0, 0.0, 0.0, rad(90)), (0.0, 0.0, rad(90), 0.0)):                      # along the equator and along a meridian
        assert K.KM_PER_DEGREE * spherical.plate_carree_distance(*p)[2] == pytest.approx(quarter, abs=1e-6)
    assert K.KM_PER_DEGREE == pytest.approx(111.19508, abs=1e-5)
    dphi, dlam, d = spherical.plate_carree_distance(rad(10), rad(170), rad(10), rad(-170))        # across the date line: 20 degrees
    assert (dphi, abs(dlam), d) == pytest.approx((0, 20, 20))
    assert spherical.plate_carree_distance(rad(10), rad(-170), rad(10), rad(170))[1] == pytest.approx(-20)
    # away from the equator the grid overstates east-west distances: 10 degrees of longitude at 60 N are 5.2 degrees of arc
    assert K.KM_PER_DEGREE * 10 > R * spherical.haversine(rad(60), 0.0, rad(60), rad(10))[1] * 1.9


def test_max_separation_of_paths():
    # identical paths: zero; a path and a shifted copy: the shift
    path = [(0.0, rad(x)) for x in range(0, 60, 5)]
    assert spherical.max_separation(path, path)[0] == pytest.approx(0, abs=1e-12)
    shifted = [(rad(2), lon) for _, lon in path]
    sep, a, b = spherical.max_separation(path, shifted)
    assert sep == pytest.approx(rad(2), abs=1e-6) and abs(a[0]) < 1e-12 and b[0] == pytest.approx(rad(2))
    # the great circle and the rhumb line of Amsterdam -> Buenos Aires: compared with a brute-force search of the whole rhumb line
    p1, l1, p2, l2 = (rad(x) for x in (52.3086, 4.7639, -34.8222, -58.5358))
    delta = spherical.haversine(p1, l1, p2, l2)[1]
    r = rhumb.rhumb(p1, l1, p2, l2)
    gc = spherical.sample_path(p1, l1, p2, l2, delta, 48)
    fine = rhumb.sample_rhumb(p1, l1, r, 6000)
    coarse = spherical.max_separation(gc, rhumb.sample_rhumb(p1, l1, r, 720))[0] * R
    brute = max(min(spherical.haversine(a[0], a[1], b[0], b[1])[1] for b in fine[::3]) for a in gc) * R
    assert coarse == pytest.approx(brute, abs=10) and coarse == pytest.approx(450, abs=10)


def vin(*c):
    return ellipsoid.vincenty_inverse(*[rad(x) for x in c], K.WGS84_A_KM, K.WGS84_F, K.VINCENTY_TOLERANCE, K.VINCENTY_MAX_ITERATIONS)


VINCENTY_CASES = [   # (A, B, exact distance in km from GeographicLib/Karney)
    ((50.8659, 7.1427, -33.3930, -70.7858), 12040.7751),
    ((52.308056, 4.764167, -34.822167, -58.535833), 11437.1973),
    ((0, 0, 0, 90), 10018.7542),                      # along the equator: a * pi / 2
    ((0, 0, 90, 0), 10001.9657),                      # along a meridian: a quarter of the meridian
    ((-0.18, -78.47, 1.35, 103.82), 19743.3064),      # Quito -> Singapore: converges in 11 rounds
]


def test_vincenty_matches_the_exact_geodesic():
    for c, exact in VINCENTY_CASES:
        assert vin(*c)["dist"] == pytest.approx(exact, abs=0.001), c
    assert vin(0, 0, 0, 90)["dist"] == pytest.approx(K.WGS84_A_KM * math.pi / 2, abs=1e-6)
    r = vin(50.8659, 7.1427, -33.3930, -70.7858)
    assert r["iterations"] == len(r["log"]) == 5 and r["b"] == pytest.approx(K.WGS84_B_KM)
    assert r["log"][-1]["new_lam"] == pytest.approx(r["log"][-2]["new_lam"], abs=1e-11)         # it really settled
    assert vin(-0.18, -78.47, 1.35, 103.82)["iterations"] == 11
    # Lambert is an approximation of Vincenty: about 13 m apart on this route
    p = [rad(x) for x in (50.8659, 7.1427, -33.3930, -70.7858)]
    assert (ellipsoid.lambert_distance(*p, K.WGS84_A_KM, K.WGS84_F)["dist"] - 12040.7751) * 1000 == pytest.approx(-12.8, abs=1.0)


def test_vincenty_edge_cases():
    assert vin(10, 20, 10, 20)["dist"] == 0.0                         # identical points
    assert vin(0, 0, 0.5, 179.7) is None                              # nearly antipodal: no convergence
    assert vin(0, 0, 0, 180) is None and vin(10, 20, -10, -160) is None and vin(90, 0, -90, 0) is None     # exactly antipodal
    assert vin(90, 0, 0, 0)["dist"] == pytest.approx(10001.9657, abs=0.001)                      # from a pole
    # symmetric and agrees with the sphere to within the flattening
    a, b = vin(40, -10, -25, 100)["dist"], vin(-25, 100, 40, -10)["dist"]
    assert a == pytest.approx(b, abs=1e-6)
    p = [rad(x) for x in (40, -10, -25, 100)]
    assert a == pytest.approx(R * spherical.haversine(*p)[1], rel=0.006)


def test_vincenty_is_not_rejected_for_passing_through_lambda_above_pi():
    """Regression: a shortcut 'fail as soon as |lambda| > pi' would reject Quito -> Singapore, which does converge."""
    r = vin(-0.18, -78.47, 1.35, 103.82)
    assert r is not None and max(abs(e["new_lam"]) for e in r["log"]) > math.pi


def test_ellipsoid_chord_and_ecef():
    c, pa, pb = ellipsoid.ellipsoid_chord(rad(50.8659), rad(7.1427), rad(-33.3930), rad(-70.7858), K.WGS84_A_KM, K.WGS84_F)
    assert c == pytest.approx(10319.7456, abs=0.001)
    p = [rad(x) for x in (50.8659, 7.1427, -33.3930, -70.7858)]
    assert 2 * R * math.sin(spherical.haversine(*p)[1] / 2) == pytest.approx(10338.8, abs=0.1)     # the spherical chord
    assert ellipsoid.ellipsoid_chord(0, 0, 0, rad(90), K.WGS84_A_KM, K.WGS84_F)[0] == pytest.approx(K.WGS84_A_KM * math.sqrt(2), abs=1e-9)   # 9020.0478
    assert ellipsoid.ecef(rad(90), 0, K.WGS84_A_KM, K.WGS84_F)[2] == pytest.approx(K.WGS84_B_KM)           # the pole is b above the centre
    x, y, z = ellipsoid.ecef(rad(45), rad(30), K.WGS84_A_KM, K.WGS84_F)
    assert (x * x + y * y) / K.WGS84_A_KM ** 2 + z * z / K.WGS84_B_KM ** 2 == pytest.approx(1.0, abs=1e-12)   # on the ellipsoid


def test_spheres_with_three_radii_and_the_shortcut():
    p = [rad(x) for x in (50.8659, 7.1427, -33.3930, -70.7858)]
    delta = spherical.haversine(*p)[1]
    assert (K.WGS84_B_KM * delta, K.R_KM * delta, K.WGS84_A_KM * delta) == pytest.approx((12033.7, 12060.7, 12074.2), abs=0.1)
    assert K.R_KM == pytest.approx((2 * K.WGS84_A_KM + K.WGS84_B_KM) / 3, abs=1e-4)                # IUGG mean radius
    assert K.WGS84_B_KM == pytest.approx(6356.752314, abs=1e-6)
    assert K.R_KM * spherical.equirectangular_distance(*p)[3] == pytest.approx(12693.9, abs=0.1)
    # exact along the equator and a meridian; short distances agree with the great circle; wraps the date line
    assert spherical.equirectangular_distance(0, 0, 0, rad(90))[3] == pytest.approx(math.pi / 2)
    assert spherical.equirectangular_distance(0, 0, rad(90), 0)[3] == pytest.approx(math.pi / 2)
    near = [rad(x) for x in (51.0, 6.0, 51.1, 6.1)]
    assert spherical.equirectangular_distance(*near)[3] == pytest.approx(spherical.haversine(*near)[1], rel=1e-4)
    assert spherical.equirectangular_distance(rad(10), rad(170), rad(10), rad(-170))[1] == pytest.approx(rad(20))
