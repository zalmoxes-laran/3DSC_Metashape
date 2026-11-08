import math, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ms_grid as g


def slab(bearing, w=16.0, h=40.0, step=0.5):
    b = math.radians(bearing)
    ux, uy = math.sin(b), math.cos(b)   # long axis
    vx, vy = math.cos(b), -math.sin(b)
    pts = []
    u = -h / 2
    while u <= h / 2 + 1e-9:
        v = -w / 2
        while v <= w / 2 + 1e-9:
            pts.append((1000 + u * ux + v * vx, 2000 + u * uy + v * vy))
            v += step
        u += step
    return pts


class TestGrid(unittest.TestCase):
    def test_fit_finds_the_bearing(self):
        for b in (0.0, 10.0, -23.5, 37.0, 80.0):
            self.assertAlmostEqual(g.fit_bearing(slab(b)), g.reduce_bearing(b), places=6)

    def test_layout_is_tight(self):
        pts = g.rotate(slab(10.0), 10.0)
        lay = g.layout(pts, 8.0)
        self.assertEqual((lay["nx"], lay["ny"]), (2, 5))
        north = g.layout(slab(10.0), 8.0)
        self.assertGreater(north["cells"], lay["cells"])

    def test_wkt(self):
        w = g.oblique_wkt('GEOGCS["x"]', 44.1, 28.6, 10.0)
        self.assertIn('PROJECTION["Oblique_Mercator"]', w)
        self.assertIn('"recitified_grid_angle",35.00000000', w)

    def test_cell_names(self):
        self.assertEqual(g.cell_of("Tile -1--2.obj"), (-1, -2))
        self.assertEqual(g.cell_of("Tile 98748-37497"), (98748, 37497))
        self.assertEqual(g.cell_of("Tile 0-3.obj"), (0, 3))
        self.assertIsNone(g.cell_of("block_x001_y002.obj"))

    def test_thin(self):
        self.assertEqual(len(g.thin(list(range(100000)), 1000)), 1000)


if __name__ == "__main__":
    unittest.main()
