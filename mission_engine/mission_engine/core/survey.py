"""Serpentine ("lawnmower") survey generation over a polygon.

Algorithm:
1. Project the polygon to a local meters frame around its centroid.
2. Rotate the frame so the sweep heading points along +x (flight lines are
   then horizontal).
3. Lay horizontal lines spaced `spacing_m` apart, centered over the polygon's
   extent, and clip each to the polygon interior.
4. Alternate the direction of every other line, then rotate/project back.

v1 supports areas where every flight line crosses the polygon in a single
segment (convex or mildly concave shapes). Anything else raises
ConcaveNotSupportedError — flying the gap would exit the area (and the
identical geofence), so we refuse rather than guess.
"""

from __future__ import annotations

import math

from .geometry import (
    centroid,
    latlon_to_local,
    local_to_latlon,
    longest_edge_heading_deg,
    polygon_scanline_segments,
    rotate,
)
from .params import SurveyParams


class ConcaveNotSupportedError(ValueError):
    """A sweep line crossed the polygon in more than one segment."""


def generate_serpentine(params: SurveyParams) -> list[tuple[float, float]]:
    """Return serpentine survey waypoints as (lat, lon) pairs.

    Waypoints come in pairs (start and end of each flight line), ordered so
    consecutive lines are flown in opposite directions.
    """
    heading = params.heading_deg
    if heading is None:
        heading = longest_edge_heading_deg(params.polygon)

    origin = centroid(params.polygon)
    local = latlon_to_local(params.polygon, origin)

    # A compass heading h corresponds to the along-track unit vector
    # (sin h, cos h) in the east/north frame; rotating everything CCW by
    # (h - 90 deg) maps that vector onto +x.
    theta = math.radians(heading - 90.0)
    rot = rotate(local, theta)

    ys = [p[1] for p in rot]
    y_min, y_max = min(ys), max(ys)
    extent = y_max - y_min
    spacing = params.spacing_m

    n_lines = max(1, math.ceil(extent / spacing))
    # Center the set of lines within the extent so edge coverage is symmetric.
    first_y = y_min + (extent - (n_lines - 1) * spacing) / 2.0

    waypoints_rot: list[tuple[float, float]] = []
    nudge = max(extent, spacing) * 1e-9 + 1e-12
    for i in range(n_lines):
        y = first_y + i * spacing
        segments = _segments_robust(rot, y, nudge)
        if not segments:
            continue
        if len(segments) > 1:
            raise ConcaveNotSupportedError(
                "A flight line crosses the area in multiple segments (concave "
                "shape). v1 supports convex-ish areas only - split the polygon "
                "into convex pieces and plan them separately."
            )
        x_start, x_end = segments[0]
        if i % 2 == 1:
            x_start, x_end = x_end, x_start
        waypoints_rot.append((x_start, y))
        waypoints_rot.append((x_end, y))

    if not waypoints_rot:
        raise ValueError("polygon produced no flight lines (degenerate area?)")

    unrotated = rotate(waypoints_rot, -theta)
    return local_to_latlon(unrotated, origin)


def _segments_robust(
    polygon: list[tuple[float, float]], y: float, nudge: float
) -> list[tuple[float, float]]:
    """Scanline intersection, nudging y slightly if a degenerate hit occurs."""
    for candidate in (y, y + nudge, y - nudge):
        try:
            return polygon_scanline_segments(polygon, candidate)
        except ValueError:
            continue
    return []
