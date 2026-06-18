"""
Jira MCP Server

Implements the MCP JSON-RPC protocol for Jira ticket management tools.
AgentCore Gateway invokes this Lambda and routes tool calls based on Cedar policies.

Tools:
- list_jira_tickets: List Jira tickets with optional filtering by status, project, or priority
"""

import json

# Sample Jira tickets (mock data for demo)
SAMPLE_TICKETS = [
    {
        "id": "DEMO-001",
        "project": "DEMO",
        "summary": "Checkout page not loading",
        "status": "Open",
        "priority": "High",
        "assignee": "john.doe@example.com",
        "created": "2026-05-20T10:00:00Z"
    },
    {
        "id": "DEMO-002",
        "project": "DEMO",
        "summary": "Add product filtering feature",
        "status": "In Progress",
        "priority": "Medium",
        "assignee": "jane.smith@example.com",
        "created": "2026-05-18T14:30:00Z"
    },
    {
        "id": "DEMO-003",
        "project": "DEMO",
        "summary": "Update customer profile UI",
        "status": "Done",
        "priority": "Low",
        "assignee": "bob.wilson@example.com",
        "created": "2026-05-15T09:15:00Z"
    }
]

# Tool definitions for MCP tools/list
TOOLS = [
    {
        "name": "demo-jira-mcp___list_jira_tickets",
        "description": "List Jira tickets with optional filtering by status, project, or priority",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Filter by project key (e.g., DEMO)"
                },
                "status": {
                    "type": "string",
                    "description": "Filter by ticket status",
                    "enum": ["Open", "In Progress", "Done", "Closed"]
                },
                "priority": {
                    "type": "string",
                    "description": "Filter by priority",
                    "enum": ["High", "Medium", "Low"]
                }
            }
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

    if tool_base == 'list_jira_tickets':
        return _list_jira_tickets(request_id, arguments)
    else:
        return _mcp_error(-32602, f"Unknown tool: {tool_name}", request_id)


def _list_jira_tickets(request_id, args):
    """List Jira tickets with optional filtering."""
    tickets = SAMPLE_TICKETS

    if 'project' in args:
        tickets = [t for t in tickets if t['project'] == args['project']]
    if 'status' in args:
        tickets = [t for t in tickets if t['status'] == args['status']]
    if 'priority' in args:
        tickets = [t for t in tickets if t['priority'] == args['priority']]

    content = json.dumps({"tickets": tickets, "total": len(tickets)})
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
