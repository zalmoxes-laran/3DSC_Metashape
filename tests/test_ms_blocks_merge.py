"""Small tiles merge only into a tile that shares a side (Templu Mare, 10 Nov 2026)."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ms_blocks as mb


def T(name, faces, x0, y0, s=8.0, pad=1.5):
    # pad > 0: the bbox of a turned cell, drawn in the chunk CRS, is larger than the cell
    return {"name": name, "faces": faces,
            "bbox": ((x0 - pad, y0 - pad, 0.0), (x0 + s + pad, y0 + s + pad, 1.0))}


class TestSmallTiles(unittest.TestCase):
    def test_diagonal_is_not_a_neighbour(self):
        plan = mb.plan_small_tiles([T("Tile 0-0", 9000, 0, 0), T("Tile 1-1", 100, 8, 8)], 2000)
        self.assertEqual(plan["merges"], [])
        self.assertEqual(plan["flagged"], ["Tile 1-1"])
        self.assertEqual(plan["neighbours_by"], "grid cells")

    def test_no_chain_through_a_grown_block(self):
        stats = [T("Tile 0-0", 9000, 0, 0), T("Tile 1-0", 100, 8, 0), T("Tile 2-1", 150, 16, 8)]
        plan = mb.plan_small_tiles(stats, 2000)
        self.assertEqual(plan["merges"], [("Tile 1-0", "Tile 0-0")])
        self.assertEqual(plan["flagged"], ["Tile 2-1"])

    def test_merges_stay_contiguous(self):
        stats = [T("Tile 0-0", 9000, 0, 0), T("Tile 1-0", 500, 8, 0), T("Tile 2-0", 100, 16, 0)]
        plan = mb.plan_small_tiles(stats, 2000)
        self.assertEqual(sorted(plan["merges"]), [("Tile 1-0", "Tile 0-0"), ("Tile 2-0", "Tile 0-0")])

    def test_largest_side_neighbour_wins(self):
        stats = [T("Tile 0-0", 3000, 0, 0), T("Tile 1-1", 8000, 8, 8), T("Tile 1-0", 100, 8, 0)]
        plan = mb.plan_small_tiles(stats, 2000)
        self.assertEqual(plan["merges"], [("Tile 1-0", "Tile 1-1")])

    def test_negative_cells(self):
        self.assertEqual(mb.tile_cell("Tile -1--2.obj"), (-1, -2))
        self.assertIsNone(mb.tile_cell("block_x001_y001"))

    def test_bbox_fallback_ignores_corners(self):
        a = ((0, 0, 0), (8, 8, 1))
        self.assertFalse(mb.bboxes_touch(a, ((8, 8, 0), (16, 16, 1))))
        self.assertTrue(mb.bboxes_touch(a, ((8, 0, 0), (16, 8, 1))))


if __name__ == "__main__":
    unittest.main()


class TestSmallByArea(unittest.TestCase):
    def test_plan_area_of_an_obj(self):
        import tempfile
        d = tempfile.mkdtemp()
        p = os.path.join(d, "Tile 0-0.obj")
        with open(p, "w") as fh:   # a 4 × 5 m rectangle, plus a vertical wall that covers no ground
            fh.write("v 0 0 0\nv 4 0 0\nv 4 5 0\nv 0 5 0\nv 0 0 3\nv 4 0 3\nf 1 2 3 4\nf 1 2 6 5\n")
        st = mb.obj_stats(p)
        self.assertAlmostEqual(st["plan_area"], 20.0)
        self.assertEqual(st["faces"], 2)

    def test_twenty_of_eighty_joins(self):
        big = dict(T("Tile 0-0", 500, 0, 0), plan_area=80.0)
        thin = dict(T("Tile 1-0", 90000, 8, 0), plan_area=20.0)      # many faces, little ground
        plan = mb.plan_small_tiles([big, thin], min_area=80.0 * 0.33)
        self.assertEqual(plan["merges"], [("Tile 1-0", "Tile 0-0")])
        self.assertIn("plan area", plan["rule"])

    def test_merged_area_counts(self):
        a = dict(T("Tile 0-0", 1, 0, 0), plan_area=10.0)
        b = dict(T("Tile 1-0", 1, 8, 0), plan_area=12.0)
        c = dict(T("Tile 5-5", 1, 40, 40), plan_area=60.0)
        plan = mb.plan_small_tiles([a, b, c], min_area=20.0)
        self.assertEqual(plan["merges"], [("Tile 0-0", "Tile 1-0")])   # 22 m² after: no longer small
        self.assertEqual(plan["flagged"], [])


class TestNextDoorFirst(unittest.TestCase):
    def test_half_row_joins_its_own_column(self):
        # the two half cells of the last row: each joins the cell beside it in its column
        stats = [dict(T("Tile 0-1", 1, 0, 8), plan_area=64.0), dict(T("Tile 1-1", 1, 8, 8), plan_area=64.0),
                 dict(T("Tile 0-2", 1, 0, 16), plan_area=32.0), dict(T("Tile 1-2", 1, 8, 16), plan_area=33.0)]
        plan = mb.plan_small_tiles(stats, min_area=38.4)
        self.assertEqual(sorted(plan["merges"]), [("Tile 0-2", "Tile 0-1"), ("Tile 1-2", "Tile 1-1")])
