"""Stateless CLI adapter.

This is the exact interface the QGC Mission Studio panel will invoke as a
short-lived child process (design doc D3):

    mission-engine generate --input params.json --output mission.plan

Exit codes: 0 success, 2 bad input. Errors go to stderr as one readable line
(the QGC panel will surface stderr to the operator).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..core.params import SurveyParams
from ..core.plan_io import build_plan, write_plan
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

    args = parser.parse_args(argv)

    if args.command == "generate":
        return _generate(args)
    parser.error(f"unknown command {args.command!r}")  # pragma: no cover
    return 2  # pragma: no cover


def _generate(args: argparse.Namespace) -> int:
    in_path = Path(args.input)
    out_path = Path(args.output) if args.output else in_path.with_suffix(".plan")

    try:
        params = SurveyParams.from_json_file(in_path)
        waypoints = generate_serpentine(params)
        plan = build_plan(params, waypoints)
        write_plan(plan, out_path)
    except FileNotFoundError:
        print(f"error: input file not found: {in_path}", file=sys.stderr)
        return 2
    except ValueError as exc:  # includes ConcaveNotSupportedError, bad JSON values
        print(f"error: {exc}", file=sys.stderr)
        return 2

    n_lines = len(waypoints) // 2
    print(f"wrote {out_path} ({n_lines} flight lines, {len(waypoints)} waypoints)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
