from __future__ import annotations

from bytia_kode.mcp.client import McpClient, McpToolError, McpToolTimeout
from bytia_kode.tools.registry import Tool, ToolResult


class McpTool(Tool):
    _PREFIX = "mcp"

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        client: McpClient,
        original_name: str,
        server_name: str,
    ) -> None:
        prefixed = f"{self._PREFIX}__{server_name}__{name}"
        self.name = prefixed
        self.description = description
        self.parameters = parameters
        self._client = client
        self._original_name = original_name
        self._server_name = server_name

    async def execute(self, **kwargs) -> ToolResult:
        # TODO(human): Implement the MCP tool execution bridge
        raise NotImplementedError
