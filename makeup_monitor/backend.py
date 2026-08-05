from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import Playwright, sync_playwright

from .config import PROJECT_ROOT, resolve_path


LOGGER = logging.getLogger(__name__)
DETAIL_METRICS = {
    "broker_name": "base_data.broker_name",
    "title": "base_data.title",
    "ticket_count": "base_data.ticket_count",
    "total_user_count": "base_data.total_user_count",
    "pay_user_count": "base_data.pay_user_count",
    "follow_count": "base_data.follow_count",
    "user_count": "base_data.user_count",
    "create_time": "base_data.create_time",
    "live_id": "base_data.live_id",
}


def _path_value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return ""
        current = current[part]
    return "" if current is None else current


def _first_value(data: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        value = _path_value(data, path)
        if value not in ("", None):
            return value
    return ""


def _room_id(data: dict[str, Any]) -> str:
    return str(
        _first_value(
            data,
            "id_str",
            "room_id",
            "base_data.id_str",
            "baseData.idStr",
        )
    )


def overwrite_detail_metrics(
    rooms: list[dict[str, Any]],
    room_data: list[dict[str, Any]],
) -> None:
    details = {_room_id(item): item for item in room_data if _room_id(item)}
    for room in rooms:
        detail = details.get(_room_id(room))
        if detail is None:
            continue
        for target, source in DETAIL_METRICS.items():
            value = _path_value(detail, source)
            if value not in ("", None):
                room[target] = value


def _load_shared_exporter(config: dict[str, Any]):
    project = resolve_path(config["shared_backend_project"], PROJECT_ROOT)
    if not (project / "ai_broker" / "exporter.py").exists():
        raise FileNotFoundError(f"找不到 AI经纪人后台读取模块: {project}")
    project_text = str(project)
    if project_text not in sys.path:
        sys.path.insert(0, project_text)
    from ai_broker import exporter

    return exporter


def _export_rooms_via_session(
    exporter: Any,
    backend: str,
    browser_config: dict[str, Any],
) -> list[dict[str, Any]]:
    cdp_url = str(browser_config.get("cdp_url") or "").strip()
    if not cdp_url:
        raise ValueError(f"{backend} 后台缺少 cdp_url。")

    def fetch_from_page(page: Any) -> list[dict[str, Any]]:
        rooms = exporter.fetch_rooms(page, exporter.DATA_EXT_API)
        exporter.merge_follow_rooms(
            rooms,
            exporter.fetch_rooms(page, exporter.FOLLOW_API),
        )
        room_data = exporter.fetch_room_data(page, rooms)
        exporter.merge_room_data(rooms, room_data)
        overwrite_detail_metrics(rooms, room_data)
        return rooms

    with sync_playwright() as playwright:
        session_browser = playwright.chromium.connect_over_cdp(cdp_url)
        try:
            if not session_browser.contexts:
                raise RuntimeError(f"{backend} Edge 没有可用的浏览器上下文。")
            session_context = session_browser.contexts[0]
            union_page = next(
                (
                    page
                    for page in session_context.pages
                    if "union.bytedance.com" in page.url
                ),
                None,
            )
            if union_page is None:
                raise RuntimeError(
                    f"{backend} 后台没有已登录页面；为避免占用网络，程序不会自动加载完整页面。"
                )
            return fetch_from_page(union_page)
        finally:
            session_browser.close()


def fetch_live_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    exporter = _load_shared_exporter(config)
    browsers = config.get("browsers")
    if not isinstance(browsers, dict) or not browsers:
        raise ValueError("config.json 未配置 browsers。")

    exporter_config = {
        "warning_rule": {
            "min_live_seconds": config["warning_rule"]["min_live_seconds"],
            "max_total_users": config["warning_rule"]["max_total_users"],
            "max_income": 10**18,
        }
    }
    rows: list[dict[str, Any]] = []
    for backend, browser in browsers.items():
        LOGGER.info("正在无界面读取 %s 后台...", backend)
        rooms = _export_rooms_via_session(exporter, backend, browser)
        start = len(rows) + 1
        rows.extend(
            exporter.room_to_row(room, start + index, backend, exporter_config)
            for index, room in enumerate(rooms)
        )
        LOGGER.info("%s 在线直播间: %d", backend, len(rooms))
    return rows


def refresh_live_row(
    config: dict[str, Any],
    row: dict[str, Any],
    browser_config: dict[str, Any],
    playwright: Playwright | None = None,
) -> dict[str, Any]:
    exporter = _load_shared_exporter(config)
    backend = str(row.get("后台") or "").strip()
    cdp_url = str(browser_config.get("cdp_url") or "").strip()
    room_id = str(row.get("直播间ID") or "").strip()
    if not cdp_url or not room_id:
        raise ValueError(f"{backend} 缺少刷新详情所需的 cdp_url 或直播间ID。")

    def fetch_room_data(active_playwright: Playwright) -> list[dict[str, Any]]:
        session_browser = active_playwright.chromium.connect_over_cdp(cdp_url)
        try:
            if not session_browser.contexts:
                raise RuntimeError(f"{backend} Edge 没有可用的浏览器上下文。")
            page = next(
                (
                    item
                    for item in session_browser.contexts[0].pages
                    if "union.bytedance.com" in item.url
                ),
                None,
            )
            if page is None:
                raise RuntimeError(f"{backend} 后台没有已登录页面。")
            return exporter.fetch_room_data(page, [{"id_str": room_id}])
        finally:
            session_browser.close()

    if playwright is None:
        with sync_playwright() as active_playwright:
            room_data = fetch_room_data(active_playwright)
    else:
        room_data = fetch_room_data(playwright)

    if not room_data:
        raise RuntimeError(f"{backend} 详情接口未返回直播间 {room_id}。")
    detail = room_data[0]
    base_data = _path_value(detail, "base_data")
    if not isinstance(base_data, dict):
        raise RuntimeError(f"{backend} 详情接口缺少 base_data：{room_id}。")

    refreshed = dict(row)
    field_map = {
        "当前人气": "user_count",
        "累计观众": "total_user_count",
        "送礼人数": "pay_user_count",
        "音浪/流水": "ticket_count",
        "增长粉丝": "follow_count",
    }
    for column, field in field_map.items():
        value = base_data.get(field)
        if value not in ("", None):
            refreshed[column] = value

    started = base_data.get("create_time")
    try:
        started_timestamp = int(float(started))
        if started_timestamp > 1_000_000_000_000:
            started_timestamp //= 1000
        live_seconds = max(
            0,
            int(datetime.now(tz=timezone.utc).timestamp()) - started_timestamp,
        )
        refreshed["开播时长"] = (
            f"{live_seconds // 3600:02d}:"
            f"{live_seconds % 3600 // 60:02d}:"
            f"{live_seconds % 60:02d}"
        )
    except (TypeError, ValueError):
        pass
    return refreshed
