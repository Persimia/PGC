import math
import unittest

from mission_engine.core.geometry import latlon_to_local, local_to_latlon, rotate
from mission_engine.core.params import SurveyParams
from mission_engine.core.survey import ConcaveNotSupportedError, generate_serpentine

ORIGIN = (33.45, -84.85)


def latlon_polygon(local_corners, rotation_deg=0.0):
    corners = rotate(local_corners, math.radians(rotation_deg))
    return [list(p) for p in local_to_latlon(corners, ORIGIN)]


RECT_300x100 = [(0.0, 0.0), (300.0, 0.0), (300.0, 100.0), (0.0, 100.0)]


class TestSerpentine(unittest.TestCase):
    def _params(self, **overrides):
        base = {
            "polygon": latlon_polygon(RECT_300x100),
            "altitude_m": 60,
            "spacing_m": 30,
            "heading_deg": 90,
        }
        base.update(overrides)
        return SurveyParams.from_dict(base)

    def test_line_count_and_pairing(self):
        wps = generate_serpentine(self._params())
        # 100 m extent / 30 m spacing -> ceil = 4 lines -> 8 waypoints.
        self.assertEqual(len(wps), 8)

    def test_lines_evenly_spaced_and_centered(self):
        wps = generate_serpentine(self._params())
        local = latlon_to_local(wps, ORIGIN)  # heading 90 -> no rotation needed
        ys = sorted({round(y, 6) for _, y in local})
        self.assertEqual(len(ys), 4)
        expected = [5.0, 35.0, 65.0, 95.0]  # centered: (100 - 3*30)/2 = 5
        for got, want in zip(ys, expected):
            self.assertAlmostEqual(got, want, places=3)

    def test_serpentine_alternates_direction(self):
        wps = generate_serpentine(self._params())
        local = latlon_to_local(wps, ORIGIN)
        starts = [local[i][0] for i in range(0, len(local), 2)]
        # Even lines start at x~0, odd lines start at x~300.
        self.assertAlmostEqual(starts[0], 0.0, delta=0.01)
        self.assertAlmostEqual(starts[1], 300.0, delta=0.01)
        self.assertAlmostEqual(starts[2], 0.0, delta=0.01)
        self.assertAlmostEqual(starts[3], 300.0, delta=0.01)

    def test_waypoints_on_polygon_edges(self):
        wps = generate_serpentine(self._params())
        local = latlon_to_local(wps, ORIGIN)
        for x, y in local:
            self.assertTrue(-0.01 <= x <= 300.01)
            self.assertTrue(-0.01 <= y <= 100.01)
            # Every waypoint of an axis-aligned rect scan sits on a side edge.
            self.assertTrue(min(abs(x - 0.0), abs(x - 300.0)) < 0.01)

    def test_auto_heading_matches_long_edge(self):
        # Same rectangle rotated 30 deg CCW; auto heading should follow it,
        # producing the same number of lines as the axis-aligned case.
        params = self._params(
            polygon=latlon_polygon(RECT_300x100, rotation_deg=30.0), heading_deg=None
        )
        wps = generate_serpentine(params)
        self.assertEqual(len(wps), 8)

    def test_single_line_for_narrow_strip(self):
        strip = [(0.0, 0.0), (300.0, 0.0), (300.0, 10.0), (0.0, 10.0)]
        params = self._params(polygon=latlon_polygon(strip))
        wps = generate_serpentine(params)
        self.assertEqual(len(wps), 2)
        local = latlon_to_local(wps, ORIGIN)
        self.assertAlmostEqual(local[0][1], 5.0, places=3)  # centered in strip

    def test_concave_raises(self):
        u_shape = [
            (0, 0), (100, 0), (100, 100), (70, 100),
            (70, 30), (30, 30), (30, 100), (0, 100),
        ]
        params = self._params(polygon=latlon_polygon(u_shape), spacing_m=20)
        with self.assertRaises(ConcaveNotSupportedError):
            generate_serpentine(params)


if __name__ == "__main__":
    unittest.main()
