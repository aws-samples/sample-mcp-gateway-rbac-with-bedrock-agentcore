"""
Shared MCP JSON-RPC Protocol Helpers

Provides the base handler, response formatting, and API Gateway integration
used by all MCP Lambda servers. Individual servers only need to define their
tools and implement tool handlers.

Usage:
    from mcp_protocol import MCPServer, ToolDefinition

    server = MCPServer(prefix="demo-orders-mcp")
    server.register_tool("list_orders", list_orders_handler, schema={...})

    def lambda_handler(event, context):
        return server.handle(event)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# MCP JSON-RPC Standard Error Codes
class ErrorCode:
    PARSE_ERROR = -32700
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


@dataclass
class ToolDefinition:
    """Schema for an MCP tool exposed via tools/list."""

    name: str
    description: str
    input_schema: dict[str, Any]


# Type alias for tool handler functions
ToolHandler = Callable[[Optional[str], dict[str, Any]], dict[str, Any]]


@dataclass
class MCPServer:
    """
    Base MCP JSON-RPC server for AWS Lambda.

    Handles protocol routing, request parsing, and response formatting.
    Supports both direct Lambda invocation and API Gateway proxy formats.

    Args:
        prefix: Tool name prefix (e.g., "demo-orders-mcp"). Tools are registered
                as "{prefix}___{tool_name}" for MCP protocol compliance.
    """

    prefix: str
    _tools: dict[str, ToolHandler] = field(default_factory=dict, init=False)
    _tool_definitions: list[dict[str, Any]] = field(default_factory=list, init=False)

    def register_tool(
        self,
        name: str,
        handler: ToolHandler,
        description: str,
        input_schema: dict[str, Any],
    ) -> None:
        """
        Register a tool with the server.

        Args:
            name: Short tool name (e.g., "list_orders")
            handler: Function that accepts (request_id, arguments) and returns an MCP result
            description: Human-readable description for tools/list
            input_schema: JSON Schema for the tool's input parameters
        """
        self._tools[name] = handler
        self._tool_definitions.append({
            "name": f"{self.prefix}___{name}",
            "description": description,
            "inputSchema": input_schema,
        })

    def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        """
        Lambda entry point. Routes API Gateway or direct invocations to MCP handlers.

        Args:
            event: Lambda event (API Gateway proxy format or direct JSON-RPC)

        Returns:
            MCP JSON-RPC response (or API Gateway response wrapper)
        """
        if "body" in event and isinstance(event.get("body"), str):
            try:
                request = json.loads(event["body"])
            except (json.JSONDecodeError, TypeError):
                return _api_gateway_response(
                    400, mcp_error(ErrorCode.PARSE_ERROR, "Parse error")
                )
            result = self._route(request)
            return _api_gateway_response(200, result)

        return self._route(event)

    def _route(self, request: dict[str, Any]) -> dict[str, Any]:
        """Route an MCP JSON-RPC request to the appropriate handler."""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "tools/list":
            return mcp_result(request_id, {"tools": self._tool_definitions})
        elif method == "tools/call":
            return self._dispatch_tool(request_id, params)
        else:
            return mcp_error(
                ErrorCode.METHOD_NOT_FOUND,
                f"Method not found: {method}",
                request_id,
            )

    def _dispatch_tool(
        self, request_id: Optional[str], params: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch a tools/call request to the registered handler."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Strip prefix for routing: "demo-orders-mcp___list_orders" → "list_orders"
        base_name = tool_name.split("___")[-1] if "___" in tool_name else tool_name

        handler = self._tools.get(base_name)
        if not handler:
            return mcp_error(
                ErrorCode.INVALID_PARAMS,
                f"Unknown tool: {tool_name}",
                request_id,
            )

        return handler(request_id, arguments)


# ─────────────────────────────────────────────────────────────────────────────
# Response Helpers (usable by individual tool handlers)
# ─────────────────────────────────────────────────────────────────────────────


def mcp_result(request_id: Optional[str], result: dict[str, Any]) -> dict[str, Any]:
    """Create a successful MCP JSON-RPC response."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def mcp_text_result(request_id: Optional[str], data: Any) -> dict[str, Any]:
    """Create an MCP result with JSON-serialized text content (most common pattern)."""
    content = json.dumps(data) if not isinstance(data, str) else data
    return mcp_result(request_id, {"content": [{"type": "text", "text": content}]})


def mcp_error(
    code: int, message: str, request_id: Optional[str] = None
) -> dict[str, Any]:
    """Create an MCP JSON-RPC error response."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _api_gateway_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    """Wrap an MCP response for API Gateway proxy integration."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
