#!/bin/bash
#
# Company MCP Gateway Setup Script
# Run: curl -fsSL https://your-company.example.com/setup-mcp.sh | bash
#

set -e

echo "🚀 Setting up Company MCP Gateway for GitHub Copilot..."

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    *)          MACHINE="UNKNOWN:${OS}"
esac

if [ "$MACHINE" = "UNKNOWN:${OS}" ]; then
    echo "❌ Unsupported OS: ${OS}"
    exit 1
fi

# Set paths based on OS
if [ "$MACHINE" = "Mac" ]; then
    MCP_DIR="$HOME/Library/Application Support/Code/User"
    MCP_JSON="$MCP_DIR/mcp.json"
    PROXY_DIR="$HOME/.mcp-proxies"
elif [ "$MACHINE" = "Linux" ]; then
    MCP_DIR="$HOME/.config/Code/User"
    MCP_JSON="$MCP_DIR/mcp.json"
    PROXY_DIR="$HOME/.mcp-proxies"
fi

# Create directories
mkdir -p "$PROXY_DIR"
mkdir -p "$MCP_DIR"

# Download proxy script
echo "📥 Downloading proxy script..."
cat > "$PROXY_DIR/customer-gateway-proxy.py" << 'PROXY_EOF'
#!/usr/bin/env python3
import sys
import json
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import urllib3
from urllib.parse import urlparse

GATEWAY_URL = "https://<GATEWAY_ID>.gateway.bedrock-agentcore.<REGION>.amazonaws.com/mcp"

def forward_request(url: str, payload: str):
    parsed = urlparse(url)
    hostname = parsed.netloc

    request_headers = {
        'Content-Type': 'application/json',
        'Host': hostname,
    }

    aws_request = AWSRequest(method='POST', url=url, data=payload, headers=request_headers)
    credentials = boto3.Session().get_credentials()
    SigV4Auth(credentials, 'bedrock-agentcore', 'us-east-1').add_auth(aws_request)

    http = urllib3.PoolManager()
    response = http.request('POST', url, body=payload, headers=dict(aws_request.headers), timeout=120.0)
    return response.data.decode('utf-8')

def main():
    for line in sys.stdin:
        try:
            message = line.strip()
            if not message:
                continue

            response = forward_request(GATEWAY_URL, message)
            sys.stdout.write(response + '\n')
            sys.stdout.flush()
        except Exception as e:
            error = json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32000, "message": str(e)}
            })
            sys.stdout.write(error + '\n')
            sys.stdout.flush()

if __name__ == "__main__":
    main()
PROXY_EOF

chmod +x "$PROXY_DIR/customer-gateway-proxy.py"

# Update or create mcp.json
echo "⚙️  Configuring VS Code..."

if [ -f "$MCP_JSON" ]; then
    # Backup existing config
    cp "$MCP_JSON" "$MCP_JSON.backup.$(date +%Y%m%d_%H%M%S)"
    echo "📋 Backed up existing configuration"
fi

# Create/update mcp.json
cat > "$MCP_JSON" << MCP_EOF
{
  "servers": {
    "customer-gateway": {
      "command": "python3",
      "args": ["$PROXY_DIR/customer-gateway-proxy.py"],
      "description": "Company MCP Gateway - Customers, Products, Orders, Jira"
    }
  }
}
MCP_EOF

echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Ensure AWS credentials are configured: aws configure"
echo "   2. Restart VS Code"
echo "   3. Ask GitHub Copilot: 'Show me all customers'"
echo ""
echo "📚 Available tools:"
echo "   - Customer management (list, get by ID)"
echo "   - Product catalog (list, search)"
echo "   - Order tracking (list, get by ID)"
echo "   - Jira integration (list tickets)"
echo ""
echo "❓ Questions? Contact your-team@example.com"
