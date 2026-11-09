"""Compares the hand-written calculations with independent libraries and prints the measured accuracy.

NOT part of the app and not needed to run it. It needs three extra packages that are not project dependencies:

    pip install geographiclib ephem timezonefinder          (use a separate virtual environment)
    python tools/verify_accuracy.py [sphere] [ellipsoid] [vincenty] [sun] [moon] [timezones]      (default: all)

  sphere      haversine, bearings, destination, midpoint, interpolation vs GeographicLib on a perfect sphere
  ellipsoid   Lambert's formula, spherical distance and spherical bearing vs the exact WGS84 geodesic
  vincenty    Vincenty's inverse formula (the reference of the distance analysis) vs GeographicLib: agreement, iterations,
              and where it does not converge
  sun         declination, equation of time, sunrise/sunset vs PyEphem
  moon        lit fraction, times of new and full moon vs PyEphem
  timezones   the bundled simplified zone polygons vs TimezoneFinder (exact polygons), for every bundled place

The numbers in docs/ACCURACY.md come from this script. Random pairs use a fixed seed, so runs are repeatable.
"""
import datetime as dt
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app import constants as K  # noqa: E402
from app.geo import ellipsoid, moon, spherical, sun  # noqa: E402

rad, deg = math.radians, math.degrees


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


def jd12(d):
    return d.toordinal() + K.JD_AT_ORDINAL_ZERO_NOON


def check_sphere():
    from geographiclib.geodesic import Geodesic
    R = K.R_KM * 1000
    sph = Geodesic(R, 0.0)
    rng = random.Random(42)
    worst = {"distance (m)": 0, "initial bearing (deg)": 0, "final bearing (deg)": 0, "destination (m)": 0, "midpoint (m)": 0, "interpolation (m)": 0}
    n = 0
    for _ in range(20000):
        la1, lo1, la2, lo2 = rng.uniform(-89, 89), rng.uniform(-180, 180), rng.uniform(-89, 89), rng.uniform(-180, 180)
        g = sph.Inverse(la1, lo1, la2, lo2)
        p1, l1, p2, l2 = map(rad, (la1, lo1, la2, lo2))
        _, delta = spherical.haversine(p1, l1, p2, l2)
        if math.pi - delta < 1e-4 or delta < 1e-6:
            continue
        n += 1
        worst["distance (m)"] = max(worst["distance (m)"], abs(R * delta - g["s12"]))
        _, _, th = spherical.initial_bearing(p1, l1, p2, l2)
        worst["initial bearing (deg)"] = max(worst["initial bearing (deg)"], abs((deg(th) - g["azi1"] + 180) % 360 - 180))
        worst["final bearing (deg)"] = max(worst["final bearing (deg)"], abs((deg(spherical.final_bearing(p1, l1, p2, l2)) - g["azi2"] + 180) % 360 - 180))
        la, lo = spherical.destination(p1, l1, th, delta)
        worst["destination (m)"] = max(worst["destination (m)"], R * spherical.haversine(la, lo, p2, l2)[1])
        d = sph.Direct(la1, lo1, g["azi1"], g["s12"] / 2)
        _, _, mla, mlo = spherical.midpoint(p1, l1, p2, l2)
        worst["midpoint (m)"] = max(worst["midpoint (m)"], R * spherical.haversine(mla, mlo, rad(d["lat2"]), rad(d["lon2"]))[1])
        ila, ilo = spherical.intermediate_point(p1, l1, p2, l2, delta, 0.3)
        d = sph.Direct(la1, lo1, g["azi1"], g["s12"] * 0.3)
        worst["interpolation (m)"] = max(worst["interpolation (m)"], R * spherical.haversine(ila, ilo, rad(d["lat2"]), rad(d["lon2"]))[1])
    print(f"SPHERE vs GeographicLib on a perfect sphere, worst of {n} random pairs:")
    for k, v in worst.items():
        print(f"  {k:24s} {v:.2e}")


def check_ellipsoid():
    from geographiclib.geodesic import Geodesic
    wgs = Geodesic(K.WGS84_A_KM * 1000, K.WGS84_F)
    rng = random.Random(42)
    lam_err, lam_rel, sph_err, brg_err = [], [], [], []
    for _ in range(20000):
        la1, lo1, la2, lo2 = rng.uniform(-89, 89), rng.uniform(-180, 180), rng.uniform(-89, 89), rng.uniform(-180, 180)
        g = wgs.Inverse(la1, lo1, la2, lo2)
        p1, l1, p2, l2 = map(rad, (la1, lo1, la2, lo2))
        _, delta = spherical.haversine(p1, l1, p2, l2)
        if math.pi - delta < 1e-3 or delta < 1e-4:
            continue
        lam = ellipsoid.lambert_distance(p1, l1, p2, l2, K.WGS84_A_KM, K.WGS84_F)
        if lam is None:
            continue
        lam_err.append(abs(lam["dist"] * 1000 - g["s12"]))
        lam_rel.append(abs(lam["dist"] * 1000 - g["s12"]) / g["s12"] * 100)
        sph_err.append((K.R_KM * 1000 * delta - g["s12"]) / g["s12"] * 100)
        _, _, th = spherical.initial_bearing(p1, l1, p2, l2)
        brg_err.append(abs((deg(th) - g["azi1"] + 180) % 360 - 180))
    print(f"LAMBERT vs the exact WGS84 geodesic ({len(lam_err)} random pairs):")
    print(f"  absolute error: mean {sum(lam_err) / len(lam_err):.1f} m, 99th percentile {pct(lam_err, .99):.0f} m, maximum {max(lam_err):.0f} m")
    print(f"  relative error: median {pct(lam_rel, .5):.5f} %, maximum {max(lam_rel):.4f} %")
    bins = {}
    rng = random.Random(5)
    for _ in range(60000):                                  # pairs biased towards the antipode
        la1, lo1 = rng.uniform(-89, 89), rng.uniform(-180, 180)
        la2 = max(-89, min(89, -la1 + rng.uniform(-25, 25)))
        lo2 = (lo1 + 180 + rng.uniform(-25, 25) + 180) % 360 - 180
        p1, l1, p2, l2 = map(rad, (la1, lo1, la2, lo2))
        lam = ellipsoid.lambert_distance(p1, l1, p2, l2, K.WGS84_A_KM, K.WGS84_F)
        if lam is None:
            continue
        err = abs(lam["dist"] * 1000 - wgs.Inverse(la1, lo1, la2, lo2)["s12"])
        bins.setdefault(int(deg(spherical.haversine(p1, l1, p2, l2)[1]) // 2) * 2, []).append(err)
    print("LAMBERT error for nearly antipodal pairs, largest error by central angle (these are the constants.LAMBERT_ERROR_TIERS):")
    for b in sorted(bins):
        if b >= 150:
            print(f"  {b:3d}-{b + 2:3d} deg: max {max(bins[b]):7.0f} m  (n={len(bins[b])})")
    print("SPHERE (R = 6371.0088 km) vs the exact WGS84 geodesic:")
    print(f"  distance error: 1st pct {pct(sph_err, .01):+.3f} %, median {pct(sph_err, .5):+.3f} %, 99th pct {pct(sph_err, .99):+.3f} %, min {min(sph_err):+.3f} %, max {max(sph_err):+.3f} %")
    print(f"  initial bearing error: median {pct(brg_err, .5):.3f} deg, 90th pct {pct(brg_err, .9):.3f}, 99th pct {pct(brg_err, .99):.3f}, maximum {max(brg_err):.1f} deg")


def check_vincenty():
    from geographiclib.geodesic import Geodesic
    wgs = Geodesic(K.WGS84_A_KM * 1000, K.WGS84_F)
    for label, bias in (("random pairs", False), ("pairs biased towards the antipode (opposite side +/- 15 deg)", True)):
        rng = random.Random(11)
        n = fail = 0
        worst, iters = 0.0, []
        by_angle = {}
        for _ in range(30000):
            la1, lo1 = rng.uniform(-89, 89), rng.uniform(-180, 180)
            if bias:
                la2 = max(-89.9, min(89.9, -la1 + rng.uniform(-15, 15)))
                lo2 = (lo1 + 180 + rng.uniform(-15, 15) + 180) % 360 - 180
            else:
                la2, lo2 = rng.uniform(-89, 89), rng.uniform(-180, 180)
            p = [rad(x) for x in (la1, lo1, la2, lo2)]
            angle = deg(spherical.haversine(*p)[1])
            r = ellipsoid.vincenty_inverse(*p, K.WGS84_A_KM, K.WGS84_F, K.VINCENTY_TOLERANCE, K.VINCENTY_MAX_ITERATIONS)
            n += 1
            bucket = by_angle.setdefault(int(angle // 5) * 5, [0, 0])
            bucket[0] += 1
            if r is None:
                fail += 1
                bucket[1] += 1
                continue
            iters.append(r["iterations"])
            worst = max(worst, abs(r["dist"] - wgs.Inverse(la1, lo1, la2, lo2)["s12"] / 1000))
        print(f"VINCENTY vs GeographicLib, {label} (n={n}):")
        print(f"  worst difference {worst * 1e6:.2f} mm where it converges; iterations: median {pct(iters, .5)}, 99th percentile {pct(iters, .99)}, max {max(iters)}")
        print(f"  no convergence: {fail} of {n} ({100 * fail / n:.2f} %)" + (
            "; by central angle (degrees): " + ", ".join(f"{b}-{b + 5}: {v[1]}/{v[0]}" for b, v in sorted(by_angle.items()) if v[1]) if fail else ""))
    # the cases of the tests
    for name, c in (("Cologne -> Santiago", (50.8659, 7.1427, -33.393, -70.7858)), ("Quito -> Singapore", (-0.18, -78.47, 1.35, 103.82)),
                    ("(0, 0) -> (0.5, 179.7)", (0, 0, 0.5, 179.7))):
        r = ellipsoid.vincenty_inverse(*[rad(x) for x in c], K.WGS84_A_KM, K.WGS84_F, K.VINCENTY_TOLERANCE, K.VINCENTY_MAX_ITERATIONS)
        g = wgs.Inverse(*c)["s12"] / 1000
        print(f"  {name}: " + (f"Vincenty {r['dist']:.4f} km in {r['iterations']} rounds, GeographicLib {g:.4f} km" if r else f"no convergence (GeographicLib {g:.4f} km)"))
    p = [rad(x) for x in (50.8659, 7.1427, -33.393, -70.7858)]
    delta = spherical.haversine(*p)[1]
    print("  the three spheres on Cologne -> Santiago: " + ", ".join(f"{name} {radius * delta:.1f} km" for name, radius in
          (("polar", K.WGS84_B_KM), ("mean", K.R_KM), ("equatorial", K.WGS84_A_KM))))


def check_sun():
    import ephem
    de, ee = [], []
    for year in (1970, 1980, 2000, 2024, 2026, 2049):
        for n in range(0, 365, 2):
            d = dt.date(year, 1, 1) + dt.timedelta(days=n)
            pos = sun.sun_position(jd12(d))
            s, obs = ephem.Sun(), ephem.Observer()
            obs.lat, obs.lon, obs.date = "0", "0", d.strftime("%Y/%m/%d") + " 12:00:00"
            obs.epoch = obs.date
            s.compute(obs)
            ha = (float(obs.sidereal_time()) - float(s.g_ra) + math.pi) % (2 * math.pi) - math.pi
            de.append(abs(deg(pos["decl"]) - deg(float(s.dec))))
            ee.append(abs(pos["eot_min"] - deg(ha) * 4))
    print("SUN vs PyEphem (every second day of six years between 1970 and 2049):")
    print(f"  declination: mean {sum(de) / len(de):.4f} deg, max {max(de):.4f} deg;  equation of time: mean {sum(ee) / len(ee):.3f} min, max {max(ee):.3f} min")

    def utc_h(x):
        t = x.datetime()
        return t.hour + t.minute / 60 + t.second / 3600
    print("  sunrise/sunset (centre of the Sun at -0.833 deg, UTC clock), difference to PyEphem:")
    for name, lat, lon in [("Cologne", 50.8659, 7.1427), ("Santiago", -33.393, -70.7858), ("Quito", -0.14, -78.49), ("Reykjavik", 64.13, -21.9),
                           ("Tromso", 69.65, 18.96), ("Sydney", -33.87, 151.21), ("Anchorage", 61.2, -149.9), ("Honolulu", 21.3, -157.86),
                           ("Auckland", -36.85, 174.76), ("Singapore", 1.35, 103.82)]:
        errs, mismatch = [], 0
        for year in (1975, 2026, 2045):
            for n in range(0, 365, 4):
                d = dt.date(year, 1, 1) + dt.timedelta(days=n)
                s = sun.sun_times(rad(lat), rad(lon), jd12(d), K.SUN_ALTITUDE_DEG)
                obs = ephem.Observer()
                obs.lat, obs.lon, obs.pressure, obs.horizon = str(lat), str(lon), 0, "-0.833"
                obs.date = ephem.Date(d.strftime("%Y/%m/%d") + " 12:00:00") - lon / 360.0
                try:
                    rise = obs.previous_rising(ephem.Sun(), use_center=True)
                    sset = obs.next_setting(ephem.Sun(), use_center=True)
                except (ephem.AlwaysUpError, ephem.NeverUpError):
                    mismatch += s["state"] == "normal"
                    continue
                if s["state"] != "normal":
                    mismatch += 1
                    continue
                errs.append(max(abs((utc_h(rise) - s["sunrise_h"] + 12) % 24 - 12), abs((utc_h(sset) - s["sunset_h"] + 12) % 24 - 12)) * 60)
        print(f"    {name:10s} lat {lat:6.1f}: max {max(errs):5.1f} min, mean {sum(errs) / len(errs):.2f} min, polar day/night disagreements: {mismatch}")
    rows = []
    for lat in (60, 62, 64, 66, 67, 68, 69, 70, 71, 72, 75, -62, -66, -68):
        for n in range(0, 365, 3):
            d = dt.date(2026, 1, 1) + dt.timedelta(days=n)
            s = sun.sun_times(rad(lat), rad(15.0), jd12(d), K.SUN_ALTITUDE_DEG)
            if s["state"] != "normal":
                continue
            obs = ephem.Observer()
            obs.lat, obs.lon, obs.pressure, obs.horizon = str(lat), "15", 0, "-0.833"
            obs.date = ephem.Date(d.strftime("%Y/%m/%d") + " 12:00:00") - 15.0 / 360.0
            try:
                rise = obs.previous_rising(ephem.Sun(), use_center=True)
                sset = obs.next_setting(ephem.Sun(), use_center=True)
            except (ephem.AlwaysUpError, ephem.NeverUpError):
                continue
            rows.append((s["day_length_h"], max(abs((utc_h(rise) - s["sunrise_h"] + 12) % 24 - 12), abs((utc_h(sset) - s["sunset_h"] + 12) % 24 - 12)) * 60))
    print("  largest sunrise/sunset error by length of the day (latitudes 60-75, both hemispheres; constants.LONG_DAY_HINT_H = 21):")
    for lo, hi in [(0, 8), (8, 16), (16, 19), (19, 21), (21, 22.5), (22.5, 24)]:
        v = [e for dl, e in rows if lo <= dl < hi]
        print(f"    day length {lo:4.1f}-{hi:4.1f} h: " + (f"max {max(v):5.1f} min (n={len(v)})" if v else "no cases"))


def check_moon():
    import ephem
    errs = []
    for i in range(0, 365 * 79, 5):
        d = dt.date(1970, 1, 1) + dt.timedelta(days=i)
        m = ephem.Moon()
        m.compute(d.strftime("%Y/%m/%d") + " 12:00:00")
        errs.append(abs(moon.illuminated_fraction(moon.elongation(jd12(d))[0]) - m.phase / 100) * 100)
    print(f"MOON lit fraction vs PyEphem (1970-2049, every 5th day): mean {sum(errs) / len(errs):.3f}, max {max(errs):.3f} percentage points")
    for kind, target, nxt in (("full", 180.0, ephem.next_full_moon), ("new", 0.0, ephem.next_new_moon)):
        errs = []
        for i in range(0, 365 * 79, 17):
            d = dt.date(1970, 1, 1) + dt.timedelta(days=i)
            ref = float(nxt(d.strftime("%Y/%m/%d") + " 12:00:00")) + 2415020.0      # PyEphem date -> Julian date
            ours = moon.time_of_phase(jd12(d), target)
            if abs(ours - ref) < 5:
                errs.append(abs(ours - ref) * 24)
        print(f"  next {kind} moon: median {pct(errs, .5):.2f} h, 95th pct {pct(errs, .95):.2f} h, max {max(errs):.2f} h (n={len(errs)})")


def check_timezones():
    from timezonefinder import TimezoneFinder
    from app import timezones
    tf = TimezoneFinder()
    with open(os.path.join(ROOT, "backend", "app", "data", "places.json"), encoding="utf-8") as fh:
        places = json.load(fh)["places"]
    summer, winter = dt.date(2026, 7, 15), dt.date(2026, 1, 15)
    same_id = same_offset = nominal = 0
    for p in places:
        zi = timezones.zone_info(p["lat"], p["lon"], summer)
        ref = tf.timezone_at(lng=p["lon"], lat=p["lat"])
        nominal += zi["nominal"]
        same_id += zi["tzid"] == ref
        if ref and zi["tzid"] and all(timezones.utc_offset_hours(zi["tzid"], d) == timezones.utc_offset_hours(ref, d) for d in (summer, winter)):
            same_offset += 1
    n = len(places)
    print(f"TIME ZONES: bundled simplified polygons vs TimezoneFinder for all {n} bundled airports and cities:")
    print(f"  same zone id {same_id} ({100 * same_id / n:.1f} %), same UTC offset in July and January {same_offset} ({100 * same_offset / n:.1f} %), "
          f"fell back to the open-ocean rule: {nominal}")


CHECKS = {"sphere": check_sphere, "ellipsoid": check_ellipsoid, "vincenty": check_vincenty, "sun": check_sun, "moon": check_moon, "timezones": check_timezones}

if __name__ == "__main__":
    for name in sys.argv[1:] or list(CHECKS):
        CHECKS[name]()
        print()
