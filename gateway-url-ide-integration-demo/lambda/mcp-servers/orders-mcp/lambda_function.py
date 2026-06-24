"""
Orders MCP Server

Tools:
- list_orders: List all orders with optional filtering by status or customer
- get_order_by_id: Get order details by ID
- create_order: Create a new order
"""

from __future__ import annotations

import sys
import os
from datetime import datetime, timezone
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_protocol import MCPServer, mcp_text_result, mcp_error, ErrorCode  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Sample Data
# ─────────────────────────────────────────────────────────────────────────────

ORDERS: list[dict[str, Any]] = [
    {"id": "ORD-001", "customer_id": "CUST-001", "status": "shipped", "total": 159.97, "created": "2026-05-15T10:30:00Z", "items": [{"product_id": "PROD-001", "quantity": 2, "price": 29.99}, {"product_id": "PROD-002", "quantity": 1, "price": 12.99}, {"product_id": "PROD-004", "quantity": 1, "price": 89.99}]},
    {"id": "ORD-002", "customer_id": "CUST-002", "status": "processing", "total": 124.99, "created": "2026-05-18T14:20:00Z", "items": [{"product_id": "PROD-003", "quantity": 1, "price": 45.00}, {"product_id": "PROD-006", "quantity": 1, "price": 79.99}]},
    {"id": "ORD-003", "customer_id": "CUST-004", "status": "delivered", "total": 44.49, "created": "2026-05-10T09:15:00Z", "items": [{"product_id": "PROD-005", "quantity": 1, "price": 24.50}, {"product_id": "PROD-008", "quantity": 1, "price": 19.99}]},
    {"id": "ORD-004", "customer_id": "CUST-003", "status": "pending", "total": 149.98, "created": "2026-05-20T16:45:00Z", "items": [{"product_id": "PROD-004", "quantity": 1, "price": 89.99}, {"product_id": "PROD-007", "quantity": 1, "price": 59.99}]},
]


# ─────────────────────────────────────────────────────────────────────────────
# Tool Handlers
# ─────────────────────────────────────────────────────────────────────────────


def list_orders(request_id: Optional[str], args: dict[str, Any]) -> dict[str, Any]:
    """List orders with optional filtering by status or customer."""
    results = ORDERS

    if "status" in args:
        results = [o for o in results if o["status"] == args["status"]]
    if "customer_id" in args:
        results = [o for o in results if o["customer_id"] == args["customer_id"]]

    return mcp_text_result(request_id, {"orders": results, "total": len(results)})


def get_order_by_id(request_id: Optional[str], args: dict[str, Any]) -> dict[str, Any]:
    """Get a single order by ID."""
    order_id = args.get("order_id")
    if not order_id:
        return mcp_error(ErrorCode.INVALID_PARAMS, "order_id is required", request_id)

    order = next((o for o in ORDERS if o["id"] == order_id), None)
    if not order:
        return mcp_error(ErrorCode.INVALID_PARAMS, f"Order not found: {order_id}", request_id)

    return mcp_text_result(request_id, order)


def create_order(request_id: Optional[str], args: dict[str, Any]) -> dict[str, Any]:
    """Create a new order (mock — in production this would write to a database)."""
    customer_id = args.get("customer_id")
    items = args.get("items", [])

    if not customer_id:
        return mcp_error(ErrorCode.INVALID_PARAMS, "customer_id is required", request_id)
    if not items:
        return mcp_error(ErrorCode.INVALID_PARAMS, "items is required and must not be empty", request_id)

    new_order = {
        "order": {
            "id": f"ORD-{len(ORDERS) + 1:03d}",
            "customer_id": customer_id,
            "status": "pending",
            "items": items,
            "created": datetime.now(timezone.utc).isoformat(),
        },
        "message": "Order created successfully",
    }

    return mcp_text_result(request_id, new_order)


# ─────────────────────────────────────────────────────────────────────────────
# Server Registration
# ─────────────────────────────────────────────────────────────────────────────

server = MCPServer(prefix="demo-orders-mcp")

server.register_tool(
    name="list_orders",
    handler=list_orders,
    description="List all orders with optional filtering by status or customer",
    input_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "Filter by order status", "enum": ["pending", "processing", "shipped", "delivered", "cancelled"]},
            "customer_id": {"type": "string", "description": "Filter by customer ID"},
        },
    },
)

server.register_tool(
    name="get_order_by_id",
    handler=get_order_by_id,
    description="Get order details by order ID",
    input_schema={
        "type": "object",
        "properties": {"order_id": {"type": "string", "description": "Order ID (e.g., ORD-001)"}},
        "required": ["order_id"],
    },
)

server.register_tool(
    name="create_order",
    handler=create_order,
    description="Create a new order",
    input_schema={
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "Customer ID"},
            "items": {"type": "array", "description": "Order items", "items": {"type": "object", "properties": {"product_id": {"type": "string"}, "quantity": {"type": "number"}}}},
        },
        "required": ["customer_id", "items"],
    },
)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda handler — delegates to the MCP server."""
    return server.handle(event)
