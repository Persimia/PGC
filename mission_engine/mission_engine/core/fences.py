"""Fence libraries: KML parsing and fail-loud mission validation.

Fences are durable assets separate from any one mission (design doc D11):
clients keep company-wide or per-site KML files drawn in Google Earth, and
the engine generates missions *against* them. On any conflict the engine
refuses with the offending zone names - it never clips or reroutes; a human
redraws the survey area.

Zone marking convention (in the placemark's <name>, or <description> as a
fallback), one tag per polygon:

    [keepout]       never enter, at any altitude
    [min_alt=50]    enter only at or above 50 m (same datum as altitude_m,
                    i.e. relative to home - assumes reasonably flat sites)
    [inclusion]     the mission must stay inside; at most one per fence set

An untagged polygon is an error: intent must be explicit (same fail-loudly
rule as unknown JSON params). Non-polygon placemarks (pins, paths) are
ignored, so ordinary annotated Google Earth files pass through cleanly.

What is validated: every survey waypoint and every straight segment between
consecutive waypoints, in the local-meters frame. NOT validated (documented
limits, both depend on the launch point which is unknown at planning time):
the takeoff climb and the RTL path. The camera swath footprint between
flight lines is also not checked - the flown path is.

Vehicle-side enforcement: build_plan() embeds [keepout] zones as exclusion
polygons and the [inclusion] zone (if any) as the inclusion polygon in the
.plan geofence. [min_alt=...] zones are generation-time checks only - a
MAVLink polygon fence cannot express "allowed above X m", and embedding one
as an exclusion would wrongly forbid legitimate overflight.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .geometry import (
    centroid,
    latlon_to_local,
    point_in_polygon_tol,
    segment_intersects_polygon,
)

# Waypoints generated from the same projection as the fence they lie on can
# differ by float noise; treat anything this close (meters) as touching.
_BOUNDARY_TOL_M = 1e-6

_TAG_RE = re.compile(
    r"\[\s*(keepout|inclusion|min_alt\s*=\s*([0-9]+(?:\.[0-9]+)?))\s*\]",
    re.IGNORECASE,
)


class FenceError(ValueError):
    """Bad fence file content (parse/tag problems)."""


class FenceViolationError(ValueError):
    """Generated mission conflicts with one or more fence zones."""


@dataclass
class FenceZone:
    name: str
    kind: str  # "keepout" | "min_alt" | "inclusion"
    polygon: list[tuple[float, float]]  # (lat, lon), no duplicate closing vertex
    min_alt_m: float | None = None  # set iff kind == "min_alt"
    source: str = ""  # file it came from, for error messages

    @property
    def label(self) -> str:
        src = f" ({Path(self.source).name})" if self.source else ""
        return f"'{self.name}'{src}"


def load_fence_files(paths: list[str | Path]) -> list[FenceZone]:
    """Parse one or more fence KML files into zones; at most one [inclusion]."""
    zones: list[FenceZone] = []
    for p in paths:
        zones.extend(parse_kml_fences(p))
    inclusions = [z for z in zones if z.kind == "inclusion"]
    if len(inclusions) > 1:
        names = ", ".join(z.label for z in inclusions)
        raise FenceError(
            f"multiple [inclusion] zones found ({names}); v1 supports exactly "
            "one inclusion fence across all fence files"
        )
    return zones


def parse_kml_fences(path: str | Path) -> list[FenceZone]:
    """Extract tagged polygon zones from a Google Earth KML file."""
    path = Path(path)
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise FenceError(f"cannot parse KML file {path}: {exc}") from exc

    zones: list[FenceZone] = []
    for placemark in _iter_local(root, "Placemark"):
        polygons = list(_iter_local(placemark, "Polygon"))
        if not polygons:
            continue  # pins, paths, and other annotations are fine to ignore

        name = _first_text(placemark, "name") or "(unnamed)"
        tag_source = name + " " + (_first_text(placemark, "description") or "")
        m = _TAG_RE.search(tag_source)
        if not m:
            raise FenceError(
                f"fence polygon '{name}' in {path.name} has no zone tag; add "
                "[keepout], [min_alt=<meters>], or [inclusion] to its name or "
                "description in Google Earth"
            )
        raw = m.group(1).lower()
        if raw.startswith("min_alt"):
            kind, min_alt = "min_alt", float(m.group(2))
            if not min_alt > 0:
                raise FenceError(f"fence polygon '{name}': min_alt must be > 0")
        else:
            kind, min_alt = raw, None

        for poly_el in polygons:
            ring = _outer_ring(poly_el, name, path.name)
            zones.append(
                FenceZone(
                    name=name,
                    kind=kind,
                    polygon=ring,
                    min_alt_m=min_alt,
                    source=str(path),
                )
            )
    return zones


def validate_mission(
    waypoints: list[tuple[float, float]],
    altitude_m: float,
    zones: list[FenceZone],
) -> None:
    """Raise FenceViolationError if the flown path conflicts with any zone.

    Checks every waypoint and every segment between consecutive waypoints.
    All geometry is evaluated in a shared local-meters frame around the
    waypoints' centroid.
    """
    if not zones:
        return

    origin = centroid(waypoints)
    wp = latlon_to_local(waypoints, origin)
    segments = list(zip(wp, wp[1:]))
    violations: list[str] = []

    for zone in zones:
        zp = latlon_to_local(zone.polygon, origin)

        if zone.kind == "inclusion":
            outside = any(
                not point_in_polygon_tol(p, zp, _BOUNDARY_TOL_M) for p in wp
            )
            crosses = any(
                segment_intersects_polygon(a, b, zp, proper_only=True)
                for a, b in segments
            )
            if outside or crosses:
                violations.append(
                    f"mission leaves inclusion fence {zone.label}"
                )
            continue

        if zone.kind == "min_alt" and altitude_m >= (zone.min_alt_m or 0.0):
            continue  # overflight at this altitude is permitted

        hit = any(point_in_polygon_tol(p, zp, _BOUNDARY_TOL_M) for p in wp) or any(
            segment_intersects_polygon(a, b, zp) for a, b in segments
        )
        if hit:
            if zone.kind == "min_alt":
                violations.append(
                    f"path enters {zone.label} below its minimum altitude "
                    f"({altitude_m:g} m < {zone.min_alt_m:g} m)"
                )
            else:
                violations.append(f"path enters keep-out zone {zone.label}")

    if violations:
        raise FenceViolationError(
            "mission conflicts with fence zones - redraw the survey area or "
            "adjust parameters: " + "; ".join(violations)
        )


# --- KML helpers (namespace-agnostic: match on local element names) ---


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _iter_local(el: ET.Element, name: str):
    for child in el.iter():
        if _local(child.tag) == name:
            yield child


def _first_text(el: ET.Element, name: str) -> str | None:
    for child in _iter_local(el, name):
        if child.text and child.text.strip():
            return child.text.strip()
    return None


def _outer_ring(
    poly_el: ET.Element, name: str, filename: str
) -> list[tuple[float, float]]:
    for outer in _iter_local(poly_el, "outerBoundaryIs"):
        coords = _first_text(outer, "coordinates")
        if coords:
            return _parse_coordinates(coords, name, filename)
    raise FenceError(
        f"fence polygon '{name}' in {filename} has no outer boundary coordinates"
    )


def _parse_coordinates(
    text: str, name: str, filename: str
) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for token in text.split():
        parts = token.split(",")
        if len(parts) < 2:
            raise FenceError(
                f"fence polygon '{name}' in {filename}: bad coordinate '{token}'"
            )
        lon, lat = float(parts[0]), float(parts[1])  # KML order is lon,lat[,alt]
        pts.append((lat, lon))
    if len(pts) >= 2 and pts[0] == pts[-1]:  # KML rings close explicitly
        pts = pts[:-1]
    if len(pts) < 3:
        raise FenceError(
            f"fence polygon '{name}' in {filename} needs at least 3 distinct vertices"
        )
    return pts
