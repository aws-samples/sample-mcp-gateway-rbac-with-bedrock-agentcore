"""
Products MCP Server

Implements the MCP JSON-RPC protocol for product catalog tools.
AgentCore Gateway invokes this Lambda and routes tool calls based on Cedar policies.

Tools:
- list_products: List all products with optional category filter
- search_products: Search products by keyword
- get_product_by_id: Get product details by ID
"""

import json

# Sample product data
SAMPLE_PRODUCTS = [
    {
        "id": "PROD-001",
        "name": "Wireless Mouse",
        "category": "electronics",
        "price": 29.99,
        "stock": 150,
        "description": "Ergonomic wireless mouse with 2.4GHz connectivity"
    },
    {
        "id": "PROD-002",
        "name": "USB-C Cable",
        "category": "electronics",
        "price": 12.99,
        "stock": 0,
        "description": "Durable USB-C charging and data cable, 6ft braided nylon"
    },
    {
        "id": "PROD-003",
        "name": "Laptop Stand",
        "category": "accessories",
        "price": 45.00,
        "stock": 80,
        "description": "Adjustable aluminum laptop stand with quick height adjustment mechanism"
    },
    {
        "id": "PROD-004",
        "name": "Mechanical Keyboard",
        "category": "electronics",
        "price": 89.99,
        "stock": 45,
        "description": "RGB mechanical keyboard with blue switches"
    },
    {
        "id": "PROD-005",
        "name": "Desk Organizer",
        "category": "accessories",
        "price": 24.50,
        "stock": 120,
        "description": "Multi-compartment desk organizer with color-coded labels"
    },
    {
        "id": "PROD-006",
        "name": "Monitor Arm",
        "category": "accessories",
        "price": 79.99,
        "stock": 60,
        "description": "Adjustable single monitor arm mount with gas spring"
    },
    {
        "id": "PROD-007",
        "name": "Webcam HD",
        "category": "electronics",
        "price": 59.99,
        "stock": 95,
        "description": "1080p HD webcam with built-in microphone"
    },
    {
        "id": "PROD-008",
        "name": "Headphone Stand",
        "category": "accessories",
        "price": 19.99,
        "stock": 200,
        "description": "Sleek aluminum headphone stand with cable holder"
    }
]

# Tool definitions for MCP tools/list
TOOLS = [
    {
        "name": "demo-products-mcp___list_products",
        "description": "List all products with optional filtering by category",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by product category",
                    "enum": ["electronics", "accessories"]
                },
                "in_stock_only": {
                    "type": "boolean",
                    "description": "Only show products with stock > 0"
                }
            }
        }
    },
    {
        "name": "demo-products-mcp___search_products",
        "description": "Search products by keyword in name or description",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Search keyword"
                }
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "demo-products-mcp___get_product_by_id",
        "description": "Get product details by product ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "Product ID (e.g., PROD-001)"
                }
            },
            "required": ["product_id"]
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

    if tool_base == 'list_products':
        return _list_products(request_id, arguments)
    elif tool_base == 'search_products':
        return _search_products(request_id, arguments)
    elif tool_base == 'get_product_by_id':
        return _get_product_by_id(request_id, arguments)
    else:
        return _mcp_error(-32602, f"Unknown tool: {tool_name}", request_id)


def _list_products(request_id, args):
    """List products with optional filtering."""
    products = SAMPLE_PRODUCTS

    if 'category' in args:
        products = [p for p in products if p['category'] == args['category']]
    if args.get('in_stock_only'):
        products = [p for p in products if p['stock'] > 0]

    content = json.dumps({"products": products, "total": len(products)})
    return _mcp_result(request_id, {
        "content": [{"type": "text", "text": content}]
    })


def _search_products(request_id, args):
    """Search products by keyword."""
    keyword = args.get('keyword', '').lower()
    if not keyword:
        return _mcp_error(-32602, "keyword is required", request_id)

    results = [
        p for p in SAMPLE_PRODUCTS
        if keyword in p['name'].lower() or keyword in p['description'].lower()
    ]

    content = json.dumps({"products": results, "total": len(results), "keyword": keyword})
    return _mcp_result(request_id, {
        "content": [{"type": "text", "text": content}]
    })


def _get_product_by_id(request_id, args):
    """Get product by ID."""
    product_id = args.get('product_id')
    if not product_id:
        return _mcp_error(-32602, "product_id is required", request_id)

    product = next((p for p in SAMPLE_PRODUCTS if p['id'] == product_id), None)
    if not product:
        return _mcp_error(-32602, f"Product not found: {product_id}", request_id)

    return _mcp_result(request_id, {
        "content": [{"type": "text", "text": json.dumps(product)}]
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
