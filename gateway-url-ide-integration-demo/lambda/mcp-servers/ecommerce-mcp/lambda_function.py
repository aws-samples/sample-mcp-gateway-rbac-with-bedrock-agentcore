"""
Ecommerce MCP Server (Customers)

Implements the MCP JSON-RPC protocol for customer management tools.
AgentCore Gateway invokes this Lambda and wraps responses in MCP format.

Tools:
- list_customers: List all customers with optional filtering
- get_customer_by_id: Get customer details by ID
"""

import json

# Sample customer data
SAMPLE_CUSTOMERS = [
    {"id": "CUST-001", "name": "Acme Corporation", "email": "contact@acme-corp.example.com", "type": "business", "status": "active", "created": "2025-01-15"},
    {"id": "CUST-002", "name": "Global Industries", "email": "info@global-industries.example.com", "type": "business", "status": "active", "created": "2025-02-20"},
    {"id": "CUST-003", "name": "Tech Innovations LLC", "email": "hello@tech-innovations.example.com", "type": "business", "status": "active", "created": "2025-03-10"},
    {"id": "CUST-004", "name": "John Smith", "email": "john.smith@example.com", "type": "individual", "status": "active", "created": "2025-04-05"},
    {"id": "CUST-005", "name": "Jane Doe", "email": "jane.doe@example.com", "type": "individual", "status": "inactive", "created": "2024-12-01"}
]

# Tool definitions for MCP tools/list
TOOLS = [
    {
        "name": "demo-ecommerce-mcp___list_customers",
        "description": "List all customers with optional filtering by status or type",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status (active/inactive)",
                    "enum": ["active", "inactive"]
                },
                "type": {
                    "type": "string",
                    "description": "Filter by customer type",
                    "enum": ["business", "individual"]
                }
            }
        }
    },
    {
        "name": "demo-ecommerce-mcp___get_customer_by_id",
        "description": "Get customer details by customer ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID (e.g., CUST-001)"
                }
            },
            "required": ["customer_id"]
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
    # Handle API Gateway wrapped format
    if 'body' in event and isinstance(event.get('body'), str):
        try:
            request = json.loads(event['body'])
        except (json.JSONDecodeError, TypeError):
            return _api_response(400, _mcp_error(-32700, "Parse error"))
        result = _handle_mcp_request(request)
        return _api_response(200, result)

    # Direct invocation (MCP JSON-RPC)
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

    # Strip prefix for routing
    tool_base = tool_name.split('___')[-1] if '___' in tool_name else tool_name

    if tool_base == 'list_customers':
        return _list_customers(request_id, arguments)
    elif tool_base == 'get_customer_by_id':
        return _get_customer_by_id(request_id, arguments)
    else:
        return _mcp_error(-32602, f"Unknown tool: {tool_name}", request_id)


def _list_customers(request_id, args):
    """List customers with optional filtering."""
    customers = SAMPLE_CUSTOMERS

    if 'status' in args:
        customers = [c for c in customers if c['status'] == args['status']]
    if 'type' in args:
        customers = [c for c in customers if c['type'] == args['type']]

    content = json.dumps({"customers": customers, "total": len(customers)})
    return _mcp_result(request_id, {
        "content": [{"type": "text", "text": content}]
    })


def _get_customer_by_id(request_id, args):
    """Get customer by ID."""
    customer_id = args.get('customer_id')
    if not customer_id:
        return _mcp_error(-32602, "customer_id is required", request_id)

    customer = next((c for c in SAMPLE_CUSTOMERS if c['id'] == customer_id), None)
    if not customer:
        return _mcp_error(-32602, f"Customer not found: {customer_id}", request_id)

    return _mcp_result(request_id, {
        "content": [{"type": "text", "text": json.dumps(customer)}]
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
