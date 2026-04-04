"""Configuration management."""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load .env: CWD first, then global config
_global_env = Path.home() / ".bytia-kode" / ".env"
load_dotenv(override=False)  # from CWD
if _global_env.exists():
    load_dotenv(_global_env, override=True)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


@dataclass
class ProviderConfig:
    """OpenAI-compatible provider configuration."""
    base_url: str = field(default_factory=lambda: _env("PROVIDER_BASE_URL", "http://localhost:8080/v1"))
    api_key: str = field(default_factory=lambda: _env("PROVIDER_API_KEY"))
    model: str = field(default_factory=lambda: _env("PROVIDER_MODEL", "auto"))

    # Fallback
    fallback_url: str = field(default_factory=lambda: _env("FALLBACK_BASE_URL", "https://api.z.ai/api/coding/paas/v4"))
    fallback_key: str = field(default_factory=lambda: _env("FALLBACK_API_KEY"))
    fallback_model: str = field(default_factory=lambda: _env("FALLBACK_MODEL", "glm-5-turbo"))

    # Local
    local_url: str = field(default_factory=lambda: _env("LOCAL_BASE_URL", "http://localhost:11434/v1"))
    local_model: str = field(default_factory=lambda: _env("LOCAL_MODEL", "gemma4:26b"))


@dataclass
class TelegramConfig:
    bot_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN"))
    allowed_users: list[str] = field(default_factory=lambda: [
        u.strip() for u in _env("TELEGRAM_ALLOWED_USERS").split(",") if u.strip()
    ])


@dataclass
class AppConfig:
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", "~/.bytia-kode")).expanduser())

    skills_dir: Path = field(init=False)

    def __post_init__(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir = self.data_dir / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)


def load_config() -> AppConfig:
    return AppConfig()
