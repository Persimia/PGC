import math
import unittest

from mission_engine.core.geometry import (
    latlon_to_local,
    local_to_latlon,
    longest_edge_heading_deg,
    point_in_polygon,
    polygon_scanline_segments,
    rotate,
)

ORIGIN = (33.45, -84.85)


class TestProjection(unittest.TestCase):
    def test_roundtrip(self):
        pts = [(33.45, -84.85), (33.4523, -84.8477), (33.4481, -84.8534)]
        local = latlon_to_local(pts, ORIGIN)
        back = local_to_latlon(local, ORIGIN)
        for (lat1, lon1), (lat2, lon2) in zip(pts, back):
            self.assertAlmostEqual(lat1, lat2, places=9)
            self.assertAlmostEqual(lon1, lon2, places=9)

    def test_scale_is_meters(self):
        # 0.001 deg of latitude is ~111.3 m everywhere.
        (x, y), = latlon_to_local([(33.451, -84.85)], ORIGIN)
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(y, 111.2, delta=0.5)


class TestRotate(unittest.TestCase):
    def test_quarter_turn(self):
        (x, y), = rotate([(1.0, 0.0)], math.pi / 2)
        self.assertAlmostEqual(x, 0.0, places=12)
        self.assertAlmostEqual(y, 1.0, places=12)

    def test_roundtrip(self):
        pts = [(3.2, -1.7), (0.0, 4.4)]
        back = rotate(rotate(pts, 0.83), -0.83)
        for (x1, y1), (x2, y2) in zip(pts, back):
            self.assertAlmostEqual(x1, x2, places=12)
            self.assertAlmostEqual(y1, y2, places=12)


UNIT_SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


class TestScanline(unittest.TestCase):
    def test_square_midline(self):
        segs = polygon_scanline_segments(UNIT_SQUARE, 0.5)
        self.assertEqual(len(segs), 1)
        self.assertAlmostEqual(segs[0][0], 0.0)
        self.assertAlmostEqual(segs[0][1], 1.0)

    def test_line_through_vertices_still_pairs(self):
        segs = polygon_scanline_segments(UNIT_SQUARE, 0.0)
        self.assertEqual(len(segs), 1)
        self.assertAlmostEqual(segs[0][0], 0.0)
        self.assertAlmostEqual(segs[0][1], 1.0)

    def test_outside(self):
        self.assertEqual(polygon_scanline_segments(UNIT_SQUARE, 2.0), [])

    def test_u_shape_two_segments(self):
        u_shape = [
            (0, 0), (100, 0), (100, 100), (70, 100),
            (70, 30), (30, 30), (30, 100), (0, 100),
        ]
        segs = polygon_scanline_segments(u_shape, 50.0)
        self.assertEqual(len(segs), 2)


class TestPointInPolygon(unittest.TestCase):
    def test_inside_outside(self):
        self.assertTrue(point_in_polygon((0.5, 0.5), UNIT_SQUARE))
        self.assertFalse(point_in_polygon((1.5, 0.5), UNIT_SQUARE))


class TestLongestEdgeHeading(unittest.TestCase):
    def _latlon_rect(self, rotation_deg=0.0):
        # 300 m x 100 m rectangle, long axis along +x, optionally rotated CCW.
        corners = [(0.0, 0.0), (300.0, 0.0), (300.0, 100.0), (0.0, 100.0)]
        corners = rotate(corners, math.radians(rotation_deg))
        return local_to_latlon(corners, ORIGIN)

    def test_east_west_rectangle(self):
        heading = longest_edge_heading_deg(self._latlon_rect())
        self.assertAlmostEqual(heading, 90.0, places=4)

    def test_rotated_rectangle(self):
        # Rotating the +x long axis 45 deg CCW points it northeast: heading 45.
        heading = longest_edge_heading_deg(self._latlon_rect(rotation_deg=45.0))
        self.assertAlmostEqual(heading, 45.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()
