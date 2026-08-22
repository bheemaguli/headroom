import unittest

from system_health_check.advice import advice_from_windows


def _stat(avg=None, mx=None, p95=None, samples=10):
    return {"avg": avg, "max": mx, "peak": mx, "p95": p95, "min": None, "samples": samples}


class AdviceTests(unittest.TestCase):
    def test_empty_window(self):
        tips = advice_from_windows({}, {"ram_total_gb": 16}, focus="7d")
        self.assertEqual(tips, ["Not enough data to analyse this range yet."])

    def test_high_ram_avg(self):
        windows = {
            "7d": {
                "ram": _stat(avg=75, mx=90, p95=85),
                "cpu": _stat(avg=10, mx=20, p95=15),
                "gpu": _stat(avg=5, mx=10, p95=8),
            }
        }
        tips = advice_from_windows(windows, {"ram_total_gb": 16, "gpu": 5}, focus="7d")
        self.assertTrue(any("RAM averages high" in t for t in tips))
        self.assertTrue(tips[0].startswith("Based on 7 day usage analysis"))

    def test_no_gpu_metrics(self):
        windows = {
            "7d": {
                "ram": _stat(avg=30, mx=40, p95=35),
                "cpu": _stat(avg=10, mx=20, p95=15),
                "gpu": _stat(samples=0),
            }
        }
        tips = advice_from_windows(windows, {"ram_total_gb": 32, "gpu": None}, focus="7d")
        self.assertTrue(any("no GPU metrics" in t for t in tips))

    def test_nothing_maxed(self):
        windows = {
            "14d": {
                "ram": _stat(avg=20, mx=30, p95=25),
                "cpu": _stat(avg=10, mx=40, p95=20),
                "gpu": _stat(avg=2, mx=5, p95=3),
            }
        }
        tips = advice_from_windows(windows, {"ram_total_gb": 32, "gpu": 1}, focus="14d")
        self.assertEqual(len(tips), 1)
        self.assertIn("nothing looks maxed", tips[0])
        self.assertTrue(tips[0].startswith("Based on 14 day usage analysis"))


if __name__ == "__main__":
    unittest.main()
