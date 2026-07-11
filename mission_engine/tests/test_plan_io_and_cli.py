import json
import tempfile
import unittest
from pathlib import Path

from mission_engine.adapters import cli
from mission_engine.core.params import SurveyParams
from mission_engine.core.plan_io import (
    MAV_CMD_DO_CHANGE_SPEED,
    MAV_CMD_NAV_RETURN_TO_LAUNCH,
    MAV_CMD_NAV_TAKEOFF,
    MAV_CMD_NAV_WAYPOINT,
    build_plan,
    write_plan,
)
from mission_engine.core.survey import generate_serpentine

PARAMS_DICT = {
    "polygon": [[33.45, -84.85], [33.45, -84.847], [33.452, -84.847], [33.452, -84.85]],
    "altitude_m": 60,
    "spacing_m": 40,
    "speed_ms": 8,
}


class TestBuildPlan(unittest.TestCase):
    def setUp(self):
        self.params = SurveyParams.from_dict(dict(PARAMS_DICT))
        self.waypoints = generate_serpentine(self.params)
        self.plan = build_plan(self.params, self.waypoints)

    def test_top_level_structure(self):
        for key in ("fileType", "version", "groundStation", "mission", "geoFence", "rallyPoints"):
            self.assertIn(key, self.plan)
        self.assertEqual(self.plan["fileType"], "Plan")
        self.assertEqual(self.plan["version"], 1)

    def test_item_sequence(self):
        items = self.plan["mission"]["items"]
        self.assertEqual(items[0]["command"], MAV_CMD_NAV_TAKEOFF)
        self.assertEqual(items[1]["command"], MAV_CMD_DO_CHANGE_SPEED)
        self.assertEqual(items[-1]["command"], MAV_CMD_NAV_RETURN_TO_LAUNCH)
        waypoint_items = [i for i in items if i["command"] == MAV_CMD_NAV_WAYPOINT]
        self.assertEqual(len(waypoint_items), len(self.waypoints))
        # takeoff + speed + waypoints + RTL
        self.assertEqual(len(items), len(self.waypoints) + 3)

    def test_dojumpids_sequential(self):
        ids = [i["doJumpId"] for i in self.plan["mission"]["items"]]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))

    def test_waypoint_coordinates_and_altitude(self):
        items = self.plan["mission"]["items"]
        wp_items = [i for i in items if i["command"] == MAV_CMD_NAV_WAYPOINT]
        for item, (lat, lon) in zip(wp_items, self.waypoints):
            self.assertAlmostEqual(item["params"][4], lat, places=9)
            self.assertAlmostEqual(item["params"][5], lon, places=9)
            self.assertEqual(item["params"][6], 60)

    def test_geofence_matches_polygon(self):
        polys = self.plan["geoFence"]["polygons"]
        self.assertEqual(len(polys), 1)
        self.assertTrue(polys[0]["inclusion"])
        self.assertEqual(polys[0]["polygon"], [[lat, lon] for lat, lon in self.params.polygon])

    def test_no_speed_item_when_speed_unset(self):
        d = dict(PARAMS_DICT)
        del d["speed_ms"]
        params = SurveyParams.from_dict(d)
        plan = build_plan(params, self.waypoints)
        commands = [i["command"] for i in plan["mission"]["items"]]
        self.assertNotIn(MAV_CMD_DO_CHANGE_SPEED, commands)

    def test_json_serializable(self):
        rehydrated = json.loads(json.dumps(self.plan))
        self.assertEqual(rehydrated["fileType"], "Plan")

    def test_all_items_use_relative_alt_frame(self):
        # Frame 3 for EVERY item (including do-commands and RTL): Mission
        # Planner's grid rejects frame 2 with KeyNotFoundException on load.
        # See the comment above MAV_FRAME_GLOBAL_RELATIVE_ALT in plan_io.py.
        for item in self.plan["mission"]["items"]:
            self.assertEqual(item["frame"], 3, msg=f"item {item['doJumpId']}")


class TestCli(unittest.TestCase):
    def test_generate_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "params.json"
            out_path = Path(tmp) / "mission.plan"
            in_path.write_text(json.dumps(PARAMS_DICT), encoding="utf-8")

            rc = cli.main(["generate", "-i", str(in_path), "-o", str(out_path)])

            self.assertEqual(rc, 0)
            plan = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["fileType"], "Plan")

    def test_default_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "field.json"
            in_path.write_text(json.dumps(PARAMS_DICT), encoding="utf-8")
            rc = cli.main(["generate", "-i", str(in_path)])
            self.assertEqual(rc, 0)
            self.assertTrue((Path(tmp) / "field.plan").exists())

    def test_json_waypoints_output(self):
        # .json output = raw waypoint list for the PGC Solar Scan pattern item.
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "params.json"
            out_path = Path(tmp) / "wpts.json"
            in_path.write_text(json.dumps(PARAMS_DICT), encoding="utf-8")

            rc = cli.main(["generate", "-i", str(in_path), "-o", str(out_path)])

            self.assertEqual(rc, 0)
            data = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(data["altitude_m"], PARAMS_DICT["altitude_m"])
            self.assertGreaterEqual(len(data["waypoints"]), 2)
            self.assertEqual(len(data["waypoints"]) % 2, 0)  # entry/exit pairs
            for wp in data["waypoints"]:
                self.assertEqual(len(wp), 2)  # [lat, lon]

    def test_fences_dump(self):
        # `fences` subcommand = zone dump for GCS map rendering.
        kml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark>'
            "<name>Test zone [keepout]</name><Polygon><outerBoundaryIs><LinearRing>"
            "<coordinates>-84.1,33.1,0 -84.0,33.1,0 -84.0,33.2,0 -84.1,33.2,0 -84.1,33.1,0</coordinates>"
            "</LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>"
        )
        with tempfile.TemporaryDirectory() as tmp:
            kml_path = Path(tmp) / "zones.kml"
            out_path = Path(tmp) / "zones.json"
            kml_path.write_text(kml, encoding="utf-8")

            rc = cli.main(["fences", "-f", str(kml_path), "-o", str(out_path)])

            self.assertEqual(rc, 0)
            zones = json.loads(out_path.read_text(encoding="utf-8"))["zones"]
            self.assertEqual(len(zones), 1)
            self.assertEqual(zones[0]["kind"], "keepout")
            self.assertEqual(zones[0]["name"], "Test zone [keepout]")
            self.assertEqual(len(zones[0]["polygon"]), 4)

    def test_invalid_params_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "params.json"
            bad = dict(PARAMS_DICT, spacing_m=-5)
            in_path.write_text(json.dumps(bad), encoding="utf-8")
            rc = cli.main(["generate", "-i", str(in_path)])
            self.assertEqual(rc, 2)

    def test_missing_file_exit_code(self):
        rc = cli.main(["generate", "-i", "/nonexistent/params.json"])
        self.assertEqual(rc, 2)

    def test_waypoints_extension_writes_mp_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "params.json"
            out_path = Path(tmp) / "mission.waypoints"
            in_path.write_text(json.dumps(PARAMS_DICT), encoding="utf-8")

            rc = cli.main(["generate", "-i", str(in_path), "-o", str(out_path)])

            self.assertEqual(rc, 0)
            lines = out_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "QGC WPL 110")
            # home + takeoff + speed + waypoints + RTL rows
            waypoints = generate_serpentine(SurveyParams.from_dict(dict(PARAMS_DICT)))
            self.assertEqual(len(lines) - 1, len(waypoints) + 4)

    def test_unwritable_output_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "params.json"
            in_path.write_text(json.dumps(PARAMS_DICT), encoding="utf-8")
            rc = cli.main(
                ["generate", "-i", str(in_path), "-o", str(Path(tmp) / "no_such_dir" / "m.plan")]
            )
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
