"""
Orders MCP Server

Implements the MCP JSON-RPC protocol for order management tools.
AgentCore Gateway invokes this Lambda and wraps responses in MCP format.

Tools:
- list_orders: List all orders with optional filtering
- get_order_by_id: Get order details by ID
- create_order: Create a new order
"""

import json
from datetime import datetime

# Sample order data
SAMPLE_ORDERS = [
    {
        "id": "ORD-001",
        "customer_id": "CUST-001",
        "status": "shipped",
        "total": 159.97,
        "created": "2026-05-15T10:30:00Z",
        "items": [
            {"product_id": "PROD-001", "quantity": 2, "price": 29.99},
            {"product_id": "PROD-002", "quantity": 1, "price": 12.99},
            {"product_id": "PROD-004", "quantity": 1, "price": 89.99}
        ]
    },
    {
        "id": "ORD-002",
        "customer_id": "CUST-002",
        "status": "processing",
        "total": 124.99,
        "created": "2026-05-18T14:20:00Z",
        "items": [
            {"product_id": "PROD-003", "quantity": 1, "price": 45.00},
            {"product_id": "PROD-006", "quantity": 1, "price": 79.99}
        ]
    },
    {
        "id": "ORD-003",
        "customer_id": "CUST-004",
        "status": "delivered",
        "total": 44.49,
        "created": "2026-05-10T09:15:00Z",
        "items": [
            {"product_id": "PROD-005", "quantity": 1, "price": 24.50},
            {"product_id": "PROD-008", "quantity": 1, "price": 19.99}
        ]
    },
    {
        "id": "ORD-004",
        "customer_id": "CUST-003",
        "status": "pending",
        "total": 149.98,
        "created": "2026-05-20T16:45:00Z",
        "items": [
            {"product_id": "PROD-004", "quantity": 1, "price": 89.99},
            {"product_id": "PROD-007", "quantity": 1, "price": 59.99}
        ]
    }
]

# Tool definitions for MCP tools/list
TOOLS = [
    {
        "name": "demo-orders-mcp___list_orders",
        "description": "List all orders with optional filtering by status or customer",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by order status",
                    "enum": ["pending", "processing", "shipped", "delivered", "cancelled"]
                },
                "customer_id": {
                    "type": "string",
                    "description": "Filter by customer ID"
                }
            }
        }
    },
    {
        "name": "demo-orders-mcp___get_order_by_id",
        "description": "Get order details by order ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order ID (e.g., ORD-001)"
                }
            },
            "required": ["order_id"]
        }
    },
    {
        "name": "demo-orders-mcp___create_order",
        "description": "Create a new order",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID"
                },
                "items": {
                    "type": "array",
                    "description": "Order items",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "quantity": {"type": "number"}
                        }
                    }
                }
            },
            "required": ["customer_id", "items"]
        }
    }
]


def lambda_handler(event, context):
    """
    MCP JSON-RPC Lambda handler.

    Supports two invocation formats:
    1. Direct MCP JSON-RPC: {"method": "tools/list", ...}
    2. API Gateway wrapped: {"body": "{\"method\": \"tools/list\", ...}"}
    """
    if 'body' in event and isinstance(event.get('body'), str):
        try:
            request = json.loads(event['body'])
        except (json.JSONDecodeError, TypeError):
            return _api_response(400, _mcp_error(-32700, "Parse error"))
        result = _handle_mcp_request(request)
        return _api_response(200, result)

    return _handle_mcp_request(event)


def _handle_mcp_request(request):
    """Route MCP JSON-RPC request to appropriate handler."""
    method = request.get('method', '')
    params = request.get('params', {})
    request_id = request.get('id')

    if method == 'tools/list':
        return _mcp_result(request_id, {"tools": TOOLS})
    elif method == 'tools/call':
        return _handle_tool_call(request_id, params)
    else:
        return _mcp_error(-32601, f"Method not found: {method}", request_id)


def _handle_tool_call(request_id, params):
    """Execute a tool call."""
    tool_name = params.get('name', '')
    arguments = params.get('arguments', {})

    tool_base = tool_name.split('___')[-1] if '___' in tool_name else tool_name

    if tool_base == 'list_orders':
        return _list_orders(request_id, arguments)
    elif tool_base == 'get_order_by_id':
        return _get_order_by_id(request_id, arguments)
    elif tool_base == 'create_order':
        return _create_order(request_id, arguments)
    else:
        return _mcp_error(-32602, f"Unknown tool: {tool_name}", request_id)


def _list_orders(request_id, args):
    """List orders with optional filtering."""
    orders = SAMPLE_ORDERS

    if 'status' in args:
        orders = [o for o in orders if o['status'] == args['status']]
    if 'customer_id' in args:
        orders = [o for o in orders if o['customer_id'] == args['customer_id']]

    content = json.dumps({"orders": orders, "total": len(orders)})
    return _mcp_result(request_id, {
        "content": [{"type": "text", "text": content}]
    })


def _get_order_by_id(request_id, args):
    """Get order by ID."""
    order_id = args.get('order_id')
    if not order_id:
        return _mcp_error(-32602, "order_id is required", request_id)

    order = next((o for o in SAMPLE_ORDERS if o['id'] == order_id), None)
    if not order:
        return _mcp_error(-32602, f"Order not found: {order_id}", request_id)

    return _mcp_result(request_id, {
        "content": [{"type": "text", "text": json.dumps(order)}]
    })


def _create_order(request_id, args):
    """Create a new order (mock implementation)."""
    customer_id = args.get('customer_id')
    items = args.get('items', [])

    if not customer_id:
        return _mcp_error(-32602, "customer_id is required", request_id)
    if not items:
        return _mcp_error(-32602, "items is required and must not be empty", request_id)

    # Generate a new order (mock - in production this would write to a database)
    new_order = {
        "order": {
            "id": f"ORD-{len(SAMPLE_ORDERS) + 1:03d}",
            "customer_id": customer_id,
            "status": "pending",
            "items": items,
            "created": datetime.utcnow().isoformat() + "Z"
        },
        "message": "Order created successfully"
    }

    content = json.dumps(new_order)
    return _mcp_result(request_id, {
        "content": [{"type": "text", "text": content}]
    })


def _mcp_result(request_id, result):
    """Create MCP JSON-RPC success response."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _mcp_error(code, message, request_id=None):
    """Create MCP JSON-RPC error response."""
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _api_response(status_code, body):
    """Wrap response for API Gateway."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }
