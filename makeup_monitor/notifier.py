from __future__ import annotations

import base64
import hashlib
import os
import time
from collections import deque
from pathlib import Path
from typing import Any

import requests

from .rules import AlertCandidate, duration_text


MAX_MESSAGES_PER_MINUTE = 20
WEBHOOK_PREFIX = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="
_post_times: deque[float] = deque()


def user_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value or os.name != "nt":
        return value
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            stored, _ = winreg.QueryValueEx(key, name)
            return str(stored or "").strip()
    except (FileNotFoundError, OSError):
        return ""


def validate_team_webhooks(config: dict[str, Any]) -> None:
    routes = config.get("team_webhook_envs")
    if not isinstance(routes, dict) or not routes:
        raise RuntimeError("企业微信未配置小队群路由。")
    missing = [
        team
        for team, env_name in routes.items()
        if not str(env_name or "").strip()
        or not user_environment(str(env_name).strip())
    ]
    if missing:
        raise RuntimeError(f"以下小队群 webhook 尚未配置：{'、'.join(missing)}")


def resolve_webhook(config: dict[str, Any], team: str) -> str:
    team = str(team or "").strip()
    if not team:
        raise RuntimeError("化妆师未分配小队，本次不发送，也不回退到总群。")
    routes = config.get("team_webhook_envs")
    if not isinstance(routes, dict):
        raise RuntimeError("企业微信未配置小队群路由。")
    env_name = str(routes.get(team) or "").strip()
    key = user_environment(env_name) if env_name else ""
    if not key:
        raise RuntimeError(f"{team}未配置群机器人，本次不发送，也不回退到总群。")
    return key if key.startswith("https://") else WEBHOOK_PREFIX + key


def post_message(
    url: str,
    payload: dict[str, Any],
    timeout: float,
    min_interval_seconds: float = 3.2,
) -> None:
    delays = (10, 30, 60)
    for attempt in range(len(delays) + 1):
        while True:
            now = time.monotonic()
            while _post_times and now - _post_times[0] >= 60:
                _post_times.popleft()
            interval_wait = (
                min_interval_seconds - (now - _post_times[-1])
                if _post_times
                else 0
            )
            rate_wait = (
                60 - (now - _post_times[0])
                if len(_post_times) >= MAX_MESSAGES_PER_MINUTE
                else 0
            )
            wait_seconds = max(0.0, interval_wait, rate_wait)
            if wait_seconds == 0:
                break
            time.sleep(wait_seconds)
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            result = response.json() if response.content else {}
            _post_times.append(time.monotonic())
            if response.ok and result.get("errcode", 0) == 0:
                return
            message = f"HTTP {response.status_code}: {result or response.text[:500]}"
            retryable = (
                response.status_code in {429, 500, 502, 503, 504}
                or result.get("errcode") == 45009
            )
        except requests.RequestException as exc:
            _post_times.append(time.monotonic())
            message = str(exc)
            retryable = True
        if attempt >= len(delays) or not retryable:
            raise RuntimeError(f"企业微信发送失败: {message}")
        time.sleep(delays[attempt])


def alert_text(candidate: AlertCandidate) -> str:
    row = candidate.row
    entry = candidate.entry
    nickname = str(row.get("主播昵称") or entry.streamer_name or "接口未返回").strip()
    return "\n".join(
        [
            "【妆造巡检提醒】",
            f"后台：{row.get('后台') or '接口未返回'}",
            f"主播：{nickname}",
            f"主播编号：{entry.anchor_code}",
            f"抖音号：{candidate.account}",
            f"开播时长：{duration_text(candidate.live_seconds)}",
            f"累计观众：{candidate.total_users:g}",
            f"对应化妆师：{entry.makeup_artist}",
            f"所属小队：{entry.team or '未分队'}",
            "请查看上一条直播间截图并及时跟进。",
        ]
    )


def send_alert(
    candidate: AlertCandidate,
    screenshot: Path,
    config: dict[str, Any],
) -> None:
    url = resolve_webhook(config, candidate.entry.team)
    timeout = float(config.get("timeout_seconds", 30))
    min_interval = max(0.0, float(config.get("min_message_interval_seconds", 3.2)))
    image_bytes = screenshot.read_bytes()
    image_payload = {
        "msgtype": "image",
        "image": {
            "base64": base64.b64encode(image_bytes).decode("ascii"),
            "md5": hashlib.md5(image_bytes).hexdigest(),
        },
    }
    text: dict[str, Any] = {"content": alert_text(candidate)}
    if candidate.entry.phone:
        text["mentioned_mobile_list"] = [candidate.entry.phone]
    text_payload = {"msgtype": "text", "text": text}
    # 图片先发，文字和 @ 后发。若文字失败，下轮只会重复图片，不会产生重复 @。
    post_message(url, image_payload, timeout, min_interval)
    post_message(url, text_payload, timeout, min_interval)
