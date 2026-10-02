"""The stamps of 3DSC for Metashape, without Metashape.

``stamp_export`` receives a fake chunk built from the real ``doc.xml`` files of
San Pietro (``tests/fake_metashape.py``); every stamp must pass
``dtcstamp.validate_stamp``, every file set ``verify_members`` too.
"""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import dtc_stamp_ms as ds  # noqa: E402
import fake_metashape as fm  # noqa: E402

SANPIETRO = os.environ.get("DSC_SANPIETRO", os.path.expanduser(
    "~/Documents/GitHub/_datasets/SegniSanPietro"))
FILES = os.path.join(SANPIETRO, "metashape-2026/sanpietro_LOD0.files")
ORCID = "0000-0002-1825-0097"          # ORCID's own example iD (valid check digit)


class TestDtcstampReadsMetashapeObj(unittest.TestCase):
    """Pinned: dtcstamp 0.1.3 does not follow ``mtllib "<name>"`` (Metashape's
    quotes). When a dtcstamp that does arrives, this fails and
    ``ms_blocks.unquote_mtllib`` can go."""

    def test_quoted_mtllib_is_not_followed_by_dtcstamp_013(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "t.obj"), "w") as fh:
                fh.write('mtllib "t.mtl"\nv 0 0 0\nf 1 1 1\n')
            with open(os.path.join(d, "t.mtl"), "w") as fh:
                fh.write("newmtl Solid\n")
            followed = ds.dtcstamp().follow_references(os.path.join(d, "t.obj"))
            self.assertEqual(followed["missing"], ['"t.mtl"'])


class TestOrcid(unittest.TestCase):
    def test_check_digit(self):
        self.assertTrue(ds.is_valid_orcid(ORCID))
        self.assertTrue(ds.is_valid_orcid("https://orcid.org/" + ORCID))
        self.assertEqual(ds.orcid_problem("0000-0002-1825-0098"), ds.CHECKSUM)
        self.assertEqual(ds.orcid_problem("0000-0002-1825"), ds.SHAPE)
        self.assertEqual(ds.orcid_problem("  "), ds.EMPTY)

    def test_declared_operator(self):
        self.assertEqual(ds.declared_operator(ORCID, "Josiah Carberry"),
                         {"id": "https://orcid.org/" + ORCID, "label": "Josiah Carberry",
                          "auth": {"mode": "declared"}})
        self.assertIsNone(ds.declared_operator(""))
        self.assertIsNone(ds.declared_operator("0000-0002-1825-0098"))

    def test_identity_is_remembered_in_the_settings(self):
        class Settings(dict):
            def value(self, k):
                return self.get(k)

            def setValue(self, k, v):
                self[k] = v

            def save(self):
                pass

        app = fm.Obj(settings=Settings())
        self.assertEqual(ds.save_identity(ORCID, "J. C.", app), "settings")
        self.assertEqual(ds.load_identity(app), (ORCID, "J. C."))


def obj_with_texture(folder, name="mesh"):
    with open(os.path.join(folder, name + ".obj"), "w") as fh:
        fh.write(f"mtllib {name}.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nf 1/1 2/1 3/1\n")
    with open(os.path.join(folder, name + ".mtl"), "w") as fh:
        fh.write(f"newmtl m\nmap_Kd {name}.jpg\n")
    with open(os.path.join(folder, name + ".jpg"), "wb") as fh:
        fh.write(b"\xff\xd8 not really a jpeg")
    return os.path.join(folder, name + ".obj")


@unittest.skipUnless(os.path.isdir(FILES), "San Pietro not here")
class TestSanPietro(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc, cls.chunk = fm.load_chunk(FILES, "Chunk 1_LOD0")
        cls.cache = {}
        cls.dtc = ds.dtcstamp()

    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def test_the_fake_chunk_is_the_project(self):
        # the same numbers the live API gave (probe of 2 Oct 2026)
        self.assertEqual(len(self.chunk.cameras), 273)
        self.assertEqual(sum(1 for c in self.chunk.cameras if c.transform), 217)
        self.assertEqual([len(m.faces) for m in self.chunk.models], [18766128, 11656593])
        self.assertEqual(self.chunk.crs.authority, "EPSG::7791")

    def test_a_mesh_export_with_orcid(self):
        model = self.chunk.models[1]
        path = obj_with_texture(self.d)
        op = ds.declared_operator(ORCID, "Josiah Carberry")
        [res] = ds.stamp_export(self.doc, self.chunk, model, [path], op,
                                metashape_version="2.3.2", cache=self.cache,
                                parameters={"Export/format": "obj"})
        self.assertEqual(res["state"], "stamped", res["line"])
        stamp = self.dtc.read_stamp(res["stamp_path"])
        self.dtc.validate_stamp(stamp)
        self.assertTrue(self.dtc.verify_members(stamp, path)["ok"])
        self.assertEqual(stamp["self"]["packaging"], "file_set")
        self.assertEqual(stamp["self"]["tier"], "distribution")
        how = stamp["how"]
        self.assertEqual(how["dtc_kind"], "photogrammetry")
        self.assertEqual(how["technique"], "Metashape Build Model")
        p = how["parameters"]
        for key in ("AlignCameras/duration", "OptimizeCameras/fit_flags", "MatchPhotos/keypoint_limit",
                    "BuildDepthMaps/downscale", "BuildModel/face_count", "BuildModel/duration",
                    "Info/OriginalDateTime", "Info/OriginalSoftwareVersion"):
            self.assertIn(key, p)
            self.assertIn(key, p["3DSC/read_from_meta"])
        self.assertIs(p["AlignCameras/reset_alignment"], True)
        self.assertEqual(p["BuildDepthMaps/downscale"], 2)
        self.assertEqual(p["cameras/total"], 273)
        self.assertEqual(p["cameras/aligned"], 217)
        self.assertEqual(p["markers/active"], [])           # point 1 is disabled
        self.assertEqual(p["chunk/crs"], "EPSG::7791")
        self.assertEqual(p["Export/format"], "obj")
        self.assertEqual([s["name"] for s in how["software"]],
                         ["Agisoft Metashape", "3DSC for Metashape", "dtcstamp"])
        self.assertEqual(stamp["by"]["operator"]["id"], "https://orcid.org/" + ORCID)
        # from: the master, the drone by its 69 stamps, the Canon as a tree
        master = stamp["from"][0]
        self.assertEqual((master["tier"], master["packaging"]), ("master", "datablock"))
        self.assertEqual(master["state"], {"saved": True})
        sensors = {s["sensor"]: s for s in p["photos/sensors"]}
        self.assertEqual(sensors["FC300X (3.61mm)"]["cited_as"], "stamps")
        self.assertEqual(sensors["Canon EOS 6D, EF24mm f/2.8 IS USM (24mm)"]["cited_as"], "tree")
        photo = [e for e in stamp["from"] if "FC300X" in e.get("label", "")]
        self.assertEqual(len(photo), 69)
        trees = [e for e in stamp["from"] if e.get("packaging") == "directory"]
        self.assertEqual(len(trees), 1)
        self.assertEqual(len(stamp["from"]), 1 + 69 + 1)
        # the master's psx:// is in the private hints, never in the stamp
        text = json.dumps(stamp)
        self.assertNotIn("psx://", text)
        self.assertNotIn(self.d, text)
        hints = self.dtc.read_hints(res["hints_path"])
        [seen] = hints["from"][master["resource_id"]]
        self.assertTrue(seen["locator"].startswith("psx://"))
        self.assertTrue(seen["locator"].endswith("#Chunk%201_LOD0/model/2"))
        self.assertEqual((seen["kind"], seen["scope"]), ("local", "private"))
        self.assertEqual(self.dtc.for_export(hints)["seen"], [])

    def test_anonymous_names_no_operator(self):
        path = obj_with_texture(self.d)
        [res] = ds.stamp_export(self.doc, self.chunk, self.chunk.models[1], [path], None,
                                cache=self.cache)
        stamp = self.dtc.read_stamp(res["stamp_path"])
        self.assertNotIn("operator", stamp["by"])
        self.assertIn("at", stamp["by"])

    def test_the_blocks_share_one_process_and_cite_the_source(self):
        paths = []
        for i in range(3):
            paths.append(obj_with_texture(self.d, f"block_x00{i + 1}_y001"))
        tile = fm.Model(key=3, label="Tile 93345-516970", faces=range(2743),
                        meta={"Info/OriginalDateTime": "2026:10:02 12:08:25",
                              "Info/OriginalSoftwareVersion": "2.3.2.22956"})
        source = self.chunk.models[1]
        results = ds.stamp_export(
            self.doc, self.chunk, tile, paths, None, sources=[source],
            dtc_kind=ds.KIND_TILING, technique="Metashape Block Model, blocks_size 8,94 m",
            parameters={"BuildModel/blocks_size": 8.944}, cache=self.cache)
        stamps = [self.dtc.read_stamp(r["stamp_path"]) for r in results]
        self.assertEqual(len({s["how"]["process_id"] for s in stamps}), 1)
        for s, path in zip(stamps, paths):
            self.dtc.validate_stamp(s)
            self.assertTrue(self.dtc.verify_members(s, path)["ok"])
            self.assertEqual(s["how"]["dtc_kind"], "tiling")
            self.assertEqual(len(s["from"]), 2)                # tile master + source model
            self.assertNotIn("cameras/total", s["how"]["parameters"])
            self.assertEqual(s["how"]["parameters"]["3DSC/read_from_meta"],
                             ["Info/OriginalDateTime", "Info/OriginalSoftwareVersion"])

    def test_an_imported_mesh_is_an_export_and_a_dem_has_no_kind(self):
        path = obj_with_texture(self.d)
        imported = fm.Model(key=9, label="", faces=range(3), meta={"Info/OriginalDateTime": "x"})
        [res] = ds.stamp_export(self.doc, self.chunk, imported, [path], None, cache=self.cache)
        self.assertEqual(res["stamp"]["how"]["dtc_kind"], "export")
        self.assertNotIn("FC300X", json.dumps(res["stamp"]["from"]))   # no photos
        [res] = ds.stamp_export(self.doc, self.chunk, imported, [path], None,
                                georef_export=True, cache=self.cache)
        self.assertEqual(res["state"], "unchanged")       # the same bytes: the stamp stands
        other = obj_with_texture(self.d, "shifted")
        [res] = ds.stamp_export(self.doc, self.chunk, imported, [other], None,
                                georef_export=True, cache=self.cache)
        self.assertEqual(res["stamp"]["how"]["dtc_kind"], "georeferencing")  # 69 GPS refs
        dem = fm.Elevation(key=1, label="", meta={"BuildDem/duration": "3.2"})
        tif = os.path.join(self.d, "dem.tif")
        with open(tif, "wb") as fh:
            fh.write(b"II*\x00")
        [res] = ds.stamp_export(self.doc, self.chunk, dem, [tif], None, cache=self.cache)
        self.assertNotIn("dtc_kind", res["stamp"]["how"])
        self.assertEqual(res["stamp"]["self"]["media_type"], "image/tiff")

    def test_unsaved_project_is_said_in_the_state(self):
        doc = fm.Obj(path=self.doc.path, modified=True)
        path = obj_with_texture(self.d)
        [res] = ds.stamp_export(doc, self.chunk, self.chunk.models[1], [path], None,
                                photos=False, cache=self.cache)
        self.assertIs(res["stamp"]["from"][0]["state"]["saved"], False)


if __name__ == "__main__":
    unittest.main()
