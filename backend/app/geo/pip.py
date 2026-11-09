"""Point-in-polygon by ray casting. Plain arithmetic only."""


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


def bbox_of(rings):
    """Bounding box (min_x, min_y, max_x, max_y) of the outer ring."""
    xs = [p[0] for p in rings[0]]
    ys = [p[1] for p in rings[0]]
    return min(xs), min(ys), max(xs), max(ys)
