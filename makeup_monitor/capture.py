from __future__ import annotations

import logging
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import imageio_ffmpeg
from PIL import Image, ImageFilter, ImageOps


LOGGER = logging.getLogger(__name__)
WECHAT_IMAGE_LIMIT_BYTES = 2 * 1024 * 1024


def safe_name(value: Any) -> str:
    text = {"新心": "xinxin", "中鼎": "zhongding"}.get(
        str(value).strip(),
        str(value).strip(),
    )
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", text)[:80] or "unknown"


def required_value(row: dict[str, Any], key: str) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        raise ValueError(f"直播数据缺少“{key}”，无法生成直播截图。")
    return value


def capture_stream_frame(
    row: dict[str, Any],
    frame_path: Path,
    capture_config: dict[str, Any],
) -> None:
    stream_url = required_value(row, "FLV拉流地址")
    timeout_seconds = int(capture_config.get("stream_timeout_seconds", 20))
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rw_timeout",
        str(timeout_seconds * 1_000_000),
        "-analyzeduration",
        "0",
        "-probesize",
        "32768",
        "-i",
        stream_url,
        "-frames:v",
        "1",
        "-q:v",
        "1",
        str(frame_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 5,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("直播画面接口取帧超时。") from exc
    if result.returncode != 0 or not frame_path.is_file():
        reason = (result.stderr or "").strip()[-500:]
        raise RuntimeError(f"直播画面接口取帧失败: {reason}")


def _enhance_for_delivery(
    source_path: Path,
    output_path: Path,
    capture_config: dict[str, Any],
) -> tuple[int, int]:
    min_width = max(1, int(capture_config.get("min_output_width", 720)))
    sharpen_percent = max(0, int(capture_config.get("sharpen_percent", 110)))
    preferred_quality = max(80, min(95, int(capture_config.get("jpeg_quality", 95))))

    with Image.open(source_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        if image.width < min_width:
            scale = min(2.0, min_width / image.width)
            size = (round(image.width * scale), round(image.height * scale))
            image = image.resize(size, Image.Resampling.LANCZOS)
        if sharpen_percent:
            image = image.filter(
                ImageFilter.UnsharpMask(
                    radius=1.1,
                    percent=sharpen_percent,
                    threshold=3,
                )
            )
        for quality in (preferred_quality, 90, 84, 78):
            image.save(
                output_path,
                format="JPEG",
                quality=quality,
                optimize=True,
                subsampling=0,
            )
            if output_path.stat().st_size <= WECHAT_IMAGE_LIMIT_BYTES:
                return image.size
    raise RuntimeError(f"截图超过企业微信 2MB 限制: {output_path}")


def capture_screenshot(
    row: dict[str, Any],
    output_dir: Path,
    capture_config: dict[str, Any],
) -> Path:
    backend = required_value(row, "后台")
    account = required_value(row, "抖音号/短ID")
    room_id = required_value(row, "直播间ID")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    screenshot = output_dir / (
        f"{safe_name(backend)}_{safe_name(account)}_{safe_name(room_id)}_{stamp}.jpg"
    )
    stream_frame = screenshot.with_name(f"{screenshot.stem}.stream.jpg")
    started = time.perf_counter()
    try:
        capture_stream_frame(row, stream_frame, capture_config)
        width, height = _enhance_for_delivery(
            stream_frame,
            screenshot,
            capture_config,
        )
    finally:
        stream_frame.unlink(missing_ok=True)

    LOGGER.info(
        "高清增强直播截图已保存（%dx%d，%.1f 秒，%.0f KB）: %s",
        width,
        height,
        time.perf_counter() - started,
        screenshot.stat().st_size / 1024,
        screenshot,
    )
    return screenshot
