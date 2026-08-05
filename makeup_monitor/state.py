from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .rules import AlertCandidate


def state_path(data_root: Path, day: date | None = None) -> Path:
    current = day or date.today()
    return data_root / current.strftime("%Y%m%d") / "state" / "notified.json"


def load_state(data_root: Path, day: date | None = None) -> dict[str, Any]:
    path = state_path(data_root, day)
    if not path.exists():
        return {"date": (day or date.today()).isoformat(), "accounts": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"date": (day or date.today()).isoformat(), "accounts": {}}
    if not isinstance(data.get("accounts"), dict):
        data["accounts"] = {}
    return data


def save_state(data_root: Path, state: dict[str, Any], day: date | None = None) -> Path:
    path = state_path(data_root, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return path


def mark_notified(
    state: dict[str, Any],
    candidate: AlertCandidate,
    screenshot: Path,
) -> None:
    row = candidate.row
    state.setdefault("accounts", {})[candidate.account] = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "后台": row.get("后台"),
        "主播昵称": row.get("主播昵称") or candidate.entry.streamer_name,
        "主播编号": candidate.entry.anchor_code,
        "抖音号": candidate.account,
        "化妆师": candidate.entry.makeup_artist,
        "小队": candidate.entry.team,
        "手机号": candidate.entry.phone,
        "直播间ID": row.get("直播间ID"),
        "开播时长秒": candidate.live_seconds,
        "累计观众": candidate.total_users,
        "截图": str(screenshot),
    }
