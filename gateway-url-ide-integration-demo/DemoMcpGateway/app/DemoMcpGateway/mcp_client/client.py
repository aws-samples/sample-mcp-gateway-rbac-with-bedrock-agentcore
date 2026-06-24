import os
import logging
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

# MCP endpoint URL - configure via environment variable
# The AgentCore Gateway URL is set during deployment
MCP_ENDPOINT = os.environ.get("MCP_ENDPOINT_URL", "")


def get_streamable_http_mcp_client() -> MCPClient:
    """Returns an MCP Client compatible with Strands.

    The MCP_ENDPOINT_URL environment variable should be set to your
    AgentCore Gateway URL during deployment. If not configured,
    returns None and the agent will operate without MCP tools.
    """
    if not MCP_ENDPOINT:
        logger.warning(
            "MCP_ENDPOINT_URL not configured. "
            "Set this environment variable to enable MCP tool access."
        )
        return None

    # To use bearer authentication, add:
    # headers={"Authorization": f"Bearer {access_token}"}
    return MCPClient(lambda: streamablehttp_client(MCP_ENDPOINT))
