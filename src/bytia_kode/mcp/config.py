from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0


@dataclass
class McpServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    timeout: float = _DEFAULT_TIMEOUT
    disabled: bool = False


def load_mcp_config(data_dir: Path) -> dict[str, McpServerConfig]:
    config_path = data_dir / "mcp_servers.json"
    if not config_path.exists():
        return {}

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load %s: %s", config_path, exc)
        return {}

    servers_raw = raw.get("mcpServers", {})
    if not isinstance(servers_raw, dict):
        logger.warning("mcpServers key is not a dict in %s", config_path)
        return {}

    result: dict[str, McpServerConfig] = {}
    for name, cfg in servers_raw.items():
        if not isinstance(cfg, dict) or "command" not in cfg:
            logger.warning("Skipping invalid MCP server config: %s", name)
            continue
        result[name] = McpServerConfig(
            name=name,
            command=cfg["command"],
            args=cfg.get("args", []),
            env=cfg.get("env", {}),
            cwd=cfg.get("cwd"),
            timeout=cfg.get("timeout", _DEFAULT_TIMEOUT),
            disabled=cfg.get("disabled", False),
        )

    if result:
        logger.info("Loaded %d MCP server config(s) from %s", len(result), config_path)
    return result
