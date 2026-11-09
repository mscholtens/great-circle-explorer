"""Travel-time, latency, gravity-train and horizon formulas. `math` only."""
import math


def flight_time_h(distance_km, cruise_kmh, extra_min):
    """Airborne time in hours: t = d / v + extra (the climb-and-descent allowance, in minutes)."""
    return distance_km / cruise_kmh + extra_min / 60.0


def light_times_s(distance_km, c_km_s, fiber_index):
    """One-way times in seconds: vacuum d/c, fiber d/(c/n), and minimum round trip 2 d n / c.

    Returns (t_vacuum, t_fiber, rtt_fiber).
    """
    t_vac = distance_km / c_km_s
    t_fib = distance_km / (c_km_s / fiber_index)
    return t_vac, t_fib, 2.0 * t_fib


def gravity_train(radius_m, g, chord_m):
    """Frictionless fall through a chord tunnel (uniform-density Earth): simple harmonic motion.

        omega = sqrt(g/R);  T_trip = pi sqrt(R/g)  (half a period, independent of distance)
        v_max = omega * chord/2
    Returns (omega, t_trip_s, v_max_m_s).
    """
    omega = math.sqrt(g / radius_m)
    return omega, math.pi * math.sqrt(radius_m / g), omega * chord_m / 2.0


def horizon_distance_exact_km(radius_km, height_m):
    """Ground distance to the horizon for eye height h: R acos(R / (R + h))."""
    h_km = height_m / 1000.0
    return radius_km * math.acos(radius_km / (radius_km + h_km))


def horizon_distance_approx_km(radius_km, height_m):
    """Small-height approximation: sqrt(2 R h)."""
    return math.sqrt(2.0 * radius_km * height_m / 1000.0)
