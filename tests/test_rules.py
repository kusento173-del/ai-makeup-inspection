from __future__ import annotations

import unittest

from makeup_monitor.roster import RosterEntry
from makeup_monitor.rules import find_candidates


class RuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entry = RosterEntry("100", "主播", "化妆师", "13194431228", ("dy001",))
        self.index = {"dy001": self.entry}

    def test_two_hours_is_included(self) -> None:
        rows = [{"抖音号/短ID": "dy001", "开播时长": "02:00:00", "累计观众": "999"}]
        result = find_candidates(rows, self.index, set(), 7200, 1000)
        self.assertEqual(1, len(result))

    def test_one_thousand_viewers_is_excluded(self) -> None:
        rows = [{"抖音号/短ID": "dy001", "开播时长": "03:00:00", "累计观众": "1000"}]
        result = find_candidates(rows, self.index, set(), 7200, 1000)
        self.assertEqual([], result)

    def test_notified_account_is_excluded(self) -> None:
        rows = [{"抖音号/短ID": "dy001", "开播时长": "03:00:00", "累计观众": "100"}]
        result = find_candidates(rows, self.index, {"dy001"}, 7200, 1000)
        self.assertEqual([], result)

    def test_missing_metrics_do_not_trigger(self) -> None:
        rows = [{"抖音号/短ID": "dy001", "开播时长": "", "累计观众": ""}]
        result = find_candidates(rows, self.index, set(), 7200, 1000)
        self.assertEqual([], result)


if __name__ == "__main__":
    unittest.main()

