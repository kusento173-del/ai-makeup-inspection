from __future__ import annotations

import os
import unittest
from datetime import date, datetime, time
from pathlib import Path
from tempfile import TemporaryDirectory

from makeup_monitor.roster import (
    cached_backup,
    cell_date,
    makeup_staff_columns,
    select_active_assignments,
    select_makeup_artist_contacts,
)


class RosterTests(unittest.TestCase):
    def test_keeps_newer_cached_wps_backup(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "roster.xlsx.backup.et"
            cache = root / "cache" / "roster.xlsx"
            source.write_bytes(b"old")
            cache.parent.mkdir()
            cache.write_bytes(b"new")
            source.touch()
            cache.touch()
            cache_mtime = source.stat().st_mtime + 10
            os.utime(cache, (cache_mtime, cache_mtime))
            result = cached_backup(root, ("*.et",), "名单", cache)
            self.assertEqual(cache, result)
            self.assertEqual(b"new", result.read_bytes())

    def test_treats_wps_midnight_time_as_blank_date(self) -> None:
        self.assertIsNone(cell_date(time(0, 0), datetime(1899, 12, 30)))

    def test_uses_today_for_end_date(self) -> None:
        rows = [
            (1, "已结束", "陈玉", 46204, 46229, None, None, None, None, "线下"),
            (2, "当天有效", "陈玉", 46204, 46230, None, None, None, None, "线下"),
            (3, "长期有效", "陈玉", 46204, 0, None, None, None, None, "线下"),
        ]
        result = select_active_assignments(
            rows,
            datetime(1899, 12, 30),
            date(2026, 7, 27),
        )
        self.assertEqual({"2", "3"}, set(result))

    def test_filters_unassigned_and_non_offline(self) -> None:
        rows = [
            (1, "未分组", "未分组", 46204, 0, None, None, None, None, "线下"),
            (2, "非线下", "陈玉", 46204, 0, None, None, None, None, "线上"),
        ]
        result = select_active_assignments(
            rows,
            datetime(1899, 12, 30),
            date(2026, 7, 27),
        )
        self.assertEqual({}, result)

    def test_maps_makeup_artist_to_phone_from_staff_sheet(self) -> None:
        columns = makeup_staff_columns(("姓名", "化妆师", "小队", "手机号"))
        result = select_makeup_artist_contacts(
            [
                ("王莹莹", "桃子", "桃子队", 13194431228),
                ("刘菊", "橘子", "/", None),
            ],
            columns,
        )
        self.assertEqual("13194431228", result["桃子"].phone)
        self.assertEqual("桃子队", result["桃子"].team)
        self.assertEqual("", result["橘子"].phone)
        self.assertEqual("", result["橘子"].team)

    def test_rejects_conflicting_staff_phones(self) -> None:
        columns = makeup_staff_columns(("姓名", "化妆师", "小队", "手机号"))
        with self.assertRaisesRegex(ValueError, "多个不同手机号"):
            select_makeup_artist_contacts(
                [
                    ("甲", "桃子", "桃子队", 13194431228),
                    ("乙", "桃子", "桃子队", 13194431229),
                ],
                columns,
            )

    def test_rejects_conflicting_staff_teams(self) -> None:
        columns = makeup_staff_columns(("姓名", "化妆师", "小队", "手机号"))
        with self.assertRaisesRegex(ValueError, "多个不同小队"):
            select_makeup_artist_contacts(
                [
                    ("甲", "桃子", "桃子队", 13194431228),
                    ("乙", "桃子", "陈玉队", 13194431228),
                ],
                columns,
            )


if __name__ == "__main__":
    unittest.main()
