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

# Frame 3 (GLOBAL_RELATIVE_ALT) is used for EVERY item, including DO_ commands
# and RTL where ArduPilot ignores it. Rationale: Mission Planner's planner grid
# maps each item's frame through its altmode list {0: Absolute, 3: Relative,
# 10: Terrain}; any other value - such as 2 (MAV_FRAME_MISSION), which QGC
# emits for do-commands - raises KeyNotFoundException on load. Frame 3 is in
# the intersection all our tools accept.
MAV_FRAME_GLOBAL_RELATIVE_ALT = 3

_DEFAULT_DISPLAY_SPEED_MS = 5.0  # QGC display fields only, not a command


def build_plan(
    params: SurveyParams,
    waypoints: list[tuple[float, float]],
    zones: list | None = None,
) -> dict:
    """Assemble the .plan JSON structure for the given survey.

    zones: optional list of fences.FenceZone. [keepout] zones become
    exclusion polygons and an [inclusion] zone replaces the default
    survey-polygon inclusion fence. [min_alt] zones are generation-time
    checks only and are never embedded (see the fences module docstring).
    """
    items: list[dict] = []
    seq = 1

    items.append(
        _simple_item(
            seq,
            MAV_CMD_NAV_TAKEOFF,
            MAV_FRAME_GLOBAL_RELATIVE_ALT,
            [0, 0, 0, 0, 0, 0, params.altitude_m],
        )
    )
    seq += 1

    if params.speed_ms is not None:
        # param1=1: groundspeed; param3=-1: throttle unchanged.
        items.append(
            _simple_item(
                seq,
                MAV_CMD_DO_CHANGE_SPEED,
                MAV_FRAME_GLOBAL_RELATIVE_ALT,
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
                [0, 0, 0, 0, lat, lon, params.altitude_m],
            )
        )
        seq += 1

    items.append(
        _simple_item(seq, MAV_CMD_NAV_RETURN_TO_LAUNCH, MAV_FRAME_GLOBAL_RELATIVE_ALT, [0, 0, 0, 0, 0, 0, 0])
    )

    home_lat, home_lon = centroid(params.polygon)
    speed = params.speed_ms if params.speed_ms is not None else _DEFAULT_DISPLAY_SPEED_MS
    # Mission Planner's .plan parser (MissionFile.cs) types these two fields
    # as integers and hard-fails on "8.0"; QGC accepts either. They are
    # display/estimate fields only - the authoritative speed is the
    # DO_CHANGE_SPEED item above, which keeps the exact float.
    display_speed = int(round(speed))

    inclusion_poly = params.polygon
    exclusion_polys: list[list[tuple[float, float]]] = []
    for zone in zones or []:
        if zone.kind == "inclusion":
            inclusion_poly = zone.polygon
        elif zone.kind == "keepout":
            exclusion_polys.append(zone.polygon)

    fence_polygons = [
        {
            "version": 1,
            "inclusion": True,
            "polygon": [[lat, lon] for lat, lon in inclusion_poly],
        }
    ] + [
        {
            "version": 1,
            "inclusion": False,
            "polygon": [[lat, lon] for lat, lon in poly],
        }
        for poly in exclusion_polys
    ]

    return {
        "fileType": "Plan",
        "version": 1,
        "groundStation": "QGroundControl",
        "mission": {
            "version": 2,
            "firmwareType": MAV_AUTOPILOT_ARDUPILOT,
            "vehicleType": MAV_TYPE_QUADROTOR,
            "cruiseSpeed": display_speed,
            "hoverSpeed": display_speed,
            "plannedHomePosition": [home_lat, home_lon, 0],
            "items": items,
        },
        "geoFence": {
            "version": 2,
            "circles": [],
            "polygons": fence_polygons,
        },
        "rallyPoints": {"version": 2, "points": []},
    }


def write_plan(plan: dict, path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
        f.write("\n")


def build_waypoints_text(params: SurveyParams, waypoints: list[tuple[float, float]]) -> str:
    """Mission Planner's native .waypoints format ("QGC WPL 110").

    Tab-separated rows: INDEX CURRENT FRAME COMMAND P1 P2 P3 P4 LAT LON ALT
    AUTOCONTINUE. Row 0 is the home position. This format carries the mission
    only - geofences are uploaded separately in MP, so prefer .plan where it
    works and use this as the maximally-compatible MP path.
    """
    home_lat, home_lon = centroid(params.polygon)
    rows = [_wp_row(0, 1, 0, MAV_CMD_NAV_WAYPOINT, [0, 0, 0, 0], home_lat, home_lon, 0)]
    seq = 1

    rows.append(
        _wp_row(seq, 0, MAV_FRAME_GLOBAL_RELATIVE_ALT, MAV_CMD_NAV_TAKEOFF,
                [0, 0, 0, 0], 0, 0, params.altitude_m)
    )
    seq += 1

    if params.speed_ms is not None:
        rows.append(
            _wp_row(seq, 0, MAV_FRAME_GLOBAL_RELATIVE_ALT, MAV_CMD_DO_CHANGE_SPEED,
                    [1, params.speed_ms, -1, 0], 0, 0, 0)
        )
        seq += 1

    for lat, lon in waypoints:
        rows.append(
            _wp_row(seq, 0, MAV_FRAME_GLOBAL_RELATIVE_ALT, MAV_CMD_NAV_WAYPOINT,
                    [0, 0, 0, 0], lat, lon, params.altitude_m)
        )
        seq += 1

    rows.append(
        _wp_row(seq, 0, MAV_FRAME_GLOBAL_RELATIVE_ALT, MAV_CMD_NAV_RETURN_TO_LAUNCH,
                [0, 0, 0, 0], 0, 0, 0)
    )
    return "QGC WPL 110\n" + "\n".join(rows) + "\n"


def write_waypoints(params: SurveyParams, waypoints: list[tuple[float, float]], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(build_waypoints_text(params, waypoints))


def _wp_row(index: int, current: int, frame: int, command: int, params4: list,
            lat: float, lon: float, alt: float) -> str:
    fields = [index, current, frame, command, *params4,
              f"{lat:.8f}", f"{lon:.8f}", f"{alt:.6f}", 1]
    return "\t".join(str(f) for f in fields)


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