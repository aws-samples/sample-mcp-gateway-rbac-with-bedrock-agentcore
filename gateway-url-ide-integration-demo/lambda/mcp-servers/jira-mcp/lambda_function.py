"""
Jira MCP Server - Gateway Compatible Version

Simplified demo: Returns mock Jira data. Gateway handles MCP wrapping.
In production, this would call actual Jira API.
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


def lambda_handler(event, context):
    """
    Gateway-compatible Lambda handler
    Gateway sends arguments only

    For demo: just lists all tickets
    In production: would call Jira REST API
    """
    print(f"Received event: {json.dumps(event)}")

    # Demo: return all tickets
    # In production, you'd filter based on event parameters
    return {
        "tickets": SAMPLE_TICKETS,
        "total": len(SAMPLE_TICKETS)
    }
