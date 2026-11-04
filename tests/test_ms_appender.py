"""The appender between projects, without Metashape: ``python3 -m unittest discover tests``."""

import datetime
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ms_appender as ma  # noqa: E402

CAMS = [
    {"label": "IMG_0001", "selected": True, "enabled": True, "group": 1},
    {"label": "IMG_0002", "selected": False, "enabled": True, "group": 1},
    {"label": "IMG_0003", "selected": True, "enabled": False, "group": 2},
    {"label": "IMG_0004", "selected": False, "enabled": False, "group": None},
]


class SelectCameras(unittest.TestCase):
    def test_modes(self):
        lab = lambda xs: [c["label"] for c in xs]
        self.assertEqual(lab(ma.select_cameras(CAMS, "selected")), ["IMG_0001", "IMG_0003"])
        self.assertEqual(lab(ma.select_cameras(CAMS, "group", 1)), ["IMG_0001", "IMG_0002"])
        self.assertEqual(lab(ma.select_cameras(CAMS, "enabled")), ["IMG_0001", "IMG_0002"])
        self.assertEqual(len(ma.select_cameras(CAMS, "all")), 4)

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            ma.select_cameras(CAMS, "visible")


class PlanPhotos(unittest.TestCase):
    def test_skip_same_path_and_repeats(self):
        p = ma.plan_photos(["/a/IMG_1.JPG", "/a/img_1.jpg", "/b/IMG_2.JPG"], ["/a/../a/IMG_1.jpg"])
        self.assertEqual(p["add"], ["/b/IMG_2.JPG"])
        self.assertEqual(len(p["skip"]), 2)

    def test_skip_same_hash_other_path(self):
        p = ma.plan_photos(["/x/IMG_9.JPG", "/y/IMG_9.JPG"], [],
                           source_hashes={"/x/IMG_9.JPG": "h1", "/y/IMG_9.JPG": "h1"})
        self.assertEqual(p, {"add": ["/x/IMG_9.JPG"], "skip": ["/y/IMG_9.JPG"]})


class PlanMarkers(unittest.TestCase):
    SRC = [
        {"label": "101", "cameras": ["IMG_0001", "IMG_0009"]},
        {"label": "60", "cameras": ["IMG_0001"]},
        {"label": "77", "cameras": ["IMG_0009"]},     # not on imported cameras
    ]

    def test_merge_by_label(self):
        plan = ma.plan_markers(self.SRC, ["IMG_0001"], ["101", "102"], mode="merge")
        self.assertEqual([(x["source_label"], x["target_label"], x["new"]) for x in plan],
                         [("101", "101", False), ("60", "60", True)])
        self.assertEqual(plan[0]["cameras"], ["IMG_0001"])

    def test_new_with_prefix_and_no_collisions(self):
        plan = ma.plan_markers(self.SRC, ["IMG_0001"], ["101", "2013_60"], mode="new", prefix="2013_")
        self.assertEqual([x["target_label"] for x in plan], ["2013_101", "2013_60_2"])
        self.assertTrue(all(x["new"] for x in plan))

    def test_merge_mode_never_reuses_a_taken_new_label(self):
        plan = ma.plan_markers([{"label": "5", "cameras": ["A"]}, {"label": "5", "cameras": ["A"]}],
                               ["A"], [], mode="merge")
        self.assertEqual([x["target_label"] for x in plan], ["5", "5_2"])


class Reference(unittest.TestCase):
    LOCAL = 'LOCAL_CS["Local Coordinates (m)",LOCAL_DATUM["Local Datum",0]]'
    S70 = 'PROJCS["Dealul Piscului 1970/ Stereo 70",AUTHORITY["EPSG","31700"]]'
    S70b = 'PROJCS["Pulkovo 1942(58) / Stereo70",AUTHORITY["EPSG","3844"]]'

    def test_actions(self):
        self.assertEqual(ma.reference_action(self.LOCAL, self.S70), "copy_disabled")
        self.assertEqual(ma.reference_action(self.S70, None), "copy_disabled")
        self.assertEqual(ma.reference_action(self.S70, self.S70), "copy")
        self.assertEqual(ma.reference_action(self.S70, self.S70b), "transform")


class Meta(unittest.TestCase):
    def test_summary(self):
        when = datetime.datetime(2026, 11, 4, 15, 30, tzinfo=datetime.timezone.utc)
        m = ma.summary_meta("/p/Excavation_2013_geo_v3.psx", "Excavation2013", "g", {"cameras": 3}, {"masks": True}, when)
        (k, v), = m.items()
        self.assertEqual(k, "3dsc_append_20261104T153000")
        self.assertEqual(json.loads(v)["counts"], {"cameras": 3})
        self.assertEqual(ma.default_group_label("/p/Excavation_2013_geo_v3.psx", "Excavation2013"),
                         "Excavation_2013_geo_v3 · Excavation2013")


if __name__ == "__main__":
    unittest.main()
