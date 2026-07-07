"""Minimal planar geometry for survey generation.

Works in a local East/North (meters) frame produced by an equirectangular
projection around the polygon centroid. Error is negligible for survey-scale
areas (< ~5 km across), which is our use case.

Deliberately dependency-free for v1 (simplicity rule, design doc 5.2).
Keep-out clipping in a later milestone should introduce Shapely rather than
growing hand-rolled geometry here.

Conventions:
- latlon points are (lat, lon) in WGS84 degrees.
- local points are (x, y) meters, x = east, y = north.
- compass headings are degrees, 0 = north, 90 = east.
"""

from __future__ import annotations

import math

EARTH_RADIUS_M = 6371008.8


def centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Arithmetic mean of points (adequate as a projection origin)."""
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)


def latlon_to_local(
    points: list[tuple[float, float]], origin: tuple[float, float]
) -> list[tuple[float, float]]:
    """WGS84 (lat, lon) degrees -> local (x=east, y=north) meters around origin."""
    lat0, lon0 = origin
    cos_lat0 = math.cos(math.radians(lat0))
    out = []
    for lat, lon in points:
        x = math.radians(lon - lon0) * EARTH_RADIUS_M * cos_lat0
        y = math.radians(lat - lat0) * EARTH_RADIUS_M
        out.append((x, y))
    return out


def local_to_latlon(
    points: list[tuple[float, float]], origin: tuple[float, float]
) -> list[tuple[float, float]]:
    """Inverse of latlon_to_local."""
    lat0, lon0 = origin
    cos_lat0 = math.cos(math.radians(lat0))
    out = []
    for x, y in points:
        lat = lat0 + math.degrees(y / EARTH_RADIUS_M)
        lon = lon0 + math.degrees(x / (EARTH_RADIUS_M * cos_lat0))
        out.append((lat, lon))
    return out


def rotate(
    points: list[tuple[float, float]], angle_rad: float
) -> list[tuple[float, float]]:
    """Rotate points about the origin, counterclockwise, by angle_rad."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return [(x * c - y * s, x * s + y * c) for x, y in points]


def polygon_scanline_segments(
    polygon: list[tuple[float, float]], y: float
) -> list[tuple[float, float]]:
    """Intersect the horizontal line at height y with a closed polygon.

    polygon: vertices (x, y), no duplicate closing vertex.
    Returns interior segments as (x_start, x_end) pairs, sorted by x,
    using the even-odd rule. The half-open edge test makes vertex hits
    count consistently, so crossings always pair up.
    """
    xs: list[float] = []
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 <= y < y2) or (y2 <= y < y1):
            t = (y - y1) / (y2 - y1)
            xs.append(x1 + t * (x2 - x1))
    xs.sort()
    if len(xs) % 2 != 0:  # pragma: no cover - guarded against by half-open rule
        raise ValueError("scanline produced an odd number of crossings")
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs), 2)]


def point_in_polygon(
    point: tuple[float, float], polygon: list[tuple[float, float]]
) -> bool:
    """Even-odd ray cast. Boundary points are ambiguous by design."""
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 <= y < y2) or (y2 <= y < y1):
            t = (y - y1) / (y2 - y1)
            if x < x1 + t * (x2 - x1):
                inside = not inside
    return inside


def longest_edge_heading_deg(latlon_polygon: list[tuple[float, float]]) -> float:
    """Compass heading (0=N, 90=E) of the polygon's longest edge, in [0, 180).

    Used as the default sweep direction: flying along the longest edge
    minimizes the number of turns.
    """
    origin = centroid(latlon_polygon)
    pts = latlon_to_local(latlon_polygon, origin)
    best_len2 = -1.0
    best_heading = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        len2 = dx * dx + dy * dy
        if len2 > best_len2:
            best_len2 = len2
            best_heading = math.degrees(math.atan2(dx, dy)) % 180.0
    return best_heading
