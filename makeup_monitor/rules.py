from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .roster import RosterEntry, normalize_identifier


@dataclass(frozen=True)
class AlertCandidate:
    account: str
    entry: RosterEntry
    row: dict[str, Any]
    live_seconds: int
    total_users: float


def duration_to_seconds(value: Any) -> int | None:
    if value in ("", None):
        return None
    parts = str(value).strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(float(parts[2]))
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(float(parts[1]))
        return int(float(parts[0]))
    except (TypeError, ValueError):
        return None


def number(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def find_candidates(
    rows: list[dict[str, Any]],
    account_index: dict[str, RosterEntry],
    notified_accounts: set[str],
    min_live_seconds: int,
    max_total_users: float,
) -> list[AlertCandidate]:
    candidates: dict[str, AlertCandidate] = {}
    for row in rows:
        account = normalize_identifier(row.get("抖音号/短ID"))
        entry = account_index.get(account)
        if not entry or account in notified_accounts or account in candidates:
            continue
        live_seconds = duration_to_seconds(row.get("开播时长"))
        total_users = number(row.get("累计观众"))
        if live_seconds is None or total_users is None:
            continue
        if live_seconds < min_live_seconds or total_users >= max_total_users:
            continue
        candidates[account] = AlertCandidate(
            account=account,
            entry=entry,
            row=row,
            live_seconds=live_seconds,
            total_users=total_users,
        )
    return list(candidates.values())


def duration_text(seconds: int) -> str:
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"

