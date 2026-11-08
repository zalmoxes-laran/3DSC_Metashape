import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ms_dd as dd


class TestRule(unittest.TestCase):
    def test_hundred_square_metres(self):
        # 100 m² · (1000/1.26)² = 62.99 M texels; / (4096² · 0.6) = 6.26 → 6
        self.assertEqual(dd.pages_for(100.0), 6)

    def test_same_as_the_old_code(self):
        def old(area, tex=4096, ratio=0.6, x=1.26):
            n = pow((10000 / x), 2) / (tex * tex * ratio)
            return max(1, int((n * area) / 100 + 0.5))
        for a in (0.3, 7.5, 42.0, 199.9, 200.1, 1234.5, 8000.0):
            self.assertEqual(dd.pages_for(a), old(a), a)

    def test_rounding_half_up(self):
        one = 4096 * 4096 * 0.6 / (1000 / 1.26) ** 2   # area of exactly one page
        self.assertEqual(dd.pages_for(one * 2.5), 3)

    def test_backwards(self):
        a = 350.0
        p = dd.pages_for(a)
        self.assertAlmostEqual(dd.texel_for(a, p), 1.26, delta=0.06)

    def test_cap_gives_the_coarser_texel(self):
        s = dd.simulate(1000.0, max_pages=12)
        self.assertTrue(s["over"])
        self.assertEqual(s["pages_cap"], 12)
        self.assertGreater(s["texel_cap"], 1.26)
        self.assertAlmostEqual(dd.pages_for(1000.0, s["texel_cap"]), 12)

    def test_faces(self):
        self.assertEqual(dd.faces_for(12.5, dd.DENSITY_TILEABLE), 12500)

    def test_bibliography(self):
        self.assertIn("10.3390/rs18020203", dd.BIBLIOGRAPHY[0])


if __name__ == "__main__":
    unittest.main()
