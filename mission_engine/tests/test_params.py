import unittest

from mission_engine.core.params import SurveyParams

VALID = {
    "polygon": [[33.45, -84.85], [33.45, -84.847], [33.452, -84.847], [33.452, -84.85]],
    "altitude_m": 60,
    "spacing_m": 25,
}


class TestSurveyParams(unittest.TestCase):
    def test_valid_minimal(self):
        p = SurveyParams.from_dict(dict(VALID))
        self.assertEqual(len(p.polygon), 4)
        self.assertIsNone(p.heading_deg)
        self.assertIsNone(p.speed_ms)

    def test_closing_vertex_stripped(self):
        d = dict(VALID)
        d["polygon"] = d["polygon"] + [d["polygon"][0]]
        p = SurveyParams.from_dict(d)
        self.assertEqual(len(p.polygon), 4)

    def test_unknown_key_rejected(self):
        d = dict(VALID)
        d["spacing"] = 25  # typo for spacing_m
        with self.assertRaises(ValueError) as ctx:
            SurveyParams.from_dict(d)
        self.assertIn("spacing", str(ctx.exception))

    def test_missing_required(self):
        d = dict(VALID)
        del d["altitude_m"]
        with self.assertRaises(ValueError):
            SurveyParams.from_dict(d)

    def test_bad_latitude(self):
        d = dict(VALID)
        d["polygon"] = [[91.0, 0.0], [0.0, 1.0], [1.0, 0.0]]
        with self.assertRaises(ValueError):
            SurveyParams.from_dict(d)

    def test_nonpositive_spacing(self):
        d = dict(VALID)
        d["spacing_m"] = 0
        with self.assertRaises(ValueError):
            SurveyParams.from_dict(d)

    def test_heading_normalized(self):
        d = dict(VALID)
        d["heading_deg"] = 370
        self.assertAlmostEqual(SurveyParams.from_dict(d).heading_deg, 10.0)

    def test_too_few_vertices(self):
        d = dict(VALID)
        d["polygon"] = [[33.45, -84.85], [33.45, -84.847], [33.45, -84.85]]
        with self.assertRaises(ValueError):
            SurveyParams.from_dict(d)


if __name__ == "__main__":
    unittest.main()
