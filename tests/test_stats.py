import unittest

from system_health_check.parse import cloudwatch_stats, percentile, series_stats


class StatsTests(unittest.TestCase):
    def test_percentile_empty_and_single(self):
        self.assertIsNone(percentile([], 95))
        self.assertEqual(percentile([10], 95), 10)

    def test_percentile_interpolates(self):
        values = list(range(1, 101))
        self.assertEqual(percentile(values, 95), 95.05)

    def test_series_stats(self):
        s = series_stats([10, 20, None, 30])
        self.assertEqual(s["samples"], 3)
        self.assertEqual(s["avg"], 20.0)
        self.assertEqual(s["min"], 10)
        self.assertEqual(s["max"], 30)
        self.assertEqual(s["peak"], 30)
        self.assertIsNotNone(s["p95"])

    def test_series_stats_empty(self):
        s = series_stats([])
        self.assertEqual(s["samples"], 0)
        self.assertIsNone(s["avg"])

    def test_cloudwatch_uses_max_series_peak(self):
        s = cloudwatch_stats([10, 20, 30], max_series=[40, 50, 60])
        self.assertEqual(s["avg"], 20.0)
        self.assertEqual(s["max"], 60)
        self.assertEqual(s["peak"], 60)
        self.assertEqual(s["min"], 10)


if __name__ == "__main__":
    unittest.main()
