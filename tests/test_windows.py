import unittest

from headroom.windows import (
    human_window,
    parse_window,
    points_for_window,
    resolve_window,
)


class ParseWindowTests(unittest.TestCase):
    def test_canonical_day(self):
        self.assertEqual(parse_window("7d"), ("7d", 7 * 86400))

    def test_aliases(self):
        self.assertEqual(parse_window("week"), ("7d", 7 * 86400))
        self.assertEqual(parse_window("today"), ("24h", 86400))
        self.assertEqual(parse_window("1d"), ("24h", 86400))
        self.assertEqual(parse_window("month"), ("30d", 30 * 86400))

    def test_rejects_zero_and_oversize(self):
        with self.assertRaises(ValueError):
            parse_window("0h")
        with self.assertRaises(ValueError):
            parse_window("91d")
        with self.assertRaises(ValueError):
            parse_window("nope")

    def test_resolve_days(self):
        self.assertEqual(resolve_window(days=12), ("12d", 12 * 86400))
        with self.assertRaises(ValueError):
            resolve_window(days=0)
        with self.assertRaises(ValueError):
            resolve_window(days=91)

    def test_resolve_default(self):
        self.assertEqual(resolve_window(), ("7d", 7 * 86400))

    def test_points_scale(self):
        self.assertEqual(points_for_window(3600), 60)
        self.assertEqual(points_for_window(86400), 96)
        self.assertEqual(points_for_window(7 * 86400), 168)
        self.assertEqual(points_for_window(30 * 86400), 180)

    def test_human_window(self):
        self.assertEqual(human_window("7d"), "7 day")
        self.assertEqual(human_window("24h"), "24 hour")


if __name__ == "__main__":
    unittest.main()
