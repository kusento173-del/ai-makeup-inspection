from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from .backend import fetch_live_rows, refresh_live_row
from .capture import capture_screenshot
from .config import PROJECT_ROOT, resolve_path
from .notifier import alert_text, resolve_webhook, send_alert, validate_team_webhooks
from .roster import RosterSnapshot, load_roster
from .rules import duration_to_seconds, find_candidates, number
from .state import load_state, mark_notified, save_state


LOGGER = logging.getLogger(__name__)


def write_roster_snapshot(snapshot: RosterSnapshot, data_root: Path) -> Path:
    path = data_root / date.today().strftime("%Y%m%d") / "roster_snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": date.today().isoformat(),
        "roster_file": str(snapshot.roster_file),
        "raw_file": str(snapshot.raw_file),
        "lookback_start": snapshot.lookback_start.isoformat(),
        "lookback_end": snapshot.lookback_end.isoformat(),
        "active_anchor_count": len(snapshot.entries),
        "douyin_account_count": len(snapshot.account_index),
        "entries": [
            {
                "主播编号": entry.anchor_code,
                "主播昵称": entry.streamer_name,
                "化妆师": entry.makeup_artist,
                "小队": entry.team,
                "手机号": entry.phone,
                "抖音号": list(entry.douyin_accounts),
            }
            for entry in snapshot.entries
        ],
    }
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return path


def run_once(
    config: dict[str, Any],
    *,
    dry_run: bool = False,
    roster_only: bool = False,
) -> None:
    data_root = resolve_path(config.get("data_root", "daily_data"), PROJECT_ROOT)
    snapshot = load_roster(config)
    snapshot_path = write_roster_snapshot(snapshot, data_root)
    LOGGER.info("名单快照已保存: %s", snapshot_path)
    if roster_only:
        return

    wechat = config["wechat"]
    if not dry_run:
        if not wechat.get("enabled", True):
            raise RuntimeError("wechat.enabled=false，正式发送已禁用。")
        validate_team_webhooks(wechat)

    state = load_state(data_root)
    notified_accounts = set(state["accounts"])
    rows = fetch_live_rows(config)
    rule = config["warning_rule"]
    candidates = find_candidates(
        rows,
        snapshot.account_index,
        notified_accounts,
        int(rule["min_live_seconds"]),
        float(rule["max_total_users"]),
    )
    LOGGER.info(
        "在线直播间 %d 个；固定名单命中且满足预警条件 %d 个；今日已通知账号 %d 个",
        len(rows),
        len(candidates),
        len(notified_accounts),
    )
    clips_dir = data_root / date.today().strftime("%Y%m%d") / "screenshots"
    if not candidates:
        return
    for index, candidate in enumerate(candidates, start=1):
        LOGGER.info(
            "[%d/%d] %s / %s / %s 刷新数据并生成截图",
            index,
            len(candidates),
            candidate.row.get("后台"),
            candidate.row.get("主播昵称"),
            candidate.account,
        )
        try:
            resolve_webhook(wechat, candidate.entry.team)
        except RuntimeError as exc:
            LOGGER.warning(
                "%s / %s 未发送：%s",
                candidate.account,
                candidate.entry.makeup_artist,
                exc,
            )
            continue
        try:
            backend = str(candidate.row.get("后台") or "").strip()
            browser_config = config["browsers"].get(backend)
            if not isinstance(browser_config, dict):
                raise RuntimeError(f"没有找到 {backend} 后台配置。")
            refreshed_row = refresh_live_row(
                config,
                candidate.row,
                browser_config,
            )
            refreshed_live_seconds = duration_to_seconds(
                refreshed_row.get("开播时长")
            )
            refreshed_total_users = number(refreshed_row.get("累计观众"))
            if refreshed_live_seconds is None or refreshed_total_users is None:
                raise RuntimeError("详情接口未返回有效的开播时长或累计观众。")
            candidate = replace(
                candidate,
                row=refreshed_row,
                live_seconds=refreshed_live_seconds,
                total_users=refreshed_total_users,
            )
            if (
                candidate.live_seconds < int(rule["min_live_seconds"])
                or candidate.total_users >= float(rule["max_total_users"])
            ):
                LOGGER.info(
                    "%s 刷新后不再满足条件：开播 %s 秒，累计观众 %g；本轮不发送",
                    candidate.account,
                    candidate.live_seconds,
                    candidate.total_users,
                )
                continue
            screenshot = capture_screenshot(
                candidate.row,
                clips_dir,
                config["capture"],
            )
            if dry_run:
                LOGGER.info("[预览模式，不发送、不去重]\n%s", alert_text(candidate))
                continue
            send_alert(candidate, screenshot, wechat)
            mark_notified(state, candidate, screenshot)
            save_state(data_root, state)
            if candidate.entry.phone:
                LOGGER.info(
                    "已发送到%s并尝试 @ %s：%s",
                    candidate.entry.team,
                    candidate.entry.makeup_artist,
                    candidate.entry.phone,
                )
            else:
                LOGGER.info(
                    "已发送到%s；%s 未填写手机号，本次未 @",
                    candidate.entry.team,
                    candidate.entry.makeup_artist,
                )
        except Exception:
            LOGGER.exception("主播 %s 处理失败，下轮继续重试。", candidate.account)
