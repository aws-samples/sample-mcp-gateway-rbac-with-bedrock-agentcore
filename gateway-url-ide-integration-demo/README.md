# Enterprise MCP Governance with AWS Bedrock AgentCore Gateway

> **Give 100 developers access to AI tools, but control who can do what—without changing any code.**

This sample shows how to implement **tool-level role-based access control (RBAC)** for Model Context Protocol (MCP) servers using AWS Bedrock AgentCore Gateway and Cedar policies.

## The Problem

Your organization wants to give developers AI coding assistants (like GitHub Copilot) with access to internal tools:
- Junior developers should **read** customer data, but not modify it
- Senior developers should have **full access** to create orders, update records, etc.
- Security team needs **audit logs** of who used which tools

**Without a gateway:** You'd need to build authentication into every MCP server, manage permissions in multiple places, and hope developers don't accidentally expose sensitive tools.

## The Solution

**AWS Bedrock AgentCore Gateway** acts as a centralized authorization layer:

```
Developer → GitHub Copilot → AgentCore Gateway → Cedar Policy Check → MCP Tools
                                      ↓
                              ✅ "list_customers" allowed
                              ❌ "create_order" denied
```

**Key Benefits:**
- ✅ **Zero code changes** - RBAC is pure configuration (Cedar policies)
- ✅ **Individual developer permissions** - Based on IAM user tags
- ✅ **Centralized governance** - One gateway controls access to all MCP servers
- ✅ **Audit trail** - Every tool call logged with developer identity

---

## Quick Demo (5 minutes)

See tool-level RBAC in action with GitHub Copilot.

> **Full setup guide:** [VSCODE_SETUP.md](VSCODE_SETUP.md)

### Prerequisites
- AWS account with Bedrock AgentCore access
- GitHub Copilot in VS Code
- Python 3.11+
- Two IAM users with different tags (created once by admin):
  ```bash
  # Create ReadOnly developer
  aws iam create-user --user-name test-developer-readonly
  aws iam tag-user --user-name test-developer-readonly \
    --tags Key=group,Value=ReadOnly

  # Create FullAccess developer
  aws iam create-user --user-name test-developer-fullaccess
  aws iam tag-user --user-name test-developer-fullaccess \
    --tags Key=group,Value=FullAccess

  # Attach gateway access policy to both users
  # (see iam-policies/simple-gateway-access.json)
  ```

### Steps

⚠️ **First-time setup?** Follow the complete deployment guide: **[DEPLOYMENT.md](DEPLOYMENT.md)**

The deployment guide covers:
1. Creating Lambda execution role
2. Deploying Lambda MCPs (customers, products, orders, jira)
3. Deploying AgentCore Gateway
4. Configuring Cedar policies
5. Creating test IAM users

**Quick summary** (assumes infrastructure is already deployed):

1. **Deploy the gateway** (~5 min, one time by admin):
   ```bash
   cd DemoMcpGateway/agentcore
   npm install -g @aws/agentcore-cli
   agentcore deploy
   # Outputs: Gateway URL like https://<id>.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp
   # Copy this URL — you'll need it in step 2
   ```
   See [DEPLOYMENT.md](DEPLOYMENT.md) for complete setup instructions.

2. **Configure VS Code** (each developer):
   ```bash
   # Copy the MCP config to VS Code settings
   cp vscode-config/mcp.json ~/Library/Application\ Support/Code/User/mcp.json

   # Edit mcp.json — set GATEWAY_URL to the URL from step 1
   # Then set your AWS profile before launching VS Code:
   export AWS_PROFILE=test-readonly   # or test-fullaccess
   code .
   ```

3. **Test RBAC** (see [DEMO.md](DEMO.md) for the full script):
   - **ReadOnly user** → ask Copilot "Show me all orders" ✅, then "Create an order" ❌ (Cedar denies it)
   - **FullAccess user** → both work ✅

**Result:** Same gateway URL, different permissions per developer — controlled by Cedar policies, not code.

---

> **This repo also includes:** a [Guardrails demo](../team-rbac-bedrock-chat-demo/GUARDRAIL_DEMO.md) (multi-lingual content filtering) and a [Cost Tracking demo](../team-rbac-bedrock-chat-demo/COST_EXPLORER_SETUP.md) (per-IAM-principal Bedrock cost attribution). These are **independent** of the RBAC demo above — start with RBAC, explore the others when ready.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Developer Workstation                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  VS Code + GitHub Copilot                           │   │
│  │  AWS Credentials: IAM User (tagged: group=ReadOnly) │   │
│  └────────────────┬────────────────────────────────────┘   │
└───────────────────┼─────────────────────────────────────────┘
                    │ stdio + SigV4 auth
                    ▼
        ┌───────────────────────────┐
        │   MCP Proxy (local)       │
        │   Signs request with      │
        │   developer's IAM creds   │
        └───────────┬───────────────┘
                    │ HTTPS + SigV4
                    ▼
        ┌───────────────────────────────────────┐
        │  AWS Bedrock AgentCore Gateway        │
        │  ┌─────────────────────────────────┐  │
        │  │  Cedar Policy Engine            │  │
        │  │  • Reads IAM user tags          │  │
        │  │  • Evaluates: permit/deny?      │  │
        │  │  • Logs decision to CloudWatch  │  │
        │  └─────────────────────────────────┘  │
        └───────────┬───────────────────────────┘
                    │
        ┌───────────┴────────┬──────────┬────────┐
        ▼                    ▼          ▼        ▼
    ┌────────┐          ┌────────┐ ┌──────┐ ┌──────┐
    │Customers│         │Products│ │Orders│ │Jira  │
    │  MCP   │         │  MCP   │ │ MCP  │ │ MCP  │
    │Lambda  │         │ Lambda │ │Lambda│ │Lambda│
    └────────┘          └────────┘ └──────┘ └──────┘
```

**Flow:**
1. Developer uses GitHub Copilot: "Create an order for customer CUST-001"
2. Copilot calls `orders-mcp___create_order` via MCP proxy
3. Proxy signs request with developer's IAM credentials (SigV4)
4. Gateway checks Cedar policy: Does this IAM user's `group` tag permit this action?
   - `group=ReadOnly` → ❌ Denied
   - `group=FullAccess` → ✅ Allowed
5. If allowed, gateway invokes the orders Lambda
6. Response flows back to Copilot

---

## What's Included

### 🎯 Four Sample MCP Servers (Lambda functions)
- **Customers MCP** - `list_customers`, `get_customer_by_id`
- **Products MCP** - `list_products`, `search_products`, `get_product_by_id`
- **Orders MCP** - `list_orders`, `get_order_by_id`, `create_order`
- **Jira MCP** - `list_jira_tickets`

### 🔐 Cedar Policies for RBAC
```cedar
// ReadOnly developers: Can only list/get/search
permit(
    principal,
    action in [
        AgentCore::Action::"customers-mcp___list_customers",
        AgentCore::Action::"orders-mcp___list_orders",
        // ... read-only actions
    ],
    resource == AgentCore::Gateway::"<YOUR_GATEWAY_ARN>"
)
when {
    principal.hasTag("group") && principal.getTag("group") == "ReadOnly"
};

// FullAccess developers: Can use all tools
permit(
    principal,
    action,
    resource == AgentCore::Gateway::"<YOUR_GATEWAY_ARN>"
)
when {
    principal.hasTag("group") && principal.getTag("group") == "FullAccess"
};
```

### 🛠️ VS Code Integration
- MCP proxy for stdio-to-HTTP bridging with SigV4 signing
- GitHub Copilot configuration
- Per-developer AWS credentials via `AWS_PROFILE`

---

## Repository Structure

```
bedrock-agentcore-mcp-gateway-demo/
├── README.md                    # ← You are here
├── DEMO.md                      # Step-by-step RBAC demo script
├── VSCODE_SETUP.md              # VS Code + GitHub Copilot setup
│
├── DemoMcpGateway/              # Gateway configuration (deploy this first)
│   ├── agentcore/
│   │   └── agentcore.json       # Declares the gateway + points to Lambda targets below
│   ├── policies/
│   │   └── rbac-policy.cedar    # ReadOnly/FullAccess Cedar policies
│   └── tool-schemas/            # JSON schemas for each MCP tool
│
├── lambda/mcp-servers/          # The Lambda functions that agentcore.json points to
│   ├── ecommerce-mcp/           # Customers Lambda  (list_customers, get_customer_by_id)
│   ├── products-mcp/            # Products Lambda   (list_products, search_products, ...)
│   ├── orders-mcp/              # Orders Lambda     (list_orders, create_order, ...)
│   └── jira-mcp/                # Jira Lambda       (list_jira_tickets)
│
├── npm-package/customer-gateway-proxy/
│   └── bin/
│       ├── proxy.py             # MCP stdio-to-HTTP proxy with SigV4 signing
│       └── proxy.sh             # Shell wrapper (used by VS Code)
│
├── vscode-config/
│   └── mcp.json                 # VS Code MCP server config template — copy to ~/Library/...
│
└── iam-policies/                # IAM policies to attach to developer IAM users
    ├── simple-gateway-access.json      # Basic: allow InvokeGateway
    ├── readonly-policy.json            # Restricts to read-only tools via IAM condition
    ├── fullaccess-policy.json          # Allows all tools
    ├── developer-gateway-access.json   # General developer access
    └── gateway-policy-engine-access.json  # For the gateway's Cedar policy engine role
```

---

## Use Cases

### 1. **Enterprise Developer Productivity + Governance**
Give all developers AI coding assistants with access to internal tools, but enforce least-privilege access:
- Interns: Read-only access to documentation MCP
- Junior devs: Read customer/product data
- Senior devs: Full CRUD operations
- Admins: Access to deployment and infrastructure MCPs

### 2. **Multi-Team Organization**
Different teams need different tool access:
- **Support team**: Access to customer-mcp and jira-mcp only
- **Engineering team**: Access to all MCPs
- **Data science team**: Access to analytics-mcp only

### 3. **Compliance & Audit**
- Every MCP tool invocation logged with developer IAM identity
- CloudWatch logs show: who, what tool, when, allowed/denied
- Meet SOC2/HIPAA audit requirements for AI tool usage

### 4. **Gradual Rollout**
- Start with read-only access for all developers
- Promote senior devs to full access after training
- All changes via Cedar policy updates—no code deployment

---

## How It Works: Cedar Policies + IAM Tags

### Step 1: Tag IAM Users
```bash
# Tag junior developer as ReadOnly
aws iam tag-user \
  --user-name alice@company.com \
  --tags Key=group,Value=ReadOnly

# Tag senior developer as FullAccess
aws iam tag-user \
  --user-name bob@company.com \
  --tags Key=group,Value=FullAccess
```

### Step 2: Cedar Policy Checks Tags
When Alice tries to call `orders-mcp___create_order`:
1. Gateway reads Alice's IAM user tags: `{group: "ReadOnly"}`
2. Cedar evaluates: Does any policy permit this principal + action?
3. Only the ReadOnly policy matches Alice, but it doesn't include `create_order`
4. Result: **Denied**

When Bob calls the same tool:
1. Gateway reads Bob's tags: `{group: "FullAccess"}`
2. FullAccess policy permits ALL actions on the gateway
3. Result: **Allowed**

**No code changes needed.** Just update Cedar policies or IAM tags.

---

## Getting Started

### Option 1: Quick RBAC Demo (Recommended)

Follow [VSCODE_SETUP.md](VSCODE_SETUP.md) to:
1. Deploy the gateway
2. Configure VS Code with your gateway URL
3. Test with two IAM users (ReadOnly vs FullAccess)
4. See RBAC enforcement in GitHub Copilot

**Time:** 15 minutes

### Option 2: Extend for Your Use Case

1. **Add your own MCP servers:**
   - Create Lambda functions for your internal tools
   - Add tool schemas to `DemoMcpGateway/tool-schemas/`
   - Register as targets in `agentcore.json`

2. **Customize Cedar policies:**
   - Define your own groups (e.g., `Intern`, `Engineer`, `Admin`)
   - Create fine-grained rules (e.g., "Engineers can only delete test data")
   - See [Cedar documentation](https://www.cedarpolicy.com/)

3. **Scale to production:**
   - Integrate with SSO (Okta, Azure AD) for user management
   - Add monitoring/alerting for denied requests
   - Set up CI/CD for Lambda and Cedar policy updates

---

## Troubleshooting

### "Tool Execution Denied" even though IAM policy allows?
- Cedar policies are separate from IAM policies
- Check Cedar policy is attached to gateway in **ENFORCE** mode (not LOG_ONLY)
- Verify IAM user has the correct tag: `aws iam list-user-tags --user-name YOUR_USER`

### Gateway returns 401 Unauthorized?
- IAM user needs `bedrock-agentcore:InvokeGateway` permission
- Check `iam-policies/simple-gateway-access.json` is attached to user

### VS Code not loading MCP server?
- VS Code MCP config must use absolute path or `${workspaceFolder}`
- Check VS Code Output panel → "Model Context Protocol" for errors
- Restart VS Code completely (Cmd+Q, not just close window)

See [VSCODE_SETUP.md](VSCODE_SETUP.md) for detailed troubleshooting.

---

## Security Considerations

- ✅ All requests authenticated via AWS SigV4 with IAM credentials
- ✅ No credentials stored in config files (uses AWS credential chain)
- ✅ Gateway enforces least-privilege access at tool level
- ✅ All tool invocations logged to CloudWatch with IAM principal
- ✅ Cedar policies support conditions (e.g., time-based, IP-based access)

**Production recommendations:**
- Enable MFA for IAM users with FullAccess
- Set up CloudWatch alarms for denied requests (potential security issue)
- Regularly review Cedar policies and IAM tags
- Use IAM roles (not users) for federated access via SSO

---

## Cost Estimate

**Demo setup (10 developers, 100 tool calls/day each):**

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| Bedrock AgentCore Gateway | 30,000 requests | ~$5.00 |
| Lambda (MCP servers) | 30,000 invocations | ~$1.00 |
| CloudWatch Logs | 1 GB | ~$0.50 |
| **Total** | | **~$6.50/month** |

**Free tier eligible** for first 12 months (Lambda, CloudWatch).

---

## Resources

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Cedar Policy Language](https://www.cedarpolicy.com/)
- [GitHub Blog: Connecting MCP to Bedrock](https://aws.amazon.com/blogs/machine-learning/connecting-mcp-servers-to-amazon-bedrock-agentcore-gateway/)

---

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md). We welcome:
- New MCP server examples
- Cedar policy patterns for common scenarios
- Integration guides for other AI tools (VS Code extensions, Claude Desktop, etc.)

## License

This library is licensed under the MIT-0 License. See the [LICENSE](../LICENSE) file.

---

**Built by the AWS TAM team to help customers adopt AI tools safely at scale.**

For questions or feedback, open an issue in this repository.
