from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"配置文件必须是 JSON 对象: {path}")
    data["_config_path"] = str(path.resolve())
    return data


def resolve_path(value: str | Path, root: Path = PROJECT_ROOT) -> Path:
    expanded = os.path.expandvars(str(value))
    path = Path(expanded).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def require_mapping(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"配置项 {key} 必须是对象。")
    return value

