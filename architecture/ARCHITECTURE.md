# Architecture Documentation

This repository contains **two independent demos** with different architectures. Each solves a different problem.

---

## Demo #1: AgentCore Gateway with VS Code Integration

**Purpose:** Tool-level RBAC for AI coding assistants using Cedar policies

**Architecture:**

```
┌─────────────────────────────────────────────────────────┐
│  Developer Workstation                                  │
│  ┌───────────────────────────────────────────────────┐ │
│  │  VS Code + GitHub Copilot                         │ │
│  │  AWS Credentials: IAM User                        │ │
│  │  Tags: group=ReadOnly or group=FullAccess         │ │
│  └────────────────┬──────────────────────────────────┘ │
└───────────────────┼──────────────────────────────────────┘
                    │ stdio (MCP protocol)
                    ▼
        ┌───────────────────────────┐
        │   MCP Proxy (local)       │
        │   - Signs with IAM creds  │
        │   - Converts stdio→HTTPS  │
        └───────────┬───────────────┘
                    │ HTTPS + SigV4
                    ▼
        ┌───────────────────────────────────┐
        │  AWS Bedrock AgentCore Gateway    │
        │  ┌─────────────────────────────┐  │
        │  │  Cedar Policy Engine        │  │
        │  │  • Reads IAM user tags      │  │
        │  │  • Evaluates permit/deny    │  │
        │  │  • Enforces tool access     │  │
        │  └─────────────────────────────┘  │
        └───────────┬───────────────────────┘
                    │
        ┌───────────┴──────┬──────┬──────┐
        ▼                  ▼      ▼      ▼
    ┌────────┐        ┌────────┐ ┌────┐ ┌────┐
    │Customers│       │Products│ │Orders Jira│
    │  MCP   │       │  MCP   │ │ MCP│ │MCP │
    │ Lambda │       │ Lambda │ │Lambda Lambda
    └────────┘        └────────┘ └────┘ └────┘
```

### Request Flow (Demo #1)

1. **Developer action in VS Code:**
   - GitHub Copilot calls MCP tool (e.g., `list_customers`)
   
2. **Local MCP Proxy:**
   - Reads AWS credentials from `~/.aws/credentials` (IAM user)
   - Signs request with SigV4 for `bedrock-agentcore` service
   - Sends HTTPS POST to AgentCore Gateway

3. **AgentCore Gateway:**
   - Validates SigV4 signature
   - Reads IAM user tags (e.g., `group=ReadOnly`)
   - Evaluates Cedar policy: Does this user+tag permit this tool?
   - If permit: Routes to Lambda MCP
   - If deny: Returns 403 Forbidden

4. **Lambda MCP:**
   - Executes tool (e.g., queries customer data)
   - Returns result to Gateway → Proxy → Copilot

### Security Model (Demo #1)

**Authentication:** IAM user credentials (SigV4 signing)

**Authorization:** Cedar policies based on IAM user tags

**Cedar Policy Example:**
```cedar
// ReadOnly developers can only list/get
permit(
    principal,
    action in [
        Action::"customers-mcp___list_customers",
        Action::"customers-mcp___get_customer_by_id",
        Action::"orders-mcp___list_orders"
    ],
    resource == Gateway::"<GATEWAY_ARN>"
)
when {
    principal.hasTag("group") && 
    principal.getTag("group") == "ReadOnly"
};

// FullAccess developers can do everything
permit(
    principal,
    action,
    resource == Gateway::"<GATEWAY_ARN>"
)
when {
    principal.hasTag("group") && 
    principal.getTag("group") == "FullAccess"
};
```

### Key Components (Demo #1)

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **AgentCore Gateway** | AWS Bedrock AgentCore (preview) | Central authorization layer |
| **Cedar Policies** | Cedar policy language | Declarative RBAC rules |
| **Lambda MCPs** | AWS Lambda (Python) | Tool implementations |
| **MCP Proxy** | Python script (local) | stdio → HTTPS bridge |
| **VS Code** | GitHub Copilot extension | Developer interface |

---

## Demo #2: Direct Bedrock API with Team-Based Access

**Purpose:** Team-based model access control with cost tracking

**Architecture:**

```
┌────────────────────────────────────────┐
│  Browser (chatbox.html)                │
│  Team Alpha: API Key → team-alpha      │
│  Team Beta:  API Key → team-beta       │
└────────────────┬───────────────────────┘
                 │ HTTPS + x-api-key
                 ▼
      ┌──────────────────────┐
      │   API Gateway (REST) │
      │   • Validates API key│
      │   • Usage plans      │
      │   • Rate limiting    │
      └──────────┬───────────┘
                 │
                 ▼
      ┌─────────────────────────────────┐
      │  Lambda Proxy                   │
      │  1. Map key → team              │
      │  2. Check model permissions     │
      │  3. Call bedrock.invoke_model() │
      │  4. Log with team attribution   │
      └──────────┬──────────────────────┘
                 │
                 ▼
      ┌─────────────────────────┐
      │  AWS Bedrock API        │
      │  • Claude Haiku         │
      │  • Claude Sonnet        │
      │  • Claude Opus          │
      └─────────────────────────┘
```

### Request Flow (Demo #2)

1. **User types in browser:**
   - Chatbox sends: `{team: "team-alpha", prompt: "Hello", model_id: "haiku"}`

2. **API Gateway:**
   - Routes POST /mcp → Lambda Proxy
   - No authentication (demo simplification)

3. **Lambda Proxy:**
   - Extracts team identifier
   - Checks if team can use requested model
     - Team Alpha: ✅ Haiku, Sonnet (❌ Opus)
     - Team Beta: ✅ Haiku only
   - If allowed: Calls `bedrock.invoke_model()`
   - If denied: Returns 403 with error message

4. **Bedrock API:**
   - Invokes Claude model
   - Returns response to Lambda → API Gateway → Browser

### Security Model (Demo #2)

**Authentication:** REST API Gateway with API keys and usage plans

**Authorization:** Model permissions enforced in Lambda code per team

**Lambda Environment Variables:**
```python
TEAM_ALPHA_MODELS = "haiku,sonnet"
TEAM_BETA_MODELS = "haiku"
```

**IAM Permissions:**
```yaml
Lambda Execution Role:
  - bedrock:InvokeModel
    Resource:
      - arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-haiku*
      - arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet*
```

### Key Components (Demo #2)

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Gateway** | REST API with API keys | Entry point with auth + rate limiting |
| **Lambda Proxy** | AWS Lambda (Python) | Model governance + Bedrock calls |
| **Bedrock API** | AWS Bedrock runtime | Claude model inference |
| **Chatbox** | Static HTML/JS | Browser UI for testing |

---

## Key Architectural Differences

| Aspect | Demo #1 | Demo #2 |
|--------|---------|---------|
| **Gateway Layer** | ✅ AgentCore Gateway | ❌ No Gateway (direct Bedrock) |
| **Authorization** | Cedar policies (tag-based) | Lambda code (team-based) |
| **Interface** | VS Code stdio | Browser HTTPS |
| **Permissions Level** | Tool-level (list vs create) | Model-level (Haiku vs Sonnet) |
| **Authentication** | IAM user credentials | API keys + usage plans |
| **AWS Services** | AgentCore (preview), Lambda | API Gateway, Lambda, Bedrock |
| **Cost Tracking** | Per IAM user | Per team (in Lambda logs) |

---

## Scalability

### Demo #1 (AgentCore Gateway)

**Throughput:**
- AgentCore Gateway: Service-managed (check AWS limits)
- Lambda MCPs: 1,000 concurrent executions (default)

**Latency:**
- Cold start: 200-500ms (first request)
- Warm: 100-200ms (gateway + Lambda)

**Scaling:**
- Horizontal: AgentCore + Lambda auto-scale
- Bottleneck: AgentCore Gateway limits (preview service)

---

### Demo #2 (Direct Bedrock)

**Throughput:**
- API Gateway: 10,000 req/sec per region
- Lambda: 1,000 concurrent executions (default)
- Bedrock: Model-specific quotas (check console)

**Latency:**
- Cold start: 200-300ms (first Lambda)
- Warm: 50-100ms (Lambda) + 500-2000ms (Bedrock inference)

**Scaling:**
- Horizontal: API Gateway + Lambda auto-scale
- Bottleneck: Bedrock model quotas (request quota increase)

---

## Cost Estimates

### Demo #1 (10 developers, 100 tool calls/day)

| Service | Monthly Cost |
|---------|-------------|
| AgentCore Gateway | ~$5 |
| Lambda MCPs | ~$1 |
| CloudWatch Logs | ~$0.50 |
| **Total** | **~$6.50/month** |

---

### Demo #2 (10 teams, 1000 requests/day)

| Service | Monthly Cost |
|---------|-------------|
| API Gateway | ~$3 |
| Lambda Proxy | ~$1 |
| Bedrock (Haiku) | ~$900 |
| CloudWatch Logs | ~$2.50 |
| **Total** | **~$906.50/month** |

*Bedrock inference is 99% of costs*

---

## Monitoring

### Demo #1 CloudWatch Metrics

- `bedrock-agentcore:InvokeGateway` - Gateway invocations
- `Lambda:Invocations` - MCP tool calls
- `Lambda:Duration` - Execution time
- `Lambda:Errors` - Failed tool calls

**Log Groups:**
- `/aws/lambda/<mcp-function-name>` - Tool execution logs
- AgentCore Gateway logs (managed service)

---

### Demo #2 CloudWatch Metrics

- `ApiGateway:Count` - Total requests
- `ApiGateway:4XXError`, `5XXError` - Error rates
- `Lambda:Invocations` - Proxy calls
- Bedrock metrics (in CloudWatch)

**Log Groups:**
- `/aws/lambda/gateway-proxy` - Team requests + model denials

**Sample Log Entry:**
```json
{
  "timestamp": "2026-05-30T12:00:00Z",
  "team": "team-alpha",
  "model": "haiku",
  "status": "success",
  "input_tokens": 20,
  "output_tokens": 50,
  "latency_ms": 850
}
```

---

## Security Best Practices

### Demo #1 (Production Recommendations)

- ✅ Use IAM users with MFA enabled
- ✅ Rotate IAM credentials every 90 days
- ✅ Enable CloudTrail for audit logs
- ✅ Set up CloudWatch alarms for denied requests
- ✅ Review Cedar policies quarterly

---

### Demo #2 (Production Recommendations)

- ✅ REST API with API keys and usage plans (implemented)
- ✅ Rate limiting per team via usage plans (implemented)
- ✅ Store API key→team mapping in environment variables or Secrets Manager
- ✅ Enable AWS WAF for DDoS protection (optional)
- ✅ Set CloudWatch log retention (implemented, configurable)
- ✅ Structured audit logging for CloudWatch Insights (implemented)

---

## When to Use Which Demo

**Use Demo #1 (AgentCore Gateway) when:**
- You need **tool-level permissions** (not just model-level)
- You want **Cedar policy** declarative RBAC
- You're building **VS Code/IDE integrations**
- You need **per-developer** audit trails
- You have **AgentCore preview access**

**Use Demo #2 (Direct Bedrock) when:**
- You need **model-level permissions** (Haiku vs Sonnet)
- You want **browser-based UI**
- You need **team-based cost tracking**
- You want **standard AWS services only** (no preview)
- You prioritize **simplicity over fine-grained control**

---

**Architecture Version:** 2.0  
**Last Updated:** June 2026  
**Note:** These are two independent architectures. Pick one based on your use case.
