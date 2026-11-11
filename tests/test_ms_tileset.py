import io, json, os, struct, sys, tempfile, unittest, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ms_tileset as ts


def glb(n_prims):
    doc = json.dumps({"meshes": [{"primitives": [{}] * n_prims}]}).encode()
    doc += b" " * ((4 - len(doc) % 4) % 4)
    binary = bytes([0x88, 0x00, 0xff, 0x10]) * 8          # a BIN chunk follows, as in real files
    body = struct.pack("<I", len(doc)) + b"JSON" + doc + struct.pack("<I", len(binary)) + b"BIN\x00" + binary
    return b"glTF" + struct.pack("<II", 2, 12 + len(body)) + body


class TestTileset(unittest.TestCase):
    def test_3tz(self):
        root = {"asset": {"version": "1.1"}, "geometricError": 10,
                "root": {"geometricError": 8.0, "transform": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 4200000.0, 2300000.0, 4400000.0, 1],
                         "content": {"uri": "0.glb"},
                         "children": [{"geometricError": 2.0, "content": {"uri": "a/1.glb"}},
                                      {"geometricError": 2.5, "content": {"uri": "a/2.glb"}}]}}
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "t.3tz")
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("tileset.json", json.dumps(root))
            z.writestr("0.glb", glb(1))
            z.writestr("a/1.glb", glb(2))
            z.writestr("a/2.glb", glb(3))
        info = ts.inspect(p)
        self.assertEqual(info["levels"], {0: 1, 1: 2})
        self.assertAlmostEqual(info["primitives_mean"], 2.0)
        self.assertEqual(info["primitives_max"], 3)
        self.assertIsNotNone(info["root"])
        self.assertIn("3 tiles", ts.report(info))
        self.assertEqual(info["errors"], {0: (8.0, 8.0), 1: (2.0, 2.5)})
        self.assertIn("L1 2–2.5", ts.report(info))

    def test_geodetic(self):
        lat, lon, h = ts.ecef_to_geodetic(6378137.0 + 100, 0, 0)
        self.assertAlmostEqual(lat, 0, places=6)
        self.assertAlmostEqual(h, 100, places=3)


if __name__ == "__main__":
    unittest.main()
