from __future__ import annotations

import argparse
import logging
import math
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import DEFAULT_CONFIG, PROJECT_ROOT, load_config, resolve_path
from .pipeline import run_once


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="直播妆造自动巡检")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--monitor", action="store_true", help="按配置间隔持续运行")
    parser.add_argument("--dry-run", action="store_true", help="截图但不发送群消息，也不写去重状态")
    parser.add_argument("--roster-only", action="store_true", help="只刷新和校验 WPS 名单")
    return parser.parse_args()


def configure_logging(config: dict) -> None:
    data_root = resolve_path(config.get("data_root", "daily_data"), PROJECT_ROOT)
    log_dir = data_root / date.today().strftime("%Y%m%d") / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "makeup_monitor.log"
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(stream)
    root.addHandler(file_handler)


def format_countdown(seconds: int) -> str:
    seconds = max(0, seconds)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def wait_with_countdown(seconds: int) -> None:
    deadline = time.monotonic() + max(0, seconds)
    last_remaining: int | None = None
    while True:
        remaining = max(0, math.ceil(deadline - time.monotonic()))
        if remaining != last_remaining:
            print(f"\r距离下一轮还有 {format_countdown(remaining)}", end="", flush=True)
            last_remaining = remaining
        if remaining == 0:
            print()
            return
        time.sleep(min(1.0, max(0.05, deadline - time.monotonic())))


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    configure_logging(config)
    if not args.monitor:
        run_once(config, dry_run=args.dry_run, roster_only=args.roster_only)
        return 0

    interval = max(1, int(float(config["runtime"].get("monitor_interval_minutes", 10)) * 60))
    logging.info("妆造巡检已启动，每 %g 分钟运行一次。", interval / 60)
    while True:
        started = time.monotonic()
        try:
            run_once(config, dry_run=args.dry_run, roster_only=args.roster_only)
        except Exception:
            logging.exception("本轮巡检失败，下一轮自动重试。")
        remaining = max(1, interval - int(time.monotonic() - started))
        next_run = datetime.now() + timedelta(seconds=remaining)
        logging.info("下一轮预计在 %s 开始。", next_run.strftime("%H:%M:%S"))
        wait_with_countdown(remaining)


if __name__ == "__main__":
    raise SystemExit(main())
