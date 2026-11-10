import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ms_masters as mm


def M(key, faces, label=""):
    return {"key": key, "label": label, "faces": faces, "textured": False}


class TestInventory(unittest.TestCase):
    def test_templu_mare_2015(self):
        # measured 10 Nov 2026: 40.9 M, 6.3 M, 0.6 M faces on ≈ 6 039 m²
        inv = mm.inventory([M(0, 40921320), M(1, 6287000), M(2, 628699)], 6039.3)
        self.assertEqual(inv["high"], 0)
        self.assertEqual(inv["texturable"], 0)       # no 10 000/m²: keep the highest
        self.assertEqual(inv["tileable"], 1)         # 1 041/m² is LOD0
        self.assertEqual(inv["plan"], [])            # nothing to decimate
        self.assertIn("keep for the tileset", inv["rows"][0]["role"])
        self.assertIn("lighter than LOD0", inv["rows"][2]["role"])

    def test_dense_source_makes_both(self):
        inv = mm.inventory([M(0, 30000000)], 1000.0)
        levels = [p["level"] for p in inv["plan"]]
        self.assertEqual(levels, ["texturable", "tileable"])
        self.assertEqual(inv["plan"][1]["faces"], 1000000)
        self.assertIn("geometric", inv["rows"][0]["role"])

    def test_only_light_models(self):
        inv = mm.inventory([M(0, 50000)], 1000.0)
        self.assertEqual(inv["plan"], [])
        self.assertTrue(any("cannot be made" in l for l in inv["lines"]))

    def test_no_mesh_uses_reference_area(self):
        inv = mm.inventory([], 500.0)
        self.assertTrue(any("5 000 000" in l for l in inv["lines"]))

    def test_not_measured(self):
        inv = mm.inventory([M(0, None)], None)
        self.assertTrue(any("Measure" in l for l in inv["lines"]))


if __name__ == "__main__":
    unittest.main()
