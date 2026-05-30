# MCP Gateway RBAC Demo Script

## Overview
This demonstrates tool-level RBAC using AWS AgentCore Gateway with Cedar policies.

> **Before running this demo:** Complete [VSCODE_SETUP.md](VSCODE_SETUP.md) first — you need the gateway deployed and VS Code configured with the MCP proxy.

**Two IAM users:**
- `test-developer-readonly` (tag: `group=ReadOnly`) - Can only list/get/search
- `test-developer-fullaccess` (tag: `group=FullAccess`) - Can do everything

---

## Demo Part 1: ReadOnly User

### Setup
```bash
# Terminal
export AWS_PROFILE=test-readonly
aws sts get-caller-identity

# Should show:
# "Arn": "arn:aws:iam::<ACCOUNT_ID>:user/test-developer-readonly"

# Start VS Code
code .
```

### Test in GitHub Copilot Chat

**Prompt 1: List Orders (Should Work ✅)**
```
Show me all orders
```

**Expected Result:**
- ✅ Copilot calls `orders-mcp___list_orders`
- ✅ Returns list of 4 orders
- ✅ No error

**Screenshot:** `readonly-list-success.png`

---

**Prompt 2: Create Order (Should Be DENIED ❌)**
```
Create a new order for customer CUST-001 with 1 unit of product PROD-001
```

**Expected Result:**
- ❌ Copilot calls `orders-mcp___create_order`
- ❌ Error: "Tool Execution Denied: Tool call not allowed due to policy enforcement"
- ❌ Cedar policy blocks the request

**Screenshot:** `readonly-create-denied.png`

---

## Demo Part 2: FullAccess User

### Setup
```bash
# CLOSE VS Code completely (Cmd+Q or Ctrl+Q)

# Terminal
export AWS_PROFILE=test-fullaccess
aws sts get-caller-identity

# Should show:
# "Arn": "arn:aws:iam::<ACCOUNT_ID>:user/test-developer-fullaccess"

# Start VS Code
code .
```

### Test in GitHub Copilot Chat

**Prompt 3: List Orders (Should Work ✅)**
```
Show me all orders
```

**Expected Result:**
- ✅ Works (same as ReadOnly)

---

**Prompt 4: Create Order (Should Work ✅)**
```
Create a new order for customer CUST-001 with 1 unit of product PROD-001
```

**Expected Result:**
- ✅ Copilot calls `orders-mcp___create_order`
- ✅ Returns success with new order created
- ✅ No error - Cedar policy allows it

**Screenshot:** `fullaccess-create-success.png`

---

## Demo Summary Table

| User | Action | Tool Called | Result |
|------|--------|-------------|--------|
| ReadOnly | List Orders | `orders-mcp___list_orders` | ✅ Allowed |
| ReadOnly | Create Order | `orders-mcp___create_order` | ❌ Denied by Cedar |
| FullAccess | List Orders | `orders-mcp___list_orders` | ✅ Allowed |
| FullAccess | Create Order | `orders-mcp___create_order` | ✅ Allowed |

---

## Architecture

```
Developer (with AWS credentials)
    ↓
VS Code GitHub Copilot
    ↓
MCP Proxy (with SigV4 auth)
    ↓
AWS AgentCore Gateway
    ↓
Cedar Policy Engine (checks IAM user tag: group=ReadOnly or FullAccess)
    ↓
Lambda Functions (customers, products, orders, jira)
```

---

## Cedar Policy

```cedar
// ReadOnly users - list/get/search only
permit(
    principal,
    action in [
        AgentCore::Action::"customers-mcp___list_customers",
        AgentCore::Action::"orders-mcp___list_orders",
        // ... more read-only actions
    ],
    resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:<REGION>:<ACCOUNT_ID>:gateway/<GATEWAY_ID>"
)
when {
    principal.hasTag("group") && principal.getTag("group") == "ReadOnly"
};

// FullAccess users - all actions
permit(
    principal,
    action,
    resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:<REGION>:<ACCOUNT_ID>:gateway/<GATEWAY_ID>"
)
when {
    principal.hasTag("group") && principal.getTag("group") == "FullAccess"
};
```

---

## Key Points to Highlight

1. **Same MCP Gateway** - both users connect to the same gateway URL
2. **IAM Tags** - authorization based on `group` tag on IAM user
3. **Cedar Policies** - tool-level RBAC enforced by policy engine
4. **Zero Code Changes** - RBAC purely configuration-based
5. **Enterprise Ready** - can scale to hundreds of developers with different roles

---

## Troubleshooting

**If ReadOnly can create orders:**
- Cedar policy not attached or in LOG_ONLY mode
- Check policy engine is in ENFORCE mode

**If FullAccess cannot create orders:**
- IAM user missing `group=FullAccess` tag
- Cedar policy syntax error
- Check CloudWatch logs for policy evaluation

**If neither user can access:**
- IAM users missing `bedrock-agentcore:InvokeGateway` permission
- Wrong AWS_PROFILE set
- Gateway URL incorrect in proxy script
