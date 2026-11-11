import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ms_progress as mp


class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


class TestTracker(unittest.TestCase):
    def test_weighted_estimate(self):
        c = Clock()
        tr = mp.Tracker([4, 16, 4], clock=c)       # pages of three blocks
        tr.begin(0); c.t += 60; tr.end()           # 4 pages in 60 s
        st = tr.state()
        self.assertEqual((st["done"], st["remaining"]), (1, 2))
        self.assertAlmostEqual(st["left"], 300.0)  # 20 pages left at 15 s per page
        self.assertAlmostEqual(st["overall"], 4 / 24)

    def test_part_of_the_current_item(self):
        c = Clock()
        tr = mp.Tracker([10, 10], clock=c)
        tr.begin(0); c.t += 30; tr.part(0.5)
        st = tr.state()
        self.assertAlmostEqual(st["overall"], 0.25)
        self.assertAlmostEqual(st["left"], 90.0)

    def test_no_estimate_at_the_start(self):
        tr = mp.Tracker([1, 1], clock=Clock())
        tr.begin(0)
        self.assertIsNone(tr.state()["left"])

    def test_durations(self):
        self.assertEqual(mp.fmt_duration(45), "45 s")
        self.assertEqual(mp.fmt_duration(720), "12 min")
        self.assertEqual(mp.fmt_duration(80), "1 min 20 s")
        self.assertEqual(mp.fmt_duration(4800), "1 h 20 min")
        self.assertEqual(mp.fmt_duration(None), "—")


class TestSplitAndThrottle(unittest.TestCase):
    def test_split_learns(self):
        sp = mp.Split(["UV mapping", "texture"], [0.1, 0.9])
        self.assertAlmostEqual(sp.overall("texture", 0.5), 0.55)
        sp.learn([15, 10])                         # measured: UV took 60 %
        self.assertAlmostEqual(sp.overall("UV mapping", 1.0), 0.6)
        self.assertAlmostEqual(sp.overall("texture", 0.5), 0.8)

    def test_throttle(self):
        c = Clock()
        th = mp.Throttle(5, clock=c)
        self.assertTrue(th.ready(0.3))
        self.assertFalse(th.ready(0.31))
        c.t += 0.25
        self.assertTrue(th.ready(0.32))
        self.assertTrue(th.ready(1.0))             # the end is always shown


if __name__ == "__main__":
    unittest.main()
