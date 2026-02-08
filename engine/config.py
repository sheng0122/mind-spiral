"""設定管理 — 讀取 config/default.yaml"""

from pathlib import Path
import yaml


_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "default.yaml"


def load_config(config_path: Path | None = None) -> dict:
    path = config_path or _DEFAULT_CONFIG_PATH
    with open(path) as f:
        return yaml.safe_load(f)


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
