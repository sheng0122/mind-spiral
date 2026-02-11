"""設定管理 — 讀取 config/default.yaml"""

import os
from pathlib import Path
import yaml


_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "default.yaml"


def load_config(config_path: Path | None = None) -> dict:
    path = config_path or _DEFAULT_CONFIG_PATH
    with open(path) as f:
        config = yaml.safe_load(f)

    # Environment overrides (for Docker and deployment env parity)
    backend = os.environ.get("LLM_BACKEND")
    if backend:
        config.setdefault("engine", {})["llm_backend"] = backend

    data_dir = os.environ.get("MIND_SPIRAL_DATA_DIR")
    if data_dir:
        config.setdefault("engine", {})["data_dir"] = data_dir

    return config


def get_data_dir(config: dict) -> Path:
    raw = config["engine"]["data_dir"]
    p = Path(raw)
    if not p.is_absolute():
        p = Path(__file__).parent.parent / p
    return p


def get_owner_dir(config: dict, owner_id: str) -> Path:
    d = get_data_dir(config) / owner_id
    d.mkdir(parents=True, exist_ok=True)
    return d
