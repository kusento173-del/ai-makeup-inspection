from __future__ import annotations

import unittest

from makeup_monitor.backend import overwrite_detail_metrics


class BackendTests(unittest.TestCase):
    def test_detail_metrics_overwrite_data_ext_values(self) -> None:
        rooms = [
            {
                "id_str": "room-1",
                "total_user_count": "863",
                "create_time": "100",
            }
        ]
        details = [
            {
                "base_data": {
                    "id_str": "room-1",
                    "total_user_count": "553",
                    "create_time": "100",
                }
            }
        ]

        overwrite_detail_metrics(rooms, details)

        self.assertEqual("553", rooms[0]["total_user_count"])
        self.assertEqual("100", rooms[0]["create_time"])


if __name__ == "__main__":
    unittest.main()
