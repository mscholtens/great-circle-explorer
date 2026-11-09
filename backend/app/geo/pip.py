"""Point-in-polygon by ray casting, and distance to a polygon outline. Plain arithmetic only."""
import math


def point_in_ring(x, y, ring):
    """Even-odd ray casting: count crossings of a horizontal ray from (x, y) towards +x.

    ring is a list of [x, y] vertices (closing vertex optional).
    """
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def point_in_polygon(x, y, rings):
    """Polygon = [outer, hole1, hole2, ...]. Inside the outer ring and outside every hole."""
    if not point_in_ring(x, y, rings[0]):
        return False
    return not any(point_in_ring(x, y, hole) for hole in rings[1:])


def polygon_area(ring):
    """Area of a ring in square degrees (shoelace formula); only used to compare polygons with each other."""
    total = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def distance_to_ring_km(x, y, ring, km_per_degree):
    """Distance in km from the point (x = lon, y = lat, degrees) to the outline of a ring.

    Local flat approximation (longitude scaled by cos(latitude)), good for the few tens of km it is used for.
    """
    kx = km_per_degree * math.cos(math.radians(y))
    best = float("inf")
    n = len(ring)
    for i in range(n):
        ax, ay = (ring[i][0] - x) * kx, (ring[i][1] - y) * km_per_degree
        bx, by = (ring[(i + 1) % n][0] - x) * kx, (ring[(i + 1) % n][1] - y) * km_per_degree
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        t = 0.0 if seg2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg2))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def bbox_of(rings):
    """Bounding box (min_x, min_y, max_x, max_y) of the outer ring."""
    xs = [p[0] for p in rings[0]]
    ys = [p[1] for p in rings[0]]
    return min(xs), min(ys), max(xs), max(ys)
