import unittest

from makeup_monitor.main import format_countdown


class CountdownTests(unittest.TestCase):
    def test_formats_minutes_and_seconds(self):
        self.assertEqual(format_countdown(482), "08:02")

    def test_does_not_show_negative_time(self):
        self.assertEqual(format_countdown(-1), "00:00")


if __name__ == "__main__":
    unittest.main()
