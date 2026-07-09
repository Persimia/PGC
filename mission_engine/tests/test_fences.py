import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from mission_engine.adapters import cli
from mission_engine.core.fences import (
    FenceError,
    FenceViolationError,
    FenceZone,
    load_fence_files,
    parse_kml_fences,
    validate_mission,
)
from mission_engine.core.params import SurveyParams
from mission_engine.core.plan_io import build_plan
from mission_engine.core.survey import generate_serpentine

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

# Same demo site as examples/solar_farm_params.json.
PARAMS_DICT = {
    "polygon": [[33.4490, -84.8520], [33.4490, -84.8460], [33.4530, -84.8460], [33.4530, -84.8520]],
    "altitude_m": 60,
    "spacing_m": 40,
    "speed_ms": 8,
}


def _kml(placemarks: str) -> str:
    return textwrap.dedent(
        f"""<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://www.opengis.net/kml/2.2"><Document>
        {placemarks}
        </Document></kml>"""
    )


def _poly_placemark(name: str, ring_lonlat: list[tuple[float, float]], description: str = "") -> str:
    coords = " ".join(f"{lon},{lat},0" for lon, lat in ring_lonlat + ring_lonlat[:1])
    desc = f"<description>{description}</description>" if description else ""
    return (
        f"<Placemark><name>{name}</name>{desc}"
        f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{coords}"
        "</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>"
    )


def _write_kml(tmp: str, content: str, filename: str = "fences.kml") -> Path:
    p = Path(tmp) / filename
    p.write_text(content, encoding="utf-8")
    return p


# lon,lat rings used across tests (around the demo site)
SQUARE_IN_SITE = [(-84.8500, 33.4505), (-84.8490, 33.4505), (-84.8490, 33.4515), (-84.8500, 33.4515)]
SQUARE_FAR_AWAY = [(-84.9000, 33.4000), (-84.8990, 33.4000), (-84.8990, 33.4010), (-84.9000, 33.4010)]
BIG_CONTAINER = [(-84.8600, 33.4400), (-84.8400, 33.4400), (-84.8400, 33.4600), (-84.8600, 33.4600)]


class TestKmlParsing(unittest.TestCase):
    def test_example_file_parses(self):
        zones = parse_kml_fences(EXAMPLES / "site_fences.kml")
        kinds = sorted(z.kind for z in zones)
        self.assertEqual(kinds, ["inclusion", "keepout", "min_alt"])
        min_alt = next(z for z in zones if z.kind == "min_alt")
        self.assertEqual(min_alt.min_alt_m, 40.0)
        # KML lon,lat order flipped to (lat, lon), closing vertex dropped
        for z in zones:
            self.assertGreaterEqual(len(z.polygon), 3)
            self.assertNotEqual(z.polygon[0], z.polygon[-1])
            for lat, lon in z.polygon:
                self.assertTrue(33 < lat < 34 and -85 < lon < -84)

    def test_untagged_polygon_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_kml(tmp, _kml(_poly_placemark("Mystery zone", SQUARE_IN_SITE)))
            with self.assertRaisesRegex(FenceError, "no zone tag"):
                parse_kml_fences(p)

    def test_tag_in_description_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_kml(
                tmp, _kml(_poly_placemark("Substation", SQUARE_IN_SITE, "site rule [keepout]"))
            )
            (zone,) = parse_kml_fences(p)
            self.assertEqual(zone.kind, "keepout")

    def test_pins_and_paths_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_kml(
                tmp,
                _kml(
                    "<Placemark><name>gate</name><Point><coordinates>"
                    "-84.85,33.45,0</coordinates></Point></Placemark>"
                ),
            )
            self.assertEqual(parse_kml_fences(p), [])

    def test_multiple_inclusions_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_kml(
                tmp,
                _kml(
                    _poly_placemark("A [inclusion]", BIG_CONTAINER)
                    + _poly_placemark("B [inclusion]", BIG_CONTAINER)
                ),
            )
            with self.assertRaisesRegex(FenceError, "multiple \\[inclusion\\]"):
                load_fence_files([p])

    def test_bad_min_alt_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_kml(tmp, _kml(_poly_placemark("wires [min_alt=0]", SQUARE_IN_SITE)))
            with self.assertRaisesRegex(FenceError, "min_alt must be > 0"):
                parse_kml_fences(p)


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.params = SurveyParams.from_dict(dict(PARAMS_DICT))
        self.waypoints = generate_serpentine(self.params)

    def _zone(self, kind, ring_lonlat, min_alt=None, name="Z"):
        return FenceZone(
            name=name,
            kind=kind,
            polygon=[(lat, lon) for lon, lat in ring_lonlat],
            min_alt_m=min_alt,
        )

    def test_no_zones_is_noop(self):
        validate_mission(self.waypoints, 60, [])

    def test_keepout_inside_survey_fails(self):
        zone = self._zone("keepout", SQUARE_IN_SITE, name="Substation A")
        with self.assertRaisesRegex(FenceViolationError, "Substation A"):
            validate_mission(self.waypoints, 60, [zone])

    def test_keepout_far_away_passes(self):
        validate_mission(self.waypoints, 60, [self._zone("keepout", SQUARE_FAR_AWAY)])

    def test_keepout_crossed_but_no_waypoint_inside_fails(self):
        # A thin N-S strip through the site: flight lines cross it even
        # though no waypoint (line endpoint) lies inside.
        strip = [(-84.8491, 33.4485), (-84.8489, 33.4485), (-84.8489, 33.4535), (-84.8491, 33.4535)]
        with self.assertRaises(FenceViolationError):
            validate_mission(self.waypoints, 60, [self._zone("keepout", strip)])

    def test_min_alt_pass_at_or_above(self):
        zone = self._zone("min_alt", SQUARE_IN_SITE, min_alt=40)
        validate_mission(self.waypoints, 60, [zone])
        validate_mission(self.waypoints, 40, [zone])

    def test_min_alt_fail_below(self):
        zone = self._zone("min_alt", SQUARE_IN_SITE, min_alt=80, name="HV corridor")
        with self.assertRaisesRegex(FenceViolationError, "below its minimum altitude"):
            validate_mission(self.waypoints, 60, [zone])

    def test_inclusion_containing_site_passes(self):
        validate_mission(self.waypoints, 60, [self._zone("inclusion", BIG_CONTAINER)])

    def test_inclusion_equal_to_survey_polygon_passes(self):
        # Waypoints lie exactly ON this boundary; tolerance must accept them.
        zone = FenceZone(name="site", kind="inclusion", polygon=list(self.params.polygon))
        validate_mission(self.waypoints, 60, [zone])

    def test_inclusion_smaller_than_survey_fails(self):
        zone = self._zone("inclusion", SQUARE_IN_SITE, name="tiny yard")
        with self.assertRaisesRegex(FenceViolationError, "leaves inclusion fence"):
            validate_mission(self.waypoints, 60, [zone])

    def test_all_violations_reported_together(self):
        zones = [
            self._zone("keepout", SQUARE_IN_SITE, name="Substation A"),
            self._zone("min_alt", SQUARE_IN_SITE, min_alt=80, name="HV corridor"),
        ]
        with self.assertRaises(FenceViolationError) as ctx:
            validate_mission(self.waypoints, 60, zones)
        msg = str(ctx.exception)
        self.assertIn("Substation A", msg)
        self.assertIn("HV corridor", msg)


class TestPlanEmbedding(unittest.TestCase):
    def test_keepouts_and_inclusion_embedded(self):
        params = SurveyParams.from_dict(dict(PARAMS_DICT))
        waypoints = generate_serpentine(params)
        zones = [
            FenceZone("site", "inclusion", [(lat, lon) for lon, lat in BIG_CONTAINER]),
            FenceZone("sub", "keepout", [(lat, lon) for lon, lat in SQUARE_FAR_AWAY]),
            FenceZone("hv", "min_alt", [(lat, lon) for lon, lat in SQUARE_FAR_AWAY], 40),
        ]
        plan = build_plan(params, waypoints, zones)
        polys = plan["geoFence"]["polygons"]
        self.assertEqual(len(polys), 2)  # inclusion + keepout; min_alt NOT embedded
        self.assertTrue(polys[0]["inclusion"])
        self.assertEqual(polys[0]["polygon"], [[lat, lon] for lon, lat in BIG_CONTAINER])
        self.assertFalse(polys[1]["inclusion"])

    def test_no_zones_keeps_survey_polygon_fence(self):
        params = SurveyParams.from_dict(dict(PARAMS_DICT))
        waypoints = generate_serpentine(params)
        plan = build_plan(params, waypoints)
        polys = plan["geoFence"]["polygons"]
        self.assertEqual(len(polys), 1)
        self.assertTrue(polys[0]["inclusion"])
        self.assertEqual(polys[0]["polygon"], [[lat, lon] for lat, lon in params.polygon])


class TestCliFences(unittest.TestCase):
    def test_example_params_pass_example_fences(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "m.plan"
            rc = cli.main(
                [
                    "generate",
                    "-i", str(EXAMPLES / "solar_farm_params.json"),
                    "-o", str(out),
                    "-f", str(EXAMPLES / "site_fences.kml"),
                ]
            )
            self.assertEqual(rc, 0)
            plan = json.loads(out.read_text(encoding="utf-8"))
            # inclusion (from KML) + substation keepout
            self.assertEqual(len(plan["geoFence"]["polygons"]), 2)

    def test_violation_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "params.json"
            in_path.write_text(json.dumps(PARAMS_DICT), encoding="utf-8")
            kml = _write_kml(tmp, _kml(_poly_placemark("Substation A [keepout]", SQUARE_IN_SITE)))
            rc = cli.main(["generate", "-i", str(in_path), "-o", str(Path(tmp) / "m.plan"), "-f", str(kml)])
            self.assertEqual(rc, 2)
            self.assertFalse((Path(tmp) / "m.plan").exists())  # nothing written on failure

    def test_missing_fence_file_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "params.json"
            in_path.write_text(json.dumps(PARAMS_DICT), encoding="utf-8")
            rc = cli.main(["generate", "-i", str(in_path), "-f", "/nonexistent/f.kml"])
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
