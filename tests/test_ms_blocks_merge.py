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
