from __future__ import annotations

import os
import random
from dataclasses import dataclass, field


def get_env(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def get_env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def get_env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(slots=True)
class RuntimeContext:
    base_url: str = field(default_factory=lambda: get_env("TT_BASE_URL", "http://127.0.0.1:8080").rstrip("/"))
    timeout: float = field(default_factory=lambda: get_env_float("TT_TIMEOUT", 20.0))
    request_retries: int = field(default_factory=lambda: max(1, get_env_int("TT_REQUEST_RETRIES", 3)))
    retry_sleep: float = field(default_factory=lambda: get_env_float("TT_REQUEST_RETRY_SLEEP", 1.0))
    username: str = field(default_factory=lambda: get_env("TT_USERNAME", "fdse_microservice"))
    password: str = field(default_factory=lambda: get_env("TT_PASSWORD", "111111"))
    admin_username: str = field(default_factory=lambda: get_env("TT_ADMIN_USERNAME", "admin"))
    admin_password: str = field(default_factory=lambda: get_env("TT_ADMIN_PASSWORD", "222222"))
    seed: int = field(default_factory=lambda: get_env_int("TT_RANDOM_SEED", 20260405))

    def new_rng(self) -> random.Random:
        return random.Random(self.seed)
