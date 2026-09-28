"""Configuration management."""

from __future__ import annotations

import importlib.metadata
import logging
import os
import shutil
from pathlib import Path
from dataclasses import dataclass, field

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env: CWD first, then global config. Neither may override variables
# already present in the environment, and the project .env (loaded first)
# wins over the global one — the global file is writable by the agent itself
# (trusted path), so letting it override would let a compromised session
# redirect PROVIDER_* or widen EXTRA_BINARIES on the next start (AST-15 T4).
# The CWD path is explicit because bare load_dotenv() searches from the
# calling module's directory, not from the process CWD.
_global_env = Path.home() / ".bytia-kode" / ".env"
load_dotenv(Path.cwd() / ".env", override=False)  # project .env wins
if _global_env.exists():
    load_dotenv(_global_env, override=False)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _get_vendor_skills_path() -> Path | None:
    """Get the path to vendored skills in the package."""
    package_dir = Path(__file__).parent
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

    # DeepSeek
    deepseek_url: str = field(
        default_factory=lambda: _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    deepseek_key: str = field(default_factory=lambda: _env("DEEPSEEK_API_KEY"))
    deepseek_model: str = field(
        default_factory=lambda: _env("DEEPSEEK_MODEL", "deepseek-flash")
    )
    deepseek_max_context: int = field(
        default_factory=lambda: int(_env("DEEPSEEK_MAX_CONTEXT", "1000000"))
    )

    # Unsloth Studio (local AppImage, :8888)
    unsloth_url: str = field(
        default_factory=lambda: _env("UNSLOTH_BASE_URL", "http://localhost:8888/v1")
    )
    unsloth_key: str = field(default_factory=lambda: _env("UNSLOTH_API_KEY"))
    unsloth_model: str = field(default_factory=lambda: _env("UNSLOTH_MODEL", "auto"))


@dataclass
class TelegramConfig:
    bot_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN"))
    allowed_users: list[str] = field(
        default_factory=lambda: [
            u.strip() for u in _env("TELEGRAM_ALLOWED_USERS").split(",") if u.strip()
        ]
    )


def _load_yaml_config() -> dict:
    """Read ~/.bytia-kode/config.yaml if present (AST-26).

    Missing file → {}. Malformed YAML or a non-mapping document → {} with a
    warning: a broken config must not brick the agent, it falls back to
    defaults. (Fail-open on *availability*, never on policy — the registry
    still applies whatever mode ends up configured, and the file itself is
    agent-write-denied, see T4.)
    """
    path = Path.home() / ".bytia-kode" / "config.yaml"
    if not path.exists():
        return {}
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Failed to parse %s, using defaults: %s", path, exc)
        return {}


def _workspace_from_config(data: dict) -> WorkspaceConfig:
    """Build the WorkspaceConfig from the parsed config.yaml document."""
    ws = data.get("workspace") or {}
    if not isinstance(ws, dict):
        logger.warning("config.yaml: 'workspace' must be a mapping, ignoring it")
        ws = {}

    mode = ws.get("mode", "permissive")
    if not isinstance(mode, str):
        logger.warning(
            "config.yaml: 'workspace.mode' must be a string, got %r — "
            "falling back to 'permissive'", type(mode).__name__,
        )
        mode = "permissive"

    raw_trusted = ws.get("trusted_paths") or []
    if isinstance(raw_trusted, str):
        raw_trusted = [raw_trusted]
    trusted = [
        Path(str(item).strip()).expanduser()
        for item in raw_trusted
        if isinstance(item, str) and item.strip()
    ]
    return WorkspaceConfig(mode=mode.strip().lower() or "permissive", trusted_paths=trusted)


@dataclass
class WorkspaceConfig:
    """Workspace jail policy (AST-26).

    mode: 'confined' (file tools AND bash jailed), 'permissive' (file tools
    jailed, bash free — the historical default, now explicit) or 'open'
    (nothing jailed). trusted_paths is the operator's precision valve out of
    the jail. An unknown mode falls back to 'permissive' with a warning:
    fail-closed would lock the user out of their own agent over a typo, and
    'permissive' is the documented pre-AST-26 behaviour.
    """

    mode: str = "permissive"
    trusted_paths: list[Path] = field(default_factory=list)

    def __post_init__(self):
        from bytia_kode.tools.registry import WORKSPACE_MODES  # lazy: registry imports config at module load

        if self.mode not in WORKSPACE_MODES:
            logger.warning(
                "config.yaml: unknown workspace mode %r, falling back to 'permissive' "
                "(valid: %s)", self.mode, ", ".join(WORKSPACE_MODES),
            )
            self.mode = "permissive"


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
    # AST-26: workspace jail policy from ~/.bytia-kode/config.yaml
    # (missing/malformed file → defaults: permissive, no extra trusted paths)
    workspace: WorkspaceConfig = field(
        default_factory=lambda: _workspace_from_config(_load_yaml_config())
    )

    def __post_init__(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir = self.data_dir / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        self.bytia_dir = Path.home() / "bytia"

        self._ensure_vendor_skills()

    def _get_package_version(self) -> str:
        """Versión instalada del paquete — también en site-packages (AST-23).

        Antes sólo se leía ``pyproject.toml`` por ruta relativa: válido en un
        checkout, pero en una instalación de wheel (site-packages) no existe
        ese archivo y la función devolvía ``"unknown"`` — así que
        ``.vendor-version`` decía "unknown" en TODA instalación de PyPI y el
        auto-reseed por cambio de versión nunca disparaba. Orden ahora:
        dist-info vía ``importlib.metadata`` (la verdad de una instalación),
        fallback al pyproject del checkout (fuente sin instalar), "unknown"
        como último recurso.
        """
        try:
            return importlib.metadata.version("bytia-kode")
        except importlib.metadata.PackageNotFoundError:
            pass
        try:
            pyproject = Path(__file__).parent.parent.parent / "pyproject.toml"
            if pyproject.exists():
                content = pyproject.read_text()
                for line in content.split("\n"):
                    if line.strip().startswith("version"):
                        return line.split("=")[1].strip().strip('"').strip("'")
        except Exception:
            pass
        return "unknown"

    def _ensure_vendor_skills(self):
        """Ensure vendor skills are installed and up-to-date in the skills directory."""
        vendor_target = self.skills_dir / "vendor"
        vendor_source = _get_vendor_skills_path()

        if not vendor_source or not vendor_source.exists():
            self.vendor_skills_installed = False
            return

        version_file = vendor_target / ".vendor-version"
        current_version = self._get_package_version()

        if vendor_target.exists() and any(vendor_target.iterdir()):
            installed_version = ""
            if version_file.exists():
                installed_version = version_file.read_text().strip()

            if installed_version == current_version:
                self.vendor_skills_installed = True
                return

        if vendor_target.exists():
            for item in vendor_target.iterdir():
                if item.name == ".vendor-version":
                    continue
                if item.is_symlink() or item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

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

        version_file.write_text(current_version)
        self.vendor_skills_installed = True


def load_config() -> AppConfig:
    return AppConfig()
