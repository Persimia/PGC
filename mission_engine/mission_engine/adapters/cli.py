"""Stateless CLI adapter.

This is the exact interface the QGC Mission Studio panel will invoke as a
short-lived child process (design doc D3):

    mission-engine generate --input params.json --output mission.plan

Output format is inferred from the --output extension: ".waypoints" writes
Mission Planner's native format; ".json" writes the raw waypoint list (the
format the PGC Solar Scan pattern item consumes — see qgc-overlay); anything
else writes a QGC .plan.

Fence libraries (repeatable --fence KML files, see core/fences.py for the
zone tag convention) are validated against before anything is written; a
conflict exits 2 with the offending zone names. [keepout]/[inclusion] zones
are embedded in .plan geofences; .waypoints carries no fence (upload fences
separately in Mission Planner).

Exit codes: 0 success, 2 bad input. Errors go to stderr as one readable line
(the QGC panel will surface stderr to the operator).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..core.fences import load_fence_files, validate_mission
from ..core.params import SurveyParams
from ..core.plan_io import build_plan, write_plan, write_waypoints
from ..core.survey import generate_serpentine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mission-engine",
        description="Parametric mission generation for ArduPilot surveys.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate a survey .plan from a params JSON file.")
    gen.add_argument("--input", "-i", required=True, help="Path to params JSON file.")
    gen.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output .plan path (default: input name with .plan extension).",
    )
    gen.add_argument(
        "--fence",
        "-f",
        action="append",
        default=[],
        metavar="KML",
        help="Fence library KML file; repeatable. Zones must be tagged "
        "[keepout], [min_alt=<m>], or [inclusion] in their name/description.",
    )

    dump = sub.add_parser(
        "fences",
        help="Dump fence-library zones as JSON (for GCS map rendering).",
    )
    dump.add_argument(
        "--fence",
        "-f",
        action="append",
        default=[],
        metavar="KML",
        help="Fence library KML file; repeatable.",
    )
    dump.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output JSON path (default: stdout).",
    )

    args = parser.parse_args(argv)

    if args.command == "generate":
        return _generate(args)
    if args.command == "fences":
        return _dump_fences(args)
    parser.error(f"unknown command {args.command!r}")  # pragma: no cover
    return 2  # pragma: no cover


def _generate(args: argparse.Namespace) -> int:
    in_path = Path(args.input)
    out_path = Path(args.output) if args.output else in_path.with_suffix(".plan")

    try:
        params = SurveyParams.from_json_file(in_path)
    except FileNotFoundError:
        print(f"error: input file not found: {in_path}", file=sys.stderr)
        return 2
    except ValueError as exc:  # bad JSON or bad parameter values
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        zones = load_fence_files(args.fence)
    except FileNotFoundError as exc:
        print(f"error: fence file not found: {exc.filename}", file=sys.stderr)
        return 2
    except ValueError as exc:  # FenceError
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        waypoints = generate_serpentine(params)
        validate_mission(waypoints, params.altitude_m, zones)
    except ValueError as exc:  # ConcaveNotSupportedError, FenceViolationError
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        if out_path.suffix.lower() == ".waypoints":
            write_waypoints(params, waypoints, out_path)
        elif out_path.suffix.lower() == ".json":
            _write_waypoints_json(params, waypoints, out_path)
        else:
            plan = build_plan(params, waypoints, zones)
            write_plan(plan, out_path)
    except OSError as exc:
        print(
            f"error: cannot write output file {out_path}: {exc} "
            "(does the output directory exist?)",
            file=sys.stderr,
        )
        return 2

    n_lines = len(waypoints) // 2
    fence_note = f", validated against {len(zones)} fence zone(s)" if zones else ""
    print(
        f"wrote {out_path} ({n_lines} flight lines, {len(waypoints)} waypoints"
        f"{fence_note})"
    )
    return 0


def _dump_fences(args: argparse.Namespace) -> int:
    try:
        zones = load_fence_files(args.fence)
    except FileNotFoundError as exc:
        print(f"error: fence file not found: {exc.filename}", file=sys.stderr)
        return 2
    except ValueError as exc:  # FenceError
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(
        {
            "zones": [
                {
                    "name": z.name,
                    "kind": z.kind,
                    "min_alt_m": z.min_alt_m,
                    "source": z.source,
                    "polygon": [[lat, lon] for lat, lon in z.polygon],
                }
                for z in zones
            ]
        },
        indent=2,
    )
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


def _write_waypoints_json(params: SurveyParams, waypoints: list, out_path: Path) -> None:
    """Raw serpentine output for in-process consumers (PGC Solar Scan item).

    Waypoints are ordered flight-line pairs: [entry, exit, entry, exit, ...].
    """
    out_path.write_text(
        json.dumps(
            {
                "altitude_m": params.altitude_m,
                "waypoints": [[lat, lon] for lat, lon in waypoints],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
