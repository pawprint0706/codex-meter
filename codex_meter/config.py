"""Non-secret application settings."""

import json
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Config:
    refresh_interval: int = 10


def config_dir() -> str:
    path = os.path.expanduser("~/.codex-meter")
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


def load_config() -> Config:
    try:
        with open(config_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        interval = int(data.get("refresh_interval", 10))
        if interval not in (5, 10, 30, 60):
            interval = 10
        return Config(refresh_interval=interval)
    except FileNotFoundError:
        return Config()
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("Could not read config: %s", exc)
        return Config()


def save_config(cfg: Config) -> None:
    path = config_path()
    temp_path = path + ".tmp"
    descriptor = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"refresh_interval": cfg.refresh_interval}, handle, indent=2)
        os.replace(temp_path, path)
    except OSError:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
