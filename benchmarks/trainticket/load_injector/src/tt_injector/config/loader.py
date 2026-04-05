from __future__ import annotations

from pathlib import Path

import yaml

from .models import MixConfig


def load_mix_config(path: str | Path) -> MixConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return MixConfig.model_validate(data)
