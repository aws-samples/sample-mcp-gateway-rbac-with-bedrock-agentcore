"""
Ecommerce MCP Server (Customers)

Tools:
- list_customers: List all customers with optional filtering by status or type
- get_customer_by_id: Get customer details by ID
"""

from __future__ import annotations

import sys
import os
from typing import Any, Optional

# Allow importing shared module from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_protocol import MCPServer, mcp_text_result, mcp_error, ErrorCode  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Sample Data
# ─────────────────────────────────────────────────────────────────────────────

CUSTOMERS: list[dict[str, Any]] = [
    {"id": "CUST-001", "name": "Acme Corporation", "email": "contact@acme-corp.example.com", "type": "business", "status": "active", "created": "2025-01-15"},
    {"id": "CUST-002", "name": "Global Industries", "email": "info@global-industries.example.com", "type": "business", "status": "active", "created": "2025-02-20"},
    {"id": "CUST-003", "name": "Tech Innovations LLC", "email": "hello@tech-innovations.example.com", "type": "business", "status": "active", "created": "2025-03-10"},
    {"id": "CUST-004", "name": "John Smith", "email": "john.smith@example.com", "type": "individual", "status": "active", "created": "2025-04-05"},
    {"id": "CUST-005", "name": "Jane Doe", "email": "jane.doe@example.com", "type": "individual", "status": "inactive", "created": "2024-12-01"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Tool Handlers
# ─────────────────────────────────────────────────────────────────────────────


def list_customers(request_id: Optional[str], args: dict[str, Any]) -> dict[str, Any]:
    """List customers with optional filtering by status or type."""
    results = CUSTOMERS

    if "status" in args:
        results = [c for c in results if c["status"] == args["status"]]
    if "type" in args:
        results = [c for c in results if c["type"] == args["type"]]

    return mcp_text_result(request_id, {"customers": results, "total": len(results)})


def get_customer_by_id(request_id: Optional[str], args: dict[str, Any]) -> dict[str, Any]:
    """Get a single customer by ID."""
    customer_id = args.get("customer_id")
    if not customer_id:
        return mcp_error(ErrorCode.INVALID_PARAMS, "customer_id is required", request_id)

    customer = next((c for c in CUSTOMERS if c["id"] == customer_id), None)
    if not customer:
        return mcp_error(ErrorCode.INVALID_PARAMS, f"Customer not found: {customer_id}", request_id)

    return mcp_text_result(request_id, customer)


# ─────────────────────────────────────────────────────────────────────────────
# Server Registration
# ─────────────────────────────────────────────────────────────────────────────

server = MCPServer(prefix="demo-ecommerce-mcp")

server.register_tool(
    name="list_customers",
    handler=list_customers,
    description="List all customers with optional filtering by status or type",
    input_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "Filter by status", "enum": ["active", "inactive"]},
            "type": {"type": "string", "description": "Filter by customer type", "enum": ["business", "individual"]},
        },
    },
)

server.register_tool(
    name="get_customer_by_id",
    handler=get_customer_by_id,
    description="Get customer details by customer ID",
    input_schema={
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "Customer ID (e.g., CUST-001)"},
        },
        "required": ["customer_id"],
    },
)


# ─────────────────────────────────────────────────────────────────────────────
# Lambda Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda handler — delegates to the MCP server."""
    return server.handle(event)
