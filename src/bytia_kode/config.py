"""Configuration management."""

from __future__ import annotations

import os
import shutil
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


def _get_vendor_skills_path() -> Path | None:
    """Get the path to vendored skills in the package."""
    package_dir = Path(__file__).parent.parent
    vendor_path = package_dir / "vendor" / "skills"
    if vendor_path.exists():
        return vendor_path
    return None


@dataclass
class ProviderConfig:
    """OpenAI-compatible provider configuration."""

    base_url: str = field(
        default_factory=lambda: _env("PROVIDER_BASE_URL", "http://localhost:8080/v1")
    )
    api_key: str = field(default_factory=lambda: _env("PROVIDER_API_KEY"))
    model: str = field(default_factory=lambda: _env("PROVIDER_MODEL", "auto"))

    # Fallback
    fallback_url: str = field(
        default_factory=lambda: _env(
            "FALLBACK_BASE_URL", "https://api.z.ai/api/coding/paas/v4"
        )
    )
    fallback_key: str = field(default_factory=lambda: _env("FALLBACK_API_KEY"))
    fallback_model: str = field(
        default_factory=lambda: _env("FALLBACK_MODEL", "glm-5-turbo")
    )

    # Local
    local_url: str = field(
        default_factory=lambda: _env("LOCAL_BASE_URL", "http://localhost:11434/v1")
    )
    local_model: str = field(default_factory=lambda: _env("LOCAL_MODEL", "gemma4:26b"))

    # MiniMax
    minimax_url: str = field(
        default_factory=lambda: _env("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
    )
    minimax_key: str = field(default_factory=lambda: _env("MINIMAX_API_KEY"))
    minimax_model: str = field(
        default_factory=lambda: _env("MINIMAX_MODEL", "MiniMax-M2.7")
    )

    # DeepSeek
    deepseek_url: str = field(
        default_factory=lambda: _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    deepseek_key: str = field(default_factory=lambda: _env("DEEPSEEK_API_KEY"))
    deepseek_model: str = field(
        default_factory=lambda: _env("DEEPSEEK_MODEL", "deepseek-v4-flash")
    )
    deepseek_max_context: int = field(
        default_factory=lambda: int(_env("DEEPSEEK_MAX_CONTEXT", "1000000"))
    )


@dataclass
class TelegramConfig:
    bot_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN"))
    allowed_users: list[str] = field(
        default_factory=lambda: [
            u.strip() for u in _env("TELEGRAM_ALLOWED_USERS").split(",") if u.strip()
        ]
    )


@dataclass
class AppConfig:
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
    log_file: str = field(default_factory=lambda: _env("LOG_FILE", ""))
    data_dir: Path = field(
        default_factory=lambda: Path(_env("DATA_DIR", "~/.bytia-kode")).expanduser()
    )
    extra_binaries: set[str] = field(
        default_factory=lambda: {
            b.strip() for b in _env("EXTRA_BINARIES").split(",") if b.strip()
        }
    )
    llm_temperature: float = field(
        default_factory=lambda: float(_env("LLM_TEMPERATURE", "0.3"))
    )
    llm_max_tokens: int = field(
        default_factory=lambda: int(_env("LLM_MAX_TOKENS", "8192"))
    )
    llm_timeout: float = field(
        default_factory=lambda: float(_env("LLM_TIMEOUT", "120"))
    )

    skills_dir: Path = field(init=False)
    bytia_dir: Path = field(init=False)
    vendor_skills_installed: bool = field(init=False, default=False)

    def __post_init__(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir = self.data_dir / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        self.bytia_dir = Path.home() / "bytia"

        self._ensure_vendor_skills()

    def _ensure_vendor_skills(self):
        """Ensure vendor skills are installed in the skills directory."""
        vendor_target = self.skills_dir / "vendor"

        if vendor_target.exists() and any(vendor_target.iterdir()):
            self.vendor_skills_installed = True
            return

        vendor_source = _get_vendor_skills_path()
        if not vendor_source or not vendor_source.exists():
            return

        vendor_target.mkdir(parents=True, exist_ok=True)

        for item in vendor_source.iterdir():
            if not item.is_dir():
                continue
            dest = vendor_target / item.name
            if dest.exists():
                if dest.is_symlink():
                    dest.unlink()
                else:
                    shutil.rmtree(dest)
            shutil.copytree(item, dest)

        self.vendor_skills_installed = True


def load_config() -> AppConfig:
    return AppConfig()
