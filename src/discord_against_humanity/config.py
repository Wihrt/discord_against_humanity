"""Runtime settings, read from environment variables."""

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    discord_token: str = ""
    valkey_host: str = "localhost"
    valkey_port: int = 6379
    valkey_db: int = 0
    valkey_password: str | None = None
    log_level: str = "INFO"
    cards_source: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Settings:
        return cls(
            discord_token=env.get("DISCORD_TOKEN", ""),
            valkey_host=env.get("VALKEY_HOST", cls.valkey_host),
            valkey_port=int(env.get("VALKEY_PORT", cls.valkey_port)),
            valkey_db=int(env.get("VALKEY_DB", cls.valkey_db)),
            valkey_password=env.get("VALKEY_PASSWORD") or None,
            log_level=env.get("LOG_LEVEL", cls.log_level).upper(),
            cards_source=env.get("CARDS_SOURCE") or None,
        )
