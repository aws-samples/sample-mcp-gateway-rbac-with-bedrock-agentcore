# Demo 3: LiteLLM Gateway — Multi-Provider AI Gateway with Team Budgets

> **Deploy LiteLLM on ECS Fargate with Bedrock, virtual keys, and real-time budget enforcement**

## What This Demo Shows

The same team-based governance as Demo 2 — but without writing any custom Lambda code. LiteLLM handles it all via configuration:

| Capability | Demo 2 (Custom Lambda) | Demo 3 (LiteLLM) |
|---|---|---|
| Team → model access control | Custom Python code | `config.yaml` |
| Budget enforcement | CloudWatch logs only | Real-time blocking (HTTP 429) |
| Cost tracking | `print(json.dumps(...))` | Built-in dashboard |
| Admin UI | None | LiteLLM web UI |
| Add a new team | Redeploy Lambda | API call or UI click |
| Multi-provider fallback | Not supported | Built-in router |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Clients (chatbox, IDE, API consumers)                  │
└─────────────────┬───────────────────────────────────────┘
                  │ HTTPS (OpenAI-compatible API)
                  ▼
      ┌───────────────────────────┐
      │  Application Load Balancer │
      │  (TLS via ACM)            │
      └───────────┬───────────────┘
                  │
      ┌───────────┴───────────────────────────┐
      │  ECS Fargate                           │
      │  ┌─────────────────────────────────┐  │
      │  │  LiteLLM Proxy Container         │  │
      │  │  • Virtual key validation        │  │
      │  │  • Budget enforcement (real-time)│  │
      │  │  • Model routing + fallback      │  │
      │  │  • Cost tracking per team        │  │
      │  └─────────────────────────────────┘  │
      └───────────┬────────────┬──────────────┘
                  │            │
          ┌───────┘            └────────┐
          ▼                             ▼
    ┌──────────────┐            ┌──────────────┐
    │ AWS Bedrock  │            │ ElastiCache  │
    │ Claude Haiku │            │ (Redis)      │
    │ Claude Sonnet│            │ Rate limits  │
    │ Claude Opus  │            │ Caching      │
    └──────────────┘            └──────────────┘
                                        │
                                ┌───────┘
                                ▼
                        ┌──────────────┐
                        │ Amazon RDS   │
                        │ (PostgreSQL) │
                        │ Keys, spend, │
                        │ team config  │
                        └──────────────┘
```

## ⏱️ Deploy Time

- **Local (docker-compose):** ~5 minutes
- **AWS (ECS Fargate):** ~20 minutes

## Prerequisites

- Docker + Docker Compose (for local testing)
- AWS CLI configured with admin credentials
- AWS account with Bedrock model access enabled
- Python 3.11+ (for helper scripts)

## Quick Start — Local

```bash
cd litellm-gateway-demo

# 1. Set your AWS credentials (LiteLLM uses these to call Bedrock)
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1

# 2. Start LiteLLM + Redis + PostgreSQL
docker compose up -d

# 3. Create teams and virtual keys
./scripts/setup-teams.sh

# 4. Test it
curl http://localhost:4000/chat/completions \
  -H "Authorization: Bearer sk-team-alpha-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-haiku",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# 5. Open Admin UI
open http://localhost:4000/ui
```

## Quick Start — AWS (ECS Fargate)

See [DEPLOYMENT.md](DEPLOYMENT.md) for full instructions.

```bash
# Deploy infrastructure + LiteLLM container
./scripts/deploy-aws.sh us-east-1
```

## Demo Script

See [DEMO.md](DEMO.md) for the live demo walkthrough:

1. Show Team Alpha can use Haiku + Sonnet ✅
2. Show Team Beta can only use Haiku ✅
3. Show Team Beta hitting budget limit → HTTP 429 ❌
4. Show Admin UI with per-team spend dashboard
5. Show adding a new team in 30 seconds (no redeploy)

## Configuration

All model routing and team policies are in `config.yaml`:

```yaml
model_list:
  - model_name: claude-haiku
    litellm_params:
      model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0

  - model_name: claude-sonnet
    litellm_params:
      model: bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

Teams and budgets are managed via API — see `scripts/setup-teams.sh`.

## Cost Estimate

| Component | Monthly Cost |
|---|---|
| ECS Fargate (1 vCPU, 2GB) | ~$35 |
| RDS PostgreSQL (db.t4g.micro) | ~$15 |
| ElastiCache Redis (cache.t4g.micro) | ~$12 |
| ALB | ~$20 |
| Bedrock (model inference) | Usage-based |
| **Infrastructure total** | **~$82/month** |

## When to Use This vs Demo 2

| Use Demo 2 (Custom Lambda) when... | Use Demo 3 (LiteLLM) when... |
|---|---|
| Single provider (Bedrock only) | Multiple providers (Bedrock + OpenAI + Vertex) |
| Bursty/low traffic | Steady production traffic |
| Want zero infrastructure | Want real budget enforcement |
| Simple 2-team setup | 10+ teams with different policies |
| Cost-optimized ($7/mo) | Feature-rich ($82/mo) |

## Resources

- [LiteLLM Documentation](https://docs.litellm.ai/)
- [AWS Reference Architecture](https://docs.aws.amazon.com/solutions/multi-provider-generative-ai-gateway-on-aws/)
- [LiteLLM Bedrock Provider](https://docs.litellm.ai/docs/providers/bedrock)
