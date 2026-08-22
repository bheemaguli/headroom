import json
import unittest
from pathlib import Path

from system_health_check.parse import dimension_names, rows_from_payload

FIXTURES = Path(__file__).parent / "fixtures"


class ParsePayloadTests(unittest.TestCase):
    def test_v1_labels_and_newest_first_reversed(self):
        payload = json.loads((FIXTURES / "cpu_v1.json").read_text())
        self.assertEqual(dimension_names(payload), ["user", "system", "idle"])
        rows = rows_from_payload(payload)
        self.assertEqual([ts for ts, _ in rows], [1001.0, 1002.0, 1003.0])
        self.assertEqual(rows[-1][1][2], 85.0)

    def test_v2_result_data_and_dimension_names(self):
        payload = json.loads((FIXTURES / "ram_v2.json").read_text())
        self.assertEqual(dimension_names(payload), ["used", "free", "cached", "buffers"])
        rows = rows_from_payload(payload)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][0], 1001.0)
        self.assertEqual(rows[-1][1][0], 60.0)

    def test_empty_payload(self):
        self.assertEqual(rows_from_payload({}), [])
        self.assertEqual(dimension_names({}), [])


if __name__ == "__main__":
    unittest.main()
