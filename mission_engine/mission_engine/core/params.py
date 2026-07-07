"""Survey mission parameters: validation and JSON loading.

The JSON schema (see examples/solar_farm_params.json):

{
  "polygon": [[lat, lon], ...],   // >= 3 vertices, WGS84 degrees
  "altitude_m": 60,               // above home, > 0
  "spacing_m": 25,                // distance between flight lines, > 0
  "heading_deg": null,            // optional compass heading; null/absent = auto
  "speed_ms": 8                   // optional; null/absent = vehicle default
}

Unknown keys are rejected so typos fail loudly instead of being ignored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_ALLOWED_KEYS = {"polygon", "altitude_m", "spacing_m", "heading_deg", "speed_ms"}


@dataclass
class SurveyParams:
    polygon: list[tuple[float, float]]
    altitude_m: float
    spacing_m: float
    heading_deg: float | None = None
    speed_ms: float | None = None

    def __post_init__(self) -> None:
        self.polygon = _validated_polygon(self.polygon)

        self.altitude_m = float(self.altitude_m)
        if not self.altitude_m > 0:
            raise ValueError("altitude_m must be > 0")

        self.spacing_m = float(self.spacing_m)
        if not self.spacing_m > 0:
            raise ValueError("spacing_m must be > 0")

        if self.heading_deg is not None:
            self.heading_deg = float(self.heading_deg) % 360.0

        if self.speed_ms is not None:
            self.speed_ms = float(self.speed_ms)
            if not self.speed_ms > 0:
                raise ValueError("speed_ms must be > 0")

    @classmethod
    def from_dict(cls, data: dict) -> "SurveyParams":
        if not isinstance(data, dict):
            raise ValueError("params must be a JSON object")
        unknown = set(data) - _ALLOWED_KEYS
        if unknown:
            raise ValueError(
                f"unknown parameter(s): {sorted(unknown)}; allowed: {sorted(_ALLOWED_KEYS)}"
            )
        missing = {"polygon", "altitude_m", "spacing_m"} - set(data)
        if missing:
            raise ValueError(f"missing required parameter(s): {sorted(missing)}")
        return cls(
            polygon=data["polygon"],
            altitude_m=data["altitude_m"],
            spacing_m=data["spacing_m"],
            heading_deg=data.get("heading_deg"),
            speed_ms=data.get("speed_ms"),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "SurveyParams":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


def _validated_polygon(raw) -> list[tuple[float, float]]:
    if not isinstance(raw, (list, tuple)):
        raise ValueError("polygon must be a list of [lat, lon] pairs")
    pts: list[tuple[float, float]] = []
    for i, p in enumerate(raw):
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError(f"polygon[{i}] must be a [lat, lon] pair")
        lat, lon = float(p[0]), float(p[1])
        if not -90.0 <= lat <= 90.0:
            raise ValueError(f"polygon[{i}] latitude {lat} out of range [-90, 90]")
        if not -180.0 <= lon <= 180.0:
            raise ValueError(f"polygon[{i}] longitude {lon} out of range [-180, 180]")
        pts.append((lat, lon))
    # Tolerate a GeoJSON-style duplicate closing vertex.
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        raise ValueError("polygon needs at least 3 distinct vertices")
    return pts
