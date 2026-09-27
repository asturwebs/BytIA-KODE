from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from mcp.client.stdio import stdio_client  # noqa: F401

    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False
    logger.debug("mcp SDK not installed — MCP tools unavailable")

_MANAGER_AVAILABLE = False
if _MCP_AVAILABLE:
    try:
        from bytia_kode.mcp.manager import McpManager

        _MANAGER_AVAILABLE = True
    except ModuleNotFoundError:
        # manager.py sigue en WIP: caemos al stub de abajo para que
        # `import bytia_kode.mcp` funcione también con el extra [mcp] instalado.
        logger.warning(
            "mcp SDK installed but bytia_kode.mcp.manager is not shipped yet "
            "(WIP) — using no-op McpManager stub"
        )

if not _MANAGER_AVAILABLE:

    class McpManager:  # type: ignore[no-redef]
        """Stub when mcp SDK is not installed or manager.py is still WIP."""

        def __init__(self, data_dir=None):
            pass

        def load_config(self):
            pass

        async def start_all(self, registry=None):
            pass

        async def stop_all(self):
            pass

        async def restart_server(self, name, registry=None):
            return False

        def get_status(self):
            return {}
