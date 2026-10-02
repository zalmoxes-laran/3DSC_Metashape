"""The blocks of STEP2, without Metashape: ``python3 -m unittest discover tests``.

The bench on San Pietro runs when the dataset is there
(``DSC_SANPIETRO``, default ``~/Documents/GitHub/_datasets/SegniSanPietro``):
the 32 blocks of ``0c2559a`` must be stopped, the 108 of ``6192f44`` must pass.
"""

import math
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ms_blocks as mb  # noqa: E402

SANPIETRO = os.environ.get("DSC_SANPIETRO", os.path.expanduser(
    "~/Documents/GitHub/_datasets/SegniSanPietro"))
OLD_32 = os.path.join(SANPIETRO, "metashape-2026/chunks/Chunk_1_LOD0_LOD0_workflow_blocks")
NEW_108 = os.path.join(SANPIETRO, "_lavoro-claude/blocchi-3dsc-6192f44")
LOD0_FACES = 11656593          # Chunk 1_LOD0, model key 2 (doc.xml faceCount)


def write_tile(folder, name, verts, faces, mtl=True):
    with open(os.path.join(folder, name + ".obj"), "w") as fh:
        fh.write("# \n")
        if mtl:
            fh.write(f'mtllib "{name}.mtl"\nusemtl Solid\n')
        for v in verts:
            fh.write("v %f %f %f 0.5 0.5 0.5\n" % v)
        for f in faces:
            fh.write("f %d %d %d\n" % f)
    if mtl:
        with open(os.path.join(folder, name + ".mtl"), "w") as fh:
            fh.write("newmtl Solid\nKd 1 1 1\n")
    with open(os.path.join(folder, name + ".tls"), "wb") as fh:
        fh.write(b"TL\x01\x02" + name.encode())


def square(x0, y0, side=1.0, z=0.0):
    return [(x0, y0, z), (x0 + side, y0, z), (x0 + side, y0 + side, z), (x0, y0 + side, z)]


class TestCheck(unittest.TestCase):
    def test_same_content_but_mtllib_is_stopped(self):
        with tempfile.TemporaryDirectory() as d:
            write_tile(d, "a", square(0, 0), [(1, 2, 3), (1, 3, 4)])
            write_tile(d, "b", square(0, 0), [(1, 2, 3), (1, 3, 4)])
            problems = mb.check_blocks(mb.folder_stats(d), source_faces=2)
            self.assertTrue(any("same content: a.obj, b.obj" in p for p in problems), problems)

    def test_same_bbox_and_faces_is_stopped(self):
        with tempfile.TemporaryDirectory() as d:
            write_tile(d, "a", square(0, 0), [(1, 2, 3), (1, 3, 4)])
            write_tile(d, "b", square(0, 0), [(1, 2, 4), (2, 3, 4)])
            problems = mb.check_blocks(mb.folder_stats(d))
            self.assertEqual(len(problems), 1, problems)
            self.assertIn("same bbox and 2 faces: a.obj, b.obj", problems[0])

    def test_faces_over_the_ceiling_are_stopped(self):
        with tempfile.TemporaryDirectory() as d:
            write_tile(d, "a", square(0, 0), [(1, 2, 3), (1, 3, 4)])
            write_tile(d, "b", square(1, 0), [(1, 2, 3), (1, 3, 4)])
            self.assertEqual(mb.check_blocks(mb.folder_stats(d), source_faces=4), [])
            problems = mb.check_blocks(mb.folder_stats(d), source_faces=2)
            self.assertIn("2.00 × the 2 of the source", problems[0])
            with self.assertRaises(mb.BlocksRejected):
                mb.assert_blocks(mb.folder_stats(d), source_faces=2)


class TestGrid(unittest.TestCase):
    def test_names_from_the_centre(self):
        stats = [{"name": "Tile 10-20", "bbox": ((0, 0, 0), (1, 1, 1))},
                 {"name": "Tile 11-20", "bbox": ((1, 0, 0), (2, 1, 1))},
                 {"name": "Tile 10-21", "bbox": ((0, 1, 0), (0.2, 2, 1))}]
        self.assertEqual(mb.grid_names(stats, 1.0), {
            "Tile 10-20": "block_x001_y001", "Tile 11-20": "block_x002_y001",
            "Tile 10-21": "block_x001_y002"})

    def test_two_centres_in_one_cell_collide(self):
        # the bare-corner origin, shifted against the cut: two slivers meet
        stats = [{"name": "A", "bbox": ((0.0, 0, 0), (0.3, 1, 1))},
                 {"name": "B", "bbox": ((0.3, 0, 0), (0.9, 1, 1))}]
        with self.assertRaises(mb.GridCollision) as ctx:
            mb.grid_names(stats, 1.0)
        self.assertEqual(sorted(ctx.exception.collisions["block_x001_y001"]), ["A", "B"])

    def test_snapped_origin_follows_the_cut(self):
        # the cut's lines at x = k·1.0 in the CRS; the files start from 0.5
        stats = [{"name": "A", "bbox": ((-0.2, 0, 0), (0.49, 1, 1))},
                 {"name": "B", "bbox": ((0.49, 0, 0), (1.49, 1, 1))}]
        origin = mb.cut_grid_origin(stats, 1.0, (0.5, 0.0, 0.0))
        self.assertAlmostEqual(origin[0], -0.5)
        self.assertEqual(mb.grid_names(stats, 1.0, origin),
                         {"A": "block_x001_y001", "B": "block_x002_y001"})

    def test_rename_moves_three_files_and_the_mtllib(self):
        with tempfile.TemporaryDirectory() as d:
            write_tile(d, "Tile 1-2", square(0, 0), [(1, 2, 3)])
            mb.rename_tiles(d, {"Tile 1-2": "block_x001_y001"})
            self.assertEqual(sorted(os.listdir(d)),
                             ["block_x001_y001.mtl", "block_x001_y001.obj", "block_x001_y001.tls"])
            with open(os.path.join(d, "block_x001_y001.obj")) as fh:
                self.assertIn("mtllib block_x001_y001.mtl\n", fh.read())

    def test_quoted_mtllib_is_unquoted_without_spaces(self):
        with tempfile.TemporaryDirectory() as d:
            write_tile(d, "a", square(0, 0), [(1, 2, 3)])          # Metashape's quotes
            self.assertTrue(mb.unquote_mtllib(os.path.join(d, "a.obj")))
            self.assertFalse(mb.unquote_mtllib(os.path.join(d, "a.obj")))
            write_tile(d, "b c", square(0, 0), [(1, 2, 3)])
            self.assertFalse(mb.unquote_mtllib(os.path.join(d, "b c.obj")))


class TestSmallTiles(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        write_tile(self.d, "big", square(0, 0, 2), [(1, 2, 3)] * 10)
        write_tile(self.d, "mid", square(2, 0, 2), [(1, 2, 3)] * 5)
        write_tile(self.d, "tiny", square(4, 0, 0.5), [(1, 2, 3), (2, 3, 4)])
        write_tile(self.d, "alone", square(50, 50, 0.5), [(1, 2, 3)])

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_flag_moves_nothing(self):
        plan = mb.plan_small_tiles(mb.folder_stats(self.d), 3, mb.SMALL_FLAG)
        self.assertEqual(plan["merges"], [])
        self.assertEqual(sorted(plan["flagged"]), ["alone", "tiny"])

    def test_merge_into_the_largest_touching_neighbour(self):
        plan = mb.plan_small_tiles(mb.folder_stats(self.d), 3, mb.SMALL_MERGE)
        self.assertEqual(plan["merges"], [("tiny", "mid")])
        self.assertEqual(plan["flagged"], ["alone"])
        mb.apply_small_tiles(self.d, plan)
        stats = {s["name"]: s for s in mb.folder_stats(self.d)}
        self.assertEqual(stats["mid"]["faces"], 7)
        self.assertEqual(stats["mid"]["vertices"], 8)
        self.assertNotIn("tiny", stats)
        self.assertEqual(sorted(os.listdir(os.path.join(self.d, mb.ABSORBED_DIR))),
                         ["mid.tls", "tiny.mtl", "tiny.obj", "tiny.tls"])
        with open(os.path.join(self.d, "mid.obj")) as fh:
            faces = [l for l in fh if l.startswith("f ")]
        self.assertEqual(faces[-1].strip(), "f 6 7 8")    # 2 3 4 shifted past 4 vertices

    def test_face_indices_with_slashes_are_shifted(self):
        a = os.path.join(self.d, "a.obj")
        b = os.path.join(self.d, "b.obj")
        with open(a, "w") as fh:
            fh.write("v 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvn 0 0 1\nf 1/1/1 2/1/1 3/1/1\n")
        with open(b, "w") as fh:
            fh.write("v 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 1\nf 1/2 2/1 3//\n")
        mb.append_obj(a, b)
        with open(a) as fh:
            self.assertEqual(fh.read().splitlines()[-1], "f 4/3 5/2 6//")


@unittest.skipUnless(os.path.isdir(OLD_32) and os.path.isdir(NEW_108), "San Pietro not here")
class TestSanPietro(unittest.TestCase):
    """The bench on the real blocks."""

    def test_the_32_blocks_of_0c2559a_are_stopped(self):
        stats = mb.folder_stats(OLD_32)
        self.assertEqual(len(stats), 32)
        problems = mb.check_blocks(stats, LOD0_FACES)
        self.assertTrue(any(p.startswith("32 blocks have the same content") for p in problems), problems)
        self.assertTrue(any("ceiling 1.5" in p for p in problems), problems)

    def test_the_108_tiles_of_6192f44_pass(self):
        stats = mb.folder_stats(NEW_108)
        self.assertEqual(len(stats), 108)
        self.assertEqual(mb.check_blocks(stats, LOD0_FACES), [])
        size = math.sqrt(80.0)
        with self.assertRaises(mb.GridCollision):       # the bare corner: measured, 12
            mb.grid_names(stats, size)
        origin = mb.cut_grid_origin(stats, size, mb.read_srs_origin(NEW_108))
        names = mb.grid_names(stats, size, origin)
        self.assertEqual(len(set(names.values())), 108)


if __name__ == "__main__":
    unittest.main()
