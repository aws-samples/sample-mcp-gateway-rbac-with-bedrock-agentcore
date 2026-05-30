# AWS Bedrock Governance Demos

> **Two independent demos showing different patterns for governing AI access at scale**

This repository contains **two separate, independent demos** that solve different problems. Pick the one that matches your use case.

---

## 🎯 Choose Your Demo

### Demo #1: AgentCore Gateway with VS Code + GitHub Copilot
📁 **Location:** `gateway-url-ide-integration-demo/`

**What it does:** Tool-level RBAC for AI coding assistants using AWS Bedrock AgentCore Gateway and Cedar policies.

**Architecture:**
```
VS Code/Copilot → AgentCore Gateway → Cedar RBAC → Lambda MCPs
```

**Use this if you want:**
- ✅ GitHub Copilot integration with VS Code
- ✅ Tool-level permissions (e.g., junior devs can *list* customers but not *create* orders)
- ✅ Cedar policy engine for declarative RBAC
- ✅ IAM user tag-based permissions
- ✅ Per-developer audit logs

**Prerequisites:**
- ⚠️ **AWS Bedrock AgentCore access** (preview service - [contact AWS](https://aws.amazon.com/bedrock/) for access)
- VS Code + GitHub Copilot
- Node.js 18+ (for AgentCore CLI)
- Python 3.11+

**👉 Start here:** [gateway-url-ide-integration-demo/README.md](gateway-url-ide-integration-demo/README.md)

---

### Demo #2: Browser Chat with Team-Based Model Access
📁 **Location:** `team-rbac-bedrock-chat-demo/`

**What it does:** Team-based model access control with cost tracking using direct Bedrock API calls.

**Architecture:**
```
Browser → API Gateway → Lambda → Bedrock API (DIRECT - no AgentCore Gateway)
```

**Use this if you want:**
- ✅ Browser-based chatbox UI
- ✅ Team-based model access (e.g., Team Alpha gets Sonnet, Team Beta gets Haiku only)
- ✅ Cost tracking and attribution per team
- ✅ Standard AWS services only (no preview access needed)
- ✅ Simpler setup and deployment

**Prerequisites:**
- ✅ Standard AWS account (no preview access needed)
- AWS Bedrock API access
- Python 3.11+

**👉 Start here:** [team-rbac-bedrock-chat-demo/README.md](team-rbac-bedrock-chat-demo/README.md)

---

## 🚨 Critical: These Demos Are INDEPENDENT

| Question | Answer |
|----------|--------|
| **Do I need both demos?** | ❌ NO - Pick ONE based on your use case |
| **Does Demo 2 need Demo 1's Gateway?** | ❌ NO - Demo 2 goes directly to Bedrock API |
| **Can I deploy Demo 2 first?** | ✅ YES - They're completely independent |
| **Do they share infrastructure?** | ❌ NO - Separate CloudFormation/deployment |
| **Different prerequisites?** | ✅ YES - Demo 1 needs AgentCore preview access |

---

## Quick Comparison

| Feature | Demo #1 (AgentCore Gateway) | Demo #2 (Direct Bedrock) |
|---------|----------------------------|--------------------------|
| **Interface** | VS Code + GitHub Copilot | Browser chatbox |
| **RBAC Level** | Tool-level (e.g., `list_orders` vs `create_order`) | Model-level (e.g., Haiku vs Sonnet) |
| **Policy Engine** | Cedar policies | Lambda code + IAM policies |
| **AWS Services** | AgentCore Gateway (preview) | API Gateway + Lambda + Bedrock |
| **Setup Time** | 15-20 min (requires AgentCore access) | 10-15 min (standard AWS) |
| **Cost Attribution** | Per IAM user | Per team |
| **Preview Access Needed?** | ⚠️ YES (contact AWS) | ✅ NO |

---

## Common Questions

### "Which demo should I start with?"

**Start with Demo #2** if:
- You want the quickest path to testing
- You don't have AgentCore preview access yet
- You care about team-based model access and cost tracking
- You want a browser-based UI

**Start with Demo #1** if:
- You have AgentCore preview access
- You want VS Code + GitHub Copilot integration
- You need fine-grained tool-level permissions
- You want Cedar policy-based RBAC

### "Can I use both demos together?"

Yes, but they're **designed to be independent**. Each demo stands alone and solves a different problem:
- **Demo #1** = Developer productivity with governed AI coding assistants
- **Demo #2** = Team-based LLM access control with cost tracking

You can deploy both in the same AWS account, but they don't share infrastructure or depend on each other.

### "What if I don't have AgentCore access?"

Start with **Demo #2** - it uses standard AWS services (API Gateway, Lambda, Bedrock) that are generally available. No preview access needed.

To get AgentCore access for Demo #1, [contact AWS](https://aws.amazon.com/bedrock/) or your AWS account team.

---

## What's Inside Each Demo

### Demo #1 Contents (`gateway-url-ide-integration-demo/`)

```
gateway-url-ide-integration-demo/
├── README.md                    # Demo overview
├── DEPLOYMENT.md                # Step-by-step setup
├── DEMO.md                      # Testing scenarios
├── VSCODE_SETUP.md              # VS Code configuration
│
├── DemoMcpGateway/              # AgentCore Gateway config
│   ├── agentcore/
│   │   └── agentcore.json       # Gateway definition
│   └── policies/
│       └── rbac-policy.cedar    # Cedar RBAC policies
│
├── lambda/mcp-servers/          # Lambda MCPs
│   ├── ecommerce-mcp/           # Customers tools
│   ├── products-mcp/            # Products tools
│   ├── orders-mcp/              # Orders tools
│   └── jira-mcp/                # Jira tools
│
└── vscode-config/
    └── mcp.json                 # VS Code MCP config template
```

**Deploys:**
- AgentCore Gateway
- 4 Lambda MCP servers
- Cedar policies
- IAM roles for developers

---

### Demo #2 Contents (`team-rbac-bedrock-chat-demo/`)

```
team-rbac-bedrock-chat-demo/
├── README.md                    # Demo overview
├── DEPLOYMENT.md                # Step-by-step setup
├── DEMO.md                      # Testing scenarios
│
├── chatbox.html                 # Browser chat UI
│
├── lambda/
│   └── gateway-proxy/           # Lambda proxy (API Gateway → Bedrock)
│       └── lambda_function.py   # Direct Bedrock API calls
│
└── infrastructure/
    └── cloudformation/
        └── main-stack.yaml      # API Gateway, Lambda, IAM roles
```

**Deploys:**
- API Gateway with usage plans
- Lambda proxy function
- IAM roles for teams
- CloudWatch logging

---

## Getting Started

### For Demo #1 (AgentCore Gateway + VS Code):

```bash
# 1. Check prerequisites
agentcore --version  # Verify AgentCore CLI installed

# 2. Deploy gateway
cd gateway-url-ide-integration-demo/DemoMcpGateway/agentcore
agentcore deploy

# 3. Follow VS Code setup guide
open ../VSCODE_SETUP.md
```

**Full guide:** [gateway-url-ide-integration-demo/DEPLOYMENT.md](gateway-url-ide-integration-demo/DEPLOYMENT.md)

---

### For Demo #2 (Browser Chat + Team RBAC):

```bash
# 1. Deploy infrastructure
cd team-rbac-bedrock-chat-demo/infrastructure/cloudformation
aws cloudformation create-stack \
  --stack-name llm-gateway-demo \
  --template-body file://main-stack.yaml \
  --capabilities CAPABILITY_IAM

# 2. Update chatbox.html with API Gateway URL and API keys

# 3. Open in browser
open ../../chatbox.html
```

**Full guide:** [team-rbac-bedrock-chat-demo/DEPLOYMENT.md](team-rbac-bedrock-chat-demo/DEPLOYMENT.md)

---

## Architecture Diagrams

### Demo #1 Architecture (AgentCore Gateway)

```
┌─────────────────────────────────────────────────────────┐
│  Developer Workstation                                  │
│  ┌───────────────────────────────────────────────────┐ │
│  │  VS Code + GitHub Copilot                         │ │
│  │  AWS Credentials: IAM User (tag: group=ReadOnly)  │ │
│  └────────────────┬──────────────────────────────────┘ │
└───────────────────┼──────────────────────────────────────┘
                    │ stdio + SigV4
                    ▼
        ┌───────────────────────────┐
        │   MCP Proxy (local)       │
        │   Signs with IAM creds    │
        └───────────┬───────────────┘
                    │ HTTPS + SigV4
                    ▼
        ┌───────────────────────────────────┐
        │  AWS Bedrock AgentCore Gateway    │
        │  ┌─────────────────────────────┐  │
        │  │  Cedar Policy Engine        │  │
        │  │  • Reads IAM user tags      │  │
        │  │  │  Evaluates permit/deny   │  │
        │  └─────────────────────────────┘  │
        └───────────┬───────────────────────┘
                    │
        ┌───────────┴──────┬──────┬──────┐
        ▼                  ▼      ▼      ▼
    ┌────────┐        ┌────────┐ ┌────┐ ┌────┐
    │Customers        │Products│ │Orders Jira│
    │  MCP   │        │  MCP   │ │ MCP│ │MCP │
    │Lambda  │        │ Lambda │ │Lambda Lambda
    └────────┘        └────────┘ └────┘ └────┘
```

---

### Demo #2 Architecture (Direct Bedrock)

```
┌────────────────────────────────────────┐
│  Browser (chatbox.html)                │
│  Team Alpha: API Key → team-alpha      │
│  Team Beta:  API Key → team-beta       │
└────────────────┬───────────────────────┘
                 │ HTTPS + x-api-key
                 ▼
      ┌──────────────────────┐
      │   API Gateway        │
      │   • Validates key    │
      │   • Usage plans      │
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

**Key Difference:** Demo #2 goes **directly to Bedrock API** - no AgentCore Gateway!

---

## Use Cases

### Demo #1 Use Cases (Tool-Level RBAC)

1. **Enterprise Developer Productivity**
   - Junior developers: Read-only tool access
   - Senior developers: Full CRUD tool access
   - Admins: Infrastructure and deployment tools

2. **Multi-Team MCP Governance**
   - Support team: customer-mcp + jira-mcp only
   - Engineering team: All MCPs
   - Data science team: analytics-mcp only

3. **Compliance & Audit**
   - Every tool invocation logged with IAM principal
   - CloudWatch logs for SOC2/HIPAA compliance

---

### Demo #2 Use Cases (Model-Level RBAC)

1. **Cost Control by Team**
   - Team A: Balanced (Haiku + Sonnet)
   - Team B: Cost-optimized (Haiku only)
   - Monthly chargeback per team

2. **Gradual Model Rollout**
   - Start all teams on Haiku
   - Promote alpha teams to Sonnet
   - Restrict Opus to high-value use cases

3. **Department-Based Access**
   - Engineering: Full model access
   - Support: Basic models only
   - Executives: Premium models

---

## Troubleshooting

### Demo #1 Issues

**"AgentCore CLI not found"**
```bash
npm install -g @aws/agentcore-cli
agentcore --version
```

**"Gateway deployment fails"**
- Check you have AgentCore preview access
- Verify CDK dependencies: `cd cdk && npm install`

**Full troubleshooting:** [gateway-url-ide-integration-demo/DEPLOYMENT.md](gateway-url-ide-integration-demo/DEPLOYMENT.md)

---

### Demo #2 Issues

**"403 Forbidden from Lambda"**
- Check IAM role has `bedrock:InvokeModel` permission
- Verify Lambda environment variables are set correctly

**"CloudFormation stack fails"**
- Ensure S3 bucket exists (if using S3 for Lambda code)
- Check you have sufficient IAM permissions

**Full troubleshooting:** [team-rbac-bedrock-chat-demo/DEPLOYMENT.md](team-rbac-bedrock-chat-demo/DEPLOYMENT.md)

---

## Cost Estimates

### Demo #1 (AgentCore Gateway)
**For 10 developers, 100 tool calls/day:**

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| AgentCore Gateway | 30K requests | ~$5 |
| Lambda (MCPs) | 30K invocations | ~$1 |
| CloudWatch Logs | 1 GB | ~$0.50 |
| **Total** | | **~$6.50/month** |

---

### Demo #2 (Direct Bedrock)
**For 10 teams, 1000 requests/day:**

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| API Gateway | 300K requests | ~$3 |
| Lambda (proxy) | 300K invocations | ~$1 |
| CloudWatch Logs | 5 GB | ~$2.50 |
| Bedrock (Haiku) | 300K × 1K tokens | ~$900 |
| **Total** | | **~$906.50/month** |

*Bedrock model costs dominate - gateway overhead is minimal*

---

## Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Cedar Policy Language](https://www.cedarpolicy.com/)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

We welcome:
- New MCP server examples (Demo #1)
- Additional Lambda proxy patterns (Demo #2)
- Cedar policy examples
- Integration guides for other AI tools

---

## License

This library is licensed under the MIT-0 License. See [LICENSE](LICENSE).

---

## Support

For questions or issues:
1. Check the demo-specific README and DEPLOYMENT guide
2. Review troubleshooting sections
3. Open an issue in this repository

---

**🎯 Remember:** These are **two independent demos**. Pick the one that matches your use case, and don't assume you need both!

- **Tool-level RBAC for AI coding?** → Demo #1
- **Team-based model access control?** → Demo #2

**Happy building!** 🚀
