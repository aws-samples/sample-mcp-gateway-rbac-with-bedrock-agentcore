# Customer Gateway MCP Proxy

MCP proxy for accessing company's customer gateway through GitHub Copilot.

## Features

- Customer management
- Product catalog
- Order tracking
- Jira integration

## Installation

### For Developers

```bash
npm install -g @your-company/customer-gateway-mcp
```

### For VS Code MCP Configuration

Add to your `~/.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "customer-gateway": {
      "command": "npx",
      "args": ["-y", "@your-company/customer-gateway-mcp"],
      "description": "Company MCP Gateway"
    }
  }
}
```

Or use GitHub Copilot settings in VS Code:

1. Open Settings (Cmd/Ctrl + ,)
2. Search for "GitHub Copilot: MCP Servers"
3. Add:
```json
{
  "customer-gateway": {
    "command": "npx",
    "args": ["-y", "@your-company/customer-gateway-mcp"],
    "description": "Company MCP Gateway"
  }
}
```

## AWS Credentials

Ensure you have AWS credentials configured:

```bash
aws configure
# or
export AWS_PROFILE=your-profile
```

The proxy uses your AWS credentials to authenticate with the AgentCore Gateway.

## Usage

Once configured, you can ask GitHub Copilot:

- "Show me customer CUST-001"
- "List all products in electronics category"
- "Show me pending orders"
- "List high priority Jira tickets"

## Architecture

```
GitHub Copilot
    ↓
customer-gateway-mcp (this proxy)
    ↓ (HTTPS + AWS SigV4)
AWS AgentCore Gateway
    ├── Customers (Lambda)
    ├── Products (Lambda)
    ├── Orders (Lambda)
    └── Jira (Lambda)
```

## Support

Open an issue in this repository.
