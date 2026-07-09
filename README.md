# AWS Bedrock Governance Demos

> **Three independent demos showing different patterns for governing AI access at scale**

| | Demo #1: AgentCore Gateway | Demo #2: Team RBAC Chat | Demo #3: Bifrost AI Gateway |
|---|---|---|---|
| **⏱️ Deploy Time** | **~15 minutes** | **~10 minutes** | **~20 minutes** |
| **Interface** | VS Code + GitHub Copilot | Browser chatbox | Browser chatbox + CloudFront |
| **Governance Level** | Tool-level (Cedar RBAC) | Model-level (per-team) | Model-level (virtual keys + quotas) |
| **Preview Access?** | ⚠️ Yes (AgentCore) | ✅ No — standard AWS | ✅ No — standard AWS |
| **Production-Ready?** | Demo only | Demo only | ✅ Yes — CloudFront, EFS, Grafana |

This repository contains **three separate, independent demos** that solve different problems. Pick the one that matches your use case.

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

### Demo #3: Bifrost AI Gateway — Production-Ready Multi-Team LLM Gateway
� **Location:** `bifrost-implementation/`

**What it does:** A fully production-grade AI gateway using [Bifrost](https://github.com/maximhq/bifrost) on ECS Fargate, fronted by CloudFront, with per-team virtual keys, daily token quotas, CloudWatch observability, and optional Amazon Managed Grafana dashboards.

**Architecture:**
```
Browser → CloudFront (HTTPS) → Internal ALB → ECS Fargate (Bifrost) → AWS Bedrock
                                                       │
                                               CloudWatch Logs/Metrics
                                               Amazon Managed Grafana (optional)
```

**Use this if you want:**
- ✅ Production-ready gateway (not just a demo)
- ✅ Per-team virtual API keys with daily token quotas
- ✅ Model-level RBAC (Team Alpha: Haiku + Sonnet; Team Beta: Haiku only)
- ✅ CloudFront HTTPS frontend with internal ALB (no public ECS exposure)
- ✅ EFS-backed config persistence across container restarts
- ✅ CloudWatch dashboard with real-time quota gauges and request metrics
- ✅ Amazon Managed Grafana + Prometheus (optional)
- ✅ Fully automated CDK TypeScript deployment
- ✅ Standard AWS services only (no preview access needed)

**Prerequisites:**
- ✅ Standard AWS account (no preview access needed)
- AWS Bedrock API access (Claude models enabled in your region)
- Node.js 18+ and AWS CDK v2
- AWS credentials configured (`aws configure` or IAM Identity Center)

**👉 Start here:** [bifrost-implementation/INSTALL.md](bifrost-implementation/INSTALL.md)

**Quick deploy:**
```bash
cd bifrost-implementation/cdk
npm install
ADMIN_EMAIL=you@example.com npx cdk deploy --all --require-approval never
```

---

## 🚨 These Demos Are INDEPENDENT

| Question | Answer |
|----------|--------|
| **Do I need all three demos?** | ❌ NO — pick ONE based on your use case |
| **Does Demo 2 or 3 need Demo 1's Gateway?** | ❌ NO — they go directly to Bedrock API |
| **Do they share infrastructure?** | ❌ NO — separate CloudFormation/CDK stacks |
| **Different prerequisites?** | ✅ YES — Demo 1 needs AgentCore preview access |
| **Which is production-ready?** | Demo #3 (Bifrost) is designed for production use |

---

## Quick Comparison

| Feature | Demo #1 (AgentCore) | Demo #2 (Direct Bedrock) | Demo #3 (Bifrost Gateway) |
|---------|---------------------|--------------------------|---------------------------|
| **Interface** | VS Code + Copilot | Browser chatbox | Browser chatbox |
| **RBAC Level** | Tool-level | Model-level | Model-level + quota |
| **Policy Engine** | Cedar policies | Lambda code | Bifrost virtual keys |
| **AWS Services** | AgentCore (preview) | API GW + Lambda | ECS + CloudFront + EFS |
| **Setup Time** | 15-20 min | 10-15 min | 20-25 min |
| **Cost Attribution** | Per IAM user | Per team | Per team (token-level) |
| **Preview Access?** | ⚠️ YES | ✅ NO | ✅ NO |
| **Production-Ready?** | Demo only | Demo only | ✅ Yes |
| **Observability** | Basic | CloudWatch | CloudWatch + Grafana |
| **Config persistence** | N/A | N/A | EFS + Secrets Manager |

---

## Common Questions

### "Which demo should I start with?"

**Start with Demo #3 (Bifrost)** if:
- You want a production-ready deployment
- You need token-level quota enforcement per team
- You want a full observability stack (CloudWatch + Grafana)
- You're building something you'll actually run in production

**Start with Demo #2** if:
- You want the quickest, simplest path to testing
- You don't need a production-grade gateway
- You want a minimal Lambda-based implementation

**Start with Demo #1** if:
- You have AgentCore preview access
- You want VS Code + GitHub Copilot integration
- You need fine-grained tool-level (not just model-level) permissions

### "What's the difference between Demo #2 and Demo #3?"

Both do team-based model access control, but at different scales:

| | Demo #2 | Demo #3 (Bifrost) |
|---|---------|-------------------|
| Gateway | Lambda proxy (100 lines) | Bifrost on ECS Fargate |
| HTTPS | API Gateway | CloudFront + internal ALB |
| Quota enforcement | API Gateway usage plans | Per-team daily token budgets |
| Config persistence | Stateless Lambda | EFS-backed SQLite |
| Observability | Basic CloudWatch | Dashboard + Grafana + alarms |
| Deploy tool | CloudFormation | CDK TypeScript |
| Production use | Demo only | Yes |

### "What if I don't have AgentCore access?"

Start with **Demo #2** or **Demo #3** — both use standard AWS services (API Gateway / ECS, Lambda, Bedrock) that are generally available. No preview access needed.

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
│   ├── ecommerce-mcp/
│   ├── products-mcp/
│   ├── orders-mcp/
│   └── jira-mcp/
│
└── vscode-config/
    └── mcp.json                 # VS Code MCP config template
```

### Demo #2 Contents (`team-rbac-bedrock-chat-demo/`)

```
team-rbac-bedrock-chat-demo/
├── README.md
├── DEPLOYMENT.md
├── chatbox.html                 # Browser chat UI
│
├── lambda/gateway-proxy/
│   └── lambda_function.py      # Direct Bedrock API calls
│
└── infrastructure/cloudformation/
    └── main-stack.yaml          # API Gateway, Lambda, IAM roles
```

### Demo #3 Contents (`bifrost-implementation/`)

```
bifrost-implementation/
├── INSTALL.md                   # Full installation guide (CDK + manual)
├── bifrost-config.json          # Bifrost config template (uses env vars)
├── task-def.json                # ECS task definition template (with placeholders)
│
├── cdk/                         # CDK TypeScript app — deploy everything from here
│   ├── bin/app.ts               # Entry point — reads env vars, wires stacks
│   ├── lib/
│   │   ├── vpc-stack.ts         # VPC, subnets, NAT gateways, security groups
│   │   ├── bifrost-stack.ts     # ECS Fargate, internal ALB, EFS, IAM roles
│   │   ├── cloudfront-stack.ts  # CloudFront VPC Origin, Cognito, S3 chatbox
│   │   ├── observability-stack.ts # CloudWatch dashboard, alarms, quota Lambda
│   │   └── grafana-stack.ts     # Amazon Managed Grafana + Prometheus (optional)
│   └── package.json
│
├── cloudformation/              # Manual deploy alternative (individual stacks)
│   ├── 01-vpc.yaml
│   ├── 02-ecs.yaml
│   ├── 03-cloudfront.yaml
│   └── 04-observability.yaml
│
├── chatbox/
│   └── chatbox.html             # Browser-based chat UI (uploaded to S3)
│
└── scripts/
    ├── deploy-bifrost.sh        # Full CloudFormation deploy script
    ├── update-chatbox-keys.sh   # Patch chatbox with live virtual keys
    └── quota-publisher/
        └── lambda_function.py   # Publishes token quota % to CloudWatch every 5 min
```

---

## Getting Started

### Demo #3 — Bifrost AI Gateway (Recommended for production)

```bash
# 1. Install CDK
npm install -g aws-cdk

# 2. Install dependencies
cd bifrost-implementation/cdk && npm install

# 3. Bootstrap CDK (first time only)
cdk bootstrap

# 4. Deploy everything
ADMIN_EMAIL=you@example.com npx cdk deploy --all --require-approval never
```

CDK will print your live URLs when complete:
- **Chat UI:** `https://xxxx.cloudfront.net/chat.html`
- **Admin UI:** `https://xxxx.cloudfront.net`
- **CloudWatch Dashboard:** link printed in outputs

**Full guide with manual step-by-step:** [bifrost-implementation/INSTALL.md](bifrost-implementation/INSTALL.md)

---

### Demo #1 — AgentCore Gateway + VS Code

```bash
cd gateway-url-ide-integration-demo/DemoMcpGateway/agentcore
agentcore deploy
```

**Full guide:** [gateway-url-ide-integration-demo/DEPLOYMENT.md](gateway-url-ide-integration-demo/DEPLOYMENT.md)

---

### Demo #2 — Browser Chat + Team RBAC

```bash
cd team-rbac-bedrock-chat-demo/infrastructure/cloudformation
aws cloudformation create-stack \
  --stack-name llm-gateway-demo \
  --template-body file://main-stack.yaml \
  --capabilities CAPABILITY_IAM
```

**Full guide:** [team-rbac-bedrock-chat-demo/DEPLOYMENT.md](team-rbac-bedrock-chat-demo/DEPLOYMENT.md)

---

## Architecture Diagrams

### Demo #1 Architecture (AgentCore Gateway)

```
┌─────────────────────────────────────────────────────────┐
│  Developer Workstation                                  │
│  VS Code + GitHub Copilot                               │
│  AWS Credentials: IAM User (tag: group=ReadOnly)        │
└────────────────┬────────────────────────────────────────┘
                 │ stdio + SigV4
                 ▼
     ┌───────────────────────────┐
     │   MCP Proxy (local)       │
     └───────────┬───────────────┘
                 │ HTTPS + SigV4
                 ▼
     ┌───────────────────────────────────┐
     │  AWS Bedrock AgentCore Gateway    │
     │  Cedar Policy Engine              │
     │  • Reads IAM user tags            │
     │  • Evaluates permit/deny          │
     └───────────┬───────────────────────┘
                 │
     ┌───────────┴──────┬──────┬──────┐
     ▼                  ▼      ▼      ▼
  Customers MCP   Products MCP  Orders MCP  Jira MCP
  (Lambda)        (Lambda)      (Lambda)    (Lambda)
```

### Demo #2 Architecture (Direct Bedrock)

```
Browser (chatbox.html)
  │  HTTPS + x-api-key
  ▼
API Gateway  →  Lambda Proxy  →  AWS Bedrock
               (team lookup,      (Claude models)
                model check)
```

### Demo #3 Architecture (Bifrost AI Gateway)

```
Internet
   │ HTTPS
   ▼
CloudFront (DDoS protection, TLS termination)
   │  VPC Origin — ALB is never publicly exposed
   │
   ├── /*          → Bifrost Admin UI  (ECS via internal ALB)
   ├── /v1/*       → Bifrost API       (ECS via internal ALB)
   ├── /chat.html  → S3 chatbox        (static HTML)
   └── /metrics*   → Blocked (403)
           │
           ▼
   ECS Fargate — private subnet
   Bifrost container
           │
           ├──→ AWS Bedrock (Claude via IAM role — no API keys)
           ├──→ CloudWatch Logs (/bifrost/container, /bifrost/access)
           └──→ EFS (config persistence across restarts)

Lambda (every 5 min):
   QuotaPublisher → CloudWatch metrics (QuotaUtilisationPct per team)

CloudWatch Namespace: Bifrost/Gateway
   RequestCount, TokensInput, TokensOutput,
   ModelAccessDenied, Errors, LatencySeconds,
   QuotaUtilisationPct, DailyTokensUsed

Optional: Amazon Managed Grafana → CloudWatch datasource → live dashboards
```

---

## Use Cases

### Demo #1: Tool-Level RBAC
- Enterprise developer productivity with governed AI coding assistants
- Junior devs: read-only tools; senior devs: full CRUD; admins: infra tools
- Every tool invocation logged with IAM principal for audit

### Demo #2: Simple Model-Level RBAC
- Quickest path to team-based model access control
- Team A: balanced (Haiku + Sonnet); Team B: cost-optimized (Haiku only)
- Monthly cost chargeback per team via CloudWatch logs

### Demo #3: Production AI Gateway
- Production-grade model access control with token budgets
- Daily quota enforcement — Team Alpha can't blow past 100K tokens/day
- Real-time observability: request rates, latency percentiles, quota gauges
- Gradual model rollout: promote teams from Haiku → Sonnet as needed
- Department-based access: Engineering gets Opus, Support gets Haiku only

---

## Cost Estimates

### Demo #1 (AgentCore Gateway)
| Service | Monthly Cost |
|---------|--------------|
| AgentCore Gateway (30K req) | ~$5 |
| Lambda MCPs | ~$1 |
| CloudWatch Logs | ~$0.50 |
| **Total** | **~$6.50/month** |

### Demo #2 (Direct Bedrock)
| Service | Monthly Cost |
|---------|--------------|
| API Gateway (300K req) | ~$3 |
| Lambda proxy | ~$1 |
| Bedrock (Haiku 4.5, 300K × 1K tokens) | ~$300 |
| **Total** | **~$304/month** |

### Demo #3 (Bifrost Gateway)
| Service | Monthly Cost |
|---------|--------------|
| ECS Fargate (1 vCPU, 3GB) | ~$35 |
| ALB | ~$20 |
| CloudFront (1M requests) | ~$1 |
| NAT Gateways (2×) | ~$65 |
| CloudWatch (metrics + logs) | ~$5 |
| Secrets Manager | ~$0.50 |
| **Total infrastructure** | **~$127/month** |
| Bedrock (Haiku, 1K req/day) | ~$30/month |
| *Optional: Managed Grafana* | *~$10/month* |

---

## Troubleshooting

### Demo #1
**"AgentCore CLI not found"** → `npm install -g @aws/agentcore-cli`

### Demo #2
**"403 from Lambda"** → Check IAM role has `bedrock:InvokeModel`

### Demo #3
**"Bifrost health check fails"** → `aws logs tail /bifrost/container --since 10m`
**"Chat returns 502"** → `curl https://YOUR_CF_URL/health` (should return `{"status":"ok"}`)
**"Virtual keys lost after restart"** → Re-configure via Admin UI (keys are in EFS now with CDK deploy)
**"Grafana shows No data"** → Metrics appear after first requests; quota metrics within 5 min

Full troubleshooting guides in each demo's DEPLOYMENT.md or INSTALL.md.

---

## Security Notes

All three demos follow AWS security best practices:
- **No hardcoded credentials** — secrets auto-generated and stored in Secrets Manager / SSM
- **IAM roles over API keys** — ECS task roles for Bedrock access (Demo #3)
- **No public ALB** — CloudFront VPC Origin keeps ALB internal (Demo #3)
- **No public ECS** — tasks run in private subnets with NAT egress (Demo #3)
- **Admin UI invite-only** — Cognito with no self-registration (Demo #3)
- **All resources tagged** — `auto-delete=no`, `project=bifrost-gateway`, `ManagedBy=CDK`

---

## Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Bifrost AI Gateway](https://github.com/maximhq/bifrost)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Cedar Policy Language](https://www.cedarpolicy.com/)
- [AWS CDK v2 Documentation](https://docs.aws.amazon.com/cdk/v2/guide/)
- [📄 Customer One-Pager](docs/customer-one-pager.md)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

We welcome:
- New MCP server examples (Demo #1)
- Additional Lambda proxy patterns (Demo #2)
- Bifrost configuration examples (Demo #3)
- Cedar policy examples
- Integration guides for other AI tools

---

## License

This library is licensed under the MIT-0 License. See [LICENSE](LICENSE).

---

**🎯 Remember:** These are **three independent demos**. Pick the one that matches your use case.

- **Tool-level RBAC for AI coding assistants?** → Demo #1
- **Quickest team-based model access control?** → Demo #2
- **Production-grade AI gateway with quotas and observability?** → Demo #3

**Happy building!** 🚀
