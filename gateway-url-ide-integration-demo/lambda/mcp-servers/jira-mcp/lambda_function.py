"""
Jira MCP Server

Tools:
- list_jira_tickets: List Jira tickets with optional filtering by status, project, or priority
"""

from __future__ import annotations

import sys
import os
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_protocol import MCPServer, mcp_text_result  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Sample Data
# ─────────────────────────────────────────────────────────────────────────────

TICKETS: list[dict[str, Any]] = [
    {"id": "DEMO-001", "project": "DEMO", "summary": "Checkout page not loading", "status": "Open", "priority": "High", "assignee": "john.doe@example.com", "created": "2026-05-20T10:00:00Z"},
    {"id": "DEMO-002", "project": "DEMO", "summary": "Add product filtering feature", "status": "In Progress", "priority": "Medium", "assignee": "jane.smith@example.com", "created": "2026-05-18T14:30:00Z"},
    {"id": "DEMO-003", "project": "DEMO", "summary": "Update customer profile UI", "status": "Done", "priority": "Low", "assignee": "bob.wilson@example.com", "created": "2026-05-15T09:15:00Z"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Tool Handlers
# ─────────────────────────────────────────────────────────────────────────────


def list_jira_tickets(request_id: str | None, args: dict[str, Any]) -> dict[str, Any]:
    """List Jira tickets with optional filtering."""
    results = TICKETS

    if "project" in args:
        results = [t for t in results if t["project"] == args["project"]]
    if "status" in args:
        results = [t for t in results if t["status"] == args["status"]]
    if "priority" in args:
        results = [t for t in results if t["priority"] == args["priority"]]

    return mcp_text_result(request_id, {"tickets": results, "total": len(results)})


# ─────────────────────────────────────────────────────────────────────────────
# Server Registration
# ─────────────────────────────────────────────────────────────────────────────

server = MCPServer(prefix="demo-jira-mcp")

server.register_tool(
    name="list_jira_tickets",
    handler=list_jira_tickets,
    description="List Jira tickets with optional filtering by status, project, or priority",
    input_schema={
        "type": "object",
        "properties": {
            "project": {"type": "string", "description": "Filter by project key (e.g., DEMO)"},
            "status": {"type": "string", "description": "Filter by ticket status", "enum": ["Open", "In Progress", "Done", "Closed"]},
            "priority": {"type": "string", "description": "Filter by priority", "enum": ["High", "Medium", "Low"]},
        },
    },
)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda handler — delegates to the MCP server."""
    return server.handle(event)
