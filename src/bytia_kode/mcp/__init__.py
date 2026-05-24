from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from mcp.client.stdio import stdio_client  # noqa: F401

    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False
    logger.debug("mcp SDK not installed — MCP tools unavailable")

if _MCP_AVAILABLE:
    from bytia_kode.mcp.manager import McpManager
else:

    class McpManager:  # type: ignore[no-redef]
        """Stub when mcp SDK is not installed."""

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
