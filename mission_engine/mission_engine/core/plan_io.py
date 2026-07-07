"""Build and write QGroundControl .plan files.

A .plan file is plain JSON - no MAVLink library required. Format reference:
QGC dev guide, "Plan File Format". The structure written here is the minimal
valid shape for an ArduPilot copter: takeoff, optional speed change, survey
waypoints, RTL, plus a geofence.

The authoritative acceptance test is loading the output in stock QGC and
Mission Planner (design doc, Phase 1) - golden unit tests here only guard
against accidental structural drift.

v1 note: the inclusion geofence is exactly the survey polygon. A configurable
safety margin (buffered fence) is a planned follow-up.
"""

from __future__ import annotations

import json
from pathlib import Path

from .geometry import centroid
from .params import SurveyParams

# MAVLink enum values used in .plan files (integers by design; a dependency
# on pymavlink is not warranted for four constants).
MAV_CMD_NAV_WAYPOINT = 16
MAV_CMD_NAV_RETURN_TO_LAUNCH = 20
MAV_CMD_NAV_TAKEOFF = 22
MAV_CMD_DO_CHANGE_SPEED = 178

MAV_AUTOPILOT_ARDUPILOT = 3
MAV_TYPE_QUADROTOR = 2

MAV_FRAME_MISSION = 2
MAV_FRAME_GLOBAL_RELATIVE_ALT = 3

_DEFAULT_DISPLAY_SPEED_MS = 5.0  # QGC display fields only, not a command


def build_plan(params: SurveyParams, waypoints: list[tuple[float, float]]) -> dict:
    """Assemble the .plan JSON structure for the given survey."""
    items: list[dict] = []
    seq = 1

    items.append(
        _simple_item(
            seq,
            MAV_CMD_NAV_TAKEOFF,
            MAV_FRAME_GLOBAL_RELATIVE_ALT,
            [0, 0, 0, None, 0, 0, params.altitude_m],
        )
    )
    seq += 1

    if params.speed_ms is not None:
        # param1=1: groundspeed; param3=-1: throttle unchanged.
        items.append(
            _simple_item(
                seq,
                MAV_CMD_DO_CHANGE_SPEED,
                MAV_FRAME_MISSION,
                [1, params.speed_ms, -1, 0, 0, 0, 0],
            )
        )
        seq += 1

    for lat, lon in waypoints:
        items.append(
            _simple_item(
                seq,
                MAV_CMD_NAV_WAYPOINT,
                MAV_FRAME_GLOBAL_RELATIVE_ALT,
                [0, 0, 0, None, lat, lon, params.altitude_m],
            )
        )
        seq += 1

    items.append(
        _simple_item(seq, MAV_CMD_NAV_RETURN_TO_LAUNCH, MAV_FRAME_MISSION, [0, 0, 0, 0, 0, 0, 0])
    )

    home_lat, home_lon = centroid(params.polygon)
    speed = params.speed_ms if params.speed_ms is not None else _DEFAULT_DISPLAY_SPEED_MS

    return {
        "fileType": "Plan",
        "version": 1,
        "groundStation": "QGroundControl",
        "mission": {
            "version": 2,
            "firmwareType": MAV_AUTOPILOT_ARDUPILOT,
            "vehicleType": MAV_TYPE_QUADROTOR,
            "cruiseSpeed": speed,
            "hoverSpeed": speed,
            "plannedHomePosition": [home_lat, home_lon, 0],
            "items": items,
        },
        "geoFence": {
            "version": 2,
            "circles": [],
            "polygons": [
                {
                    "version": 1,
                    "inclusion": True,
                    "polygon": [[lat, lon] for lat, lon in params.polygon],
                }
            ],
        },
        "rallyPoints": {"version": 2, "points": []},
    }


def write_plan(plan: dict, path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
        f.write("\n")


def _simple_item(seq: int, command: int, frame: int, params7: list) -> dict:
    if len(params7) != 7:
        raise ValueError("mission item requires exactly 7 params")
    return {
        "type": "SimpleItem",
        "doJumpId": seq,
        "command": command,
        "frame": frame,
        "params": list(params7),
        "autoContinue": True,
    }
