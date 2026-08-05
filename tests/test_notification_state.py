from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from makeup_monitor.notifier import resolve_webhook, send_alert
from makeup_monitor.roster import RosterEntry
from makeup_monitor.rules import AlertCandidate
from makeup_monitor.state import load_state, mark_notified, save_state


class NotificationStateTests(unittest.TestCase):
    def setUp(self) -> None:
        entry = RosterEntry(
            "100",
            "主播",
            "陈玉",
            "13194431228",
            ("dy001",),
            "陈玉队",
        )
        self.candidate = AlertCandidate(
            account="dy001",
            entry=entry,
            row={
                "后台": "新心",
                "主播昵称": "主播",
                "直播间ID": "room1",
            },
            live_seconds=7200,
            total_users=999,
        )

    def test_sends_image_before_text_and_mentions_phone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            screenshot = Path(directory) / "shot.jpg"
            screenshot.write_bytes(b"jpeg")
            payloads = []
            with patch("makeup_monitor.notifier.resolve_webhook", return_value="https://example.invalid"), patch(
                "makeup_monitor.notifier.post_message",
                side_effect=lambda _url, payload, _timeout, _interval: payloads.append(payload),
            ):
                send_alert(
                    self.candidate,
                    screenshot,
                    {"timeout_seconds": 1, "min_message_interval_seconds": 3.2},
                )
        self.assertEqual(["image", "text"], [payload["msgtype"] for payload in payloads])
        self.assertEqual(
            ["13194431228"],
            payloads[1]["text"]["mentioned_mobile_list"],
        )

    def test_empty_phone_sends_text_without_mention(self) -> None:
        entry = RosterEntry("100", "主播", "陈玉", "", ("dy001",), "陈玉队")
        candidate = AlertCandidate(
            account="dy001",
            entry=entry,
            row=self.candidate.row,
            live_seconds=7200,
            total_users=999,
        )
        with tempfile.TemporaryDirectory() as directory:
            screenshot = Path(directory) / "shot.jpg"
            screenshot.write_bytes(b"jpeg")
            payloads = []
            with patch(
                "makeup_monitor.notifier.resolve_webhook",
                return_value="https://example.invalid",
            ), patch(
                "makeup_monitor.notifier.post_message",
                side_effect=lambda _url, payload, _timeout, _interval: payloads.append(payload),
            ):
                send_alert(
                    candidate,
                    screenshot,
                    {"timeout_seconds": 1, "min_message_interval_seconds": 3.2},
                )
        self.assertNotIn("mentioned_mobile_list", payloads[1]["text"])

    def test_routes_to_team_group_and_never_falls_back(self) -> None:
        config = {"team_webhook_envs": {"陈玉队": "TEST_TEAM_WEBHOOK"}}
        with patch.dict(
            "os.environ",
            {"TEST_TEAM_WEBHOOK": "team-key"},
            clear=False,
        ):
            self.assertEqual(
                "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=team-key",
                resolve_webhook(config, "陈玉队"),
            )
        with self.assertRaisesRegex(RuntimeError, "不回退到总群"):
            resolve_webhook(config, "")

    def test_state_is_keyed_by_douyin_account(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            screenshot = root / "shot.jpg"
            screenshot.write_bytes(b"jpeg")
            state = load_state(root)
            mark_notified(state, self.candidate, screenshot)
            save_state(root, state)
            reloaded = load_state(root)
        self.assertIn("dy001", reloaded["accounts"])


if __name__ == "__main__":
    unittest.main()
