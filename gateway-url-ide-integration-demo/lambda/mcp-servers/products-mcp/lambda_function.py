"""
Products MCP Server

Tools:
- list_products: List all products with optional category/stock filtering
- search_products: Search products by keyword in name or description
- get_product_by_id: Get product details by ID
"""

from __future__ import annotations

import sys
import os
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_protocol import MCPServer, mcp_text_result, mcp_error, ErrorCode  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Sample Data
# ─────────────────────────────────────────────────────────────────────────────

PRODUCTS: list[dict[str, Any]] = [
    {"id": "PROD-001", "name": "Wireless Mouse", "category": "electronics", "price": 29.99, "stock": 150, "description": "Ergonomic wireless mouse with 2.4GHz connectivity"},
    {"id": "PROD-002", "name": "USB-C Cable", "category": "electronics", "price": 12.99, "stock": 0, "description": "Durable USB-C charging and data cable, 6ft braided nylon"},
    {"id": "PROD-003", "name": "Laptop Stand", "category": "accessories", "price": 45.00, "stock": 80, "description": "Adjustable aluminum laptop stand with quick height adjustment mechanism"},
    {"id": "PROD-004", "name": "Mechanical Keyboard", "category": "electronics", "price": 89.99, "stock": 45, "description": "RGB mechanical keyboard with blue switches"},
    {"id": "PROD-005", "name": "Desk Organizer", "category": "accessories", "price": 24.50, "stock": 120, "description": "Multi-compartment desk organizer with color-coded labels"},
    {"id": "PROD-006", "name": "Monitor Arm", "category": "accessories", "price": 79.99, "stock": 60, "description": "Adjustable single monitor arm mount with gas spring"},
    {"id": "PROD-007", "name": "Webcam HD", "category": "electronics", "price": 59.99, "stock": 95, "description": "1080p HD webcam with built-in microphone"},
    {"id": "PROD-008", "name": "Headphone Stand", "category": "accessories", "price": 19.99, "stock": 200, "description": "Sleek aluminum headphone stand with cable holder"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Tool Handlers
# ─────────────────────────────────────────────────────────────────────────────


def list_products(request_id: Optional[str], args: dict[str, Any]) -> dict[str, Any]:
    """List products with optional category and stock filters."""
    results = PRODUCTS

    if "category" in args:
        results = [p for p in results if p["category"] == args["category"]]
    if args.get("in_stock_only"):
        results = [p for p in results if p["stock"] > 0]

    return mcp_text_result(request_id, {"products": results, "total": len(results)})


def search_products(request_id: Optional[str], args: dict[str, Any]) -> dict[str, Any]:
    """Search products by keyword in name or description."""
    keyword = args.get("keyword", "").lower()
    if not keyword:
        return mcp_error(ErrorCode.INVALID_PARAMS, "keyword is required", request_id)

    results = [
        p for p in PRODUCTS
        if keyword in p["name"].lower() or keyword in p["description"].lower()
    ]

    return mcp_text_result(request_id, {"products": results, "total": len(results), "keyword": keyword})


def get_product_by_id(request_id: Optional[str], args: dict[str, Any]) -> dict[str, Any]:
    """Get a single product by ID."""
    product_id = args.get("product_id")
    if not product_id:
        return mcp_error(ErrorCode.INVALID_PARAMS, "product_id is required", request_id)

    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if not product:
        return mcp_error(ErrorCode.INVALID_PARAMS, f"Product not found: {product_id}", request_id)

    return mcp_text_result(request_id, product)


# ─────────────────────────────────────────────────────────────────────────────
# Server Registration
# ─────────────────────────────────────────────────────────────────────────────

server = MCPServer(prefix="demo-products-mcp")

server.register_tool(
    name="list_products",
    handler=list_products,
    description="List all products with optional filtering by category",
    input_schema={
        "type": "object",
        "properties": {
            "category": {"type": "string", "description": "Filter by product category", "enum": ["electronics", "accessories"]},
            "in_stock_only": {"type": "boolean", "description": "Only show products with stock > 0"},
        },
    },
)

server.register_tool(
    name="search_products",
    handler=search_products,
    description="Search products by keyword in name or description",
    input_schema={
        "type": "object",
        "properties": {"keyword": {"type": "string", "description": "Search keyword"}},
        "required": ["keyword"],
    },
)

server.register_tool(
    name="get_product_by_id",
    handler=get_product_by_id,
    description="Get product details by product ID",
    input_schema={
        "type": "object",
        "properties": {"product_id": {"type": "string", "description": "Product ID (e.g., PROD-001)"}},
        "required": ["product_id"],
    },
)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda handler — delegates to the MCP server."""
    return server.handle(event)
