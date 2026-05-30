# VS Code + GitHub Copilot Setup for RBAC Demo

This guide shows how to configure VS Code to use the AgentCore Gateway with GitHub Copilot, demonstrating RBAC with two different IAM users.

## Why a local proxy?

GitHub Copilot connects to MCP servers over **stdio** (a local process), not directly over HTTP. AWS AgentCore Gateway requires **SigV4 request signing** — every HTTP request must be signed with your AWS credentials.

The proxy script (`proxy.py`) sits between them:

```
GitHub Copilot  →  proxy.py (local)  →  AgentCore Gateway (AWS)
   (stdio)          signs with your        enforces Cedar RBAC
                    IAM credentials
```

This is what makes the RBAC work per-developer: each developer runs the proxy with *their own* AWS credentials, so the gateway knows who is making each tool call and applies the right Cedar policy.

## Prerequisites

1. VS Code with GitHub Copilot extension installed
2. Two AWS IAM users created with different access levels:
   - `test-developer-readonly` (tag: `group=ReadOnly`)
   - `test-developer-fullaccess` (tag: `group=FullAccess`)
3. AWS credentials configured in `~/.aws/credentials`

## Step 1: Install MCP Proxy Script

The proxy script bridges VS Code (stdio) to AWS Gateway (HTTP + SigV4 auth).

```bash
# Make proxy scripts executable
chmod +x npm-package/customer-gateway-proxy/bin/proxy.py
chmod +x npm-package/customer-gateway-proxy/bin/proxy.sh

# Test the proxy works
python3 npm-package/customer-gateway-proxy/bin/proxy.py
# Should wait for input (Ctrl+C to exit)
```

## Step 2: Configure VS Code MCP Server

Copy the MCP configuration to VS Code's settings directory:

**For macOS:**
```bash
cp vscode-config/mcp.json ~/Library/Application\ Support/Code/User/mcp.json
```

**For Linux:**
```bash
cp vscode-config/mcp.json ~/.config/Code/User/mcp.json
```

**For Windows:**
```powershell
copy vscode-config\mcp.json %APPDATA%\Code\User\mcp.json
```

### Manual Configuration

If you prefer to configure manually, add this to your VS Code MCP settings:

Location: 
- macOS: `~/Library/Application Support/Code/User/mcp.json`
- Linux: `~/.config/Code/User/mcp.json`
- Windows: `%APPDATA%\Code\User\mcp.json`

```json
{
  "servers": {
    "customer-agnostic-gateway": {
      "command": "python3",
      "args": ["${workspaceFolder}/npm-package/customer-gateway-proxy/bin/proxy.py"],
      "description": "Customer-agnostic MCP gateway with RBAC",
      "env": {
        "GATEWAY_URL": "<YOUR_GATEWAY_URL>"
      }
    }
  }
}
```

**Note:** `${workspaceFolder}` is automatically resolved by VS Code to the root of your open workspace — no manual path editing needed. Replace `<YOUR_GATEWAY_URL>` with the URL output by `agentcore deploy` — it looks like `https://<id>.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp`.

## Step 3: Set Up AWS Profiles

Add two profiles to `~/.aws/credentials`:

```ini
[test-readonly]
aws_access_key_id = YOUR_READONLY_ACCESS_KEY
aws_secret_access_key = YOUR_READONLY_SECRET_KEY
region = us-east-1

[test-fullaccess]
aws_access_key_id = YOUR_FULLACCESS_ACCESS_KEY
aws_secret_access_key = YOUR_FULLACCESS_SECRET_KEY
region = us-east-1
```

## Step 4: Test RBAC Demo

### Test 1: ReadOnly User (List Operations Only)

```bash
# Set AWS profile
export AWS_PROFILE=test-readonly

# Verify identity
aws sts get-caller-identity
# Should show: "Arn": "arn:aws:iam::ACCOUNT:user/test-developer-readonly"

# Start VS Code
code .
```

In GitHub Copilot Chat, try:

**Should Work ✅:**
```
Show me all orders
```

**Should Be Denied ❌:**
```
Create a new order for customer CUST-001 with 1 unit of product PROD-001
```

Expected error: `Tool Execution Denied: Tool call not allowed due to policy enforcement`

### Test 2: FullAccess User (All Operations)

```bash
# CLOSE VS Code completely (Cmd+Q or Ctrl+Q)

# Set AWS profile
export AWS_PROFILE=test-fullaccess

# Verify identity
aws sts get-caller-identity
# Should show: "Arn": "arn:aws:iam::ACCOUNT:user/test-developer-fullaccess"

# Start VS Code
code .
```

In GitHub Copilot Chat, try:

**Both Should Work ✅:**
```
Show me all orders
Create a new order for customer CUST-001 with 1 unit of product PROD-001
```

## Available Tools

Once configured, these tools are available in GitHub Copilot:

### Customers
- `customers-mcp___list_customers` - List all customers
- `customers-mcp___get_customer_by_id` - Get customer by ID

### Products
- `products-mcp___list_products` - List all products
- `products-mcp___get_product_by_id` - Get product by ID
- `products-mcp___search_products` - Search products

### Orders
- `orders-mcp___list_orders` - List orders (both users)
- `orders-mcp___get_order_by_id` - Get order by ID (both users)
- `orders-mcp___create_order` - Create order (FullAccess only)

### Jira
- `jira-mcp___list_jira_tickets` - List Jira tickets

## Architecture Flow

```
VS Code GitHub Copilot
    ↓ (stdio/JSON-RPC)
proxy.sh → proxy.py
    ↓ (HTTP + SigV4 auth)
AWS AgentCore Gateway
    ↓ (Cedar policy check on IAM user tag)
Lambda Functions (customers, products, orders, jira)
```

## Troubleshooting

### Issue: VS Code Not Loading MCP Server

**Solution:** 
1. Check VS Code output panel: `View → Output → Model Context Protocol`
2. Verify proxy script path is absolute (no `~` or relative paths)
3. Restart VS Code completely (Cmd+Q, not just close window)

### Issue: Authentication Error

**Solution:**
1. Verify AWS profile is set: `echo $AWS_PROFILE`
2. Test credentials: `aws sts get-caller-identity --profile test-readonly`
3. Ensure IAM user has `bedrock-agentcore:InvokeGateway` permission

### Issue: Tools Not Showing in Copilot

**Solution:**
1. Ensure MCP server is loaded (check status bar)
2. Try explicitly: "Use the customer-agnostic-gateway to list orders"
3. Check if proxy script is executable: `ls -la npm-package/customer-gateway-proxy/bin/`

### Issue: RBAC Not Working (FullAccess User Denied)

**Solution:**
1. Verify IAM user has tag: `aws iam list-user-tags --user-name test-developer-fullaccess`
2. Check Cedar policy is in ENFORCE mode (not LOG_ONLY)
3. Verify gateway ARN matches in Cedar policy
4. Check CloudWatch logs for policy evaluation details

## Switching Between Users

**Important:** Always fully quit VS Code before switching AWS profiles. VS Code caches credentials on startup.

```bash
# Switch to ReadOnly
export AWS_PROFILE=test-readonly
code .

# To switch to FullAccess:
# 1. Close VS Code (Cmd+Q)
# 2. Change profile
export AWS_PROFILE=test-fullaccess
# 3. Restart VS Code
code .
```

## Security Notes

- The proxy uses your AWS credentials (SigV4 signing)
- No credentials are stored in config files
- Each developer uses their own IAM user credentials
- RBAC is enforced at the gateway level via Cedar policies
- All requests are logged in CloudWatch for audit trail

## Next Steps

See [DEMO.md](DEMO.md) for the complete RBAC demonstration script.
