"""Tests for the hand-written geo functions, against analytic values."""
import math
import random

import pytest

from app import constants as K
from app.geo import crossings, ellipsoid, mercator, pip, rhumb, spherical, sun, travel

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


def test_sun_equinox_equator():
    s = sun.sun_times(0.0, 0.0, 80, K.AXIAL_TILT_DEG, K.SUN_ALTITUDE_DEG)
    assert 12.0 <= s["day_length_h"] <= 12.2
    assert s["state"] == "normal"


def test_sun_polar_day_and_night():
    assert sun.sun_times(rad(80), 0.0, 172, K.AXIAL_TILT_DEG, K.SUN_ALTITUDE_DEG)["state"] == "polar_day"
    s = sun.sun_times(rad(80), 0.0, 355, K.AXIAL_TILT_DEG, K.SUN_ALTITUDE_DEG)
    assert s["state"] == "polar_night" and s["day_length_h"] == 0.0


def test_sun_at_pole_does_not_divide_by_zero():
    assert sun.sun_times(rad(90), 0.0, 172, K.AXIAL_TILT_DEG, K.SUN_ALTITUDE_DEG)["state"] == "polar_day"
    assert sun.sun_times(rad(-90), 0.0, 172, K.AXIAL_TILT_DEG, K.SUN_ALTITUDE_DEG)["state"] == "polar_night"


def test_sun_noon_follows_longitude():
    s0 = sun.sun_times(0.0, 0.0, 100, K.AXIAL_TILT_DEG, K.SUN_ALTITUDE_DEG)["solar_noon_h"]
    s1 = sun.sun_times(0.0, rad(15), 100, K.AXIAL_TILT_DEG, K.SUN_ALTITUDE_DEG)["solar_noon_h"]
    assert (s0 - s1) % 24 == pytest.approx(1.0)


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
