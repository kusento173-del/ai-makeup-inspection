import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from makeup_monitor.capture import (
    capture_screenshot,
    required_value,
    safe_name,
)


class CaptureTests(unittest.TestCase):
    def test_backend_name_is_safe_for_filename(self):
        self.assertEqual(safe_name("新心"), "xinxin")
        self.assertEqual(safe_name("中鼎"), "zhongding")

    def test_required_value_rejects_missing_field(self):
        with self.assertRaisesRegex(ValueError, "主播ID"):
            required_value({}, "主播ID")

    def test_upscales_small_stream_without_overlay(self):
        row = {
            "后台": "新心",
            "抖音号/短ID": "demo",
            "直播间ID": "room-1",
            "FLV拉流地址": "https://example.invalid/live.flv",
            "开播时长": "02:09:58",
            "音浪/流水": 18000,
            "送礼人数": 94,
            "累计观众": 902,
            "当前人气": 378,
            "增长粉丝": 6,
        }

        def fake_frame(_row, path, _config):
            Image.new("RGB", (720, 1280), (87, 64, 52)).save(path)

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "makeup_monitor.capture.capture_stream_frame",
                side_effect=fake_frame,
            ):
                result = capture_screenshot(
                    row,
                    Path(temp_dir),
                    {
                        "min_output_width": 720,
                        "sharpen_percent": 110,
                        "jpeg_quality": 95,
                    },
                )
            with Image.open(result) as card:
                self.assertEqual(card.size, (720, 1280))
                pixel = card.getpixel((360, 1100))
                self.assertTrue(
                    all(
                        abs(actual - expected) <= 2
                        for actual, expected in zip(pixel, (87, 64, 52))
                    )
                )
            self.assertLess(result.stat().st_size, 2 * 1024 * 1024)

    def test_preserves_native_high_resolution(self):
        row = {
            "后台": "中鼎",
            "抖音号/短ID": "demo-hd",
            "直播间ID": "room-hd",
            "FLV拉流地址": "https://example.invalid/live.flv",
        }

        def fake_frame(_row, path, _config):
            Image.new("RGB", (1080, 1920), (70, 60, 50)).save(path)

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "makeup_monitor.capture.capture_stream_frame",
                side_effect=fake_frame,
            ):
                result = capture_screenshot(
                    row,
                    Path(temp_dir),
                    {"min_output_width": 720},
                )
            with Image.open(result) as image:
                self.assertEqual(image.size, (1080, 1920))


if __name__ == "__main__":
    unittest.main()
