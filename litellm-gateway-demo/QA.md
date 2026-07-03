# Demo 3: LiteLLM Gateway — QA Document

## What Are We Building?

A **third demo** in this repo that shows the same team-based AI governance story as Demo 2, but using LiteLLM (an open-source AI gateway) instead of custom Lambda code.

**One sentence:** "Deploy LiteLLM on ECS, configure team budgets and model access in YAML, and show customers that governance doesn't require writing code."

---

## Why Are We Building This?

| Problem | How Demo 3 Solves It |
|---|---|
| Demo 2 requires writing custom Python to enforce RBAC | LiteLLM does it via configuration — no code |
| Demo 2 only logs cost (doesn't block over-budget) | LiteLLM blocks requests in real-time when budget is exceeded (HTTP 429) |
| Adding a new team in Demo 2 requires redeploying Lambda | LiteLLM lets you add teams via an API call — zero downtime |
| Demo 2 has no admin dashboard | LiteLLM ships with a web UI for spend visibility |
| Customers ask "what's the AWS-endorsed approach for multi-provider LLM gateways?" | LiteLLM has an official AWS reference architecture in the Solutions Library |

---

## Who Is This For?

- **TAMs** demoing to customers who ask: "We have 20 teams using Claude, GPT-4, and Bedrock — how do we govern that centrally?"
- **Customers** already evaluating LiteLLM and want to see it deployed properly on AWS
- **Platform engineering teams** building internal LLM gateways

---

## What Does the Demo Show?

### Demo Flow (5 steps, ~10 minutes live)

| Step | What Happens | What Customer Sees |
|---|---|---|
| 1 | Team Alpha calls claude-haiku | ✅ Success — response from Haiku |
| 2 | Team Alpha calls claude-sonnet | ✅ Success — Team Alpha has both |
| 3 | Team Beta calls claude-sonnet | ❌ HTTP 403 — "model not allowed" |
| 4 | Set Team Beta budget to $0.01, make 2 requests | ❌ HTTP 429 — "budget exceeded" (blocked before hitting Bedrock) |
| 5 | Open Admin UI, show spend dashboard | Dashboard shows per-team costs |

### The Key "Aha" Moments

1. **Same API, different access** — Both teams use the same endpoint (`/chat/completions`), but get different model access based on their virtual key
2. **Real blocking, not just logging** — When budget is exceeded, the request never reaches Bedrock. Compare to Demo 2 where we only log the denial.
3. **Add a team in 30 seconds** — No code change, no redeploy. Just a curl to `/team/new`.

---

## What Does It NOT Show?

| Not Included | Why |
|---|---|
| Multi-provider failover (Bedrock → OpenAI) | Keeps focus on governance, not routing. Mention it exists but don't demo it. |
| Full production EKS deployment | AWS reference architecture already covers that. We show Fargate for simplicity. |
| WAF / CloudFront / custom domain | Infrastructure hardening is out of scope for a 10-minute demo. |
| Comparison with Demo 1 (AgentCore) | Different problem. Demo 1 = tool-level RBAC for AI agents. Demo 3 = model-level budget governance. |

---

## Architecture

```
Client (curl / chatbox / any OpenAI SDK app)
    │
    │  POST /chat/completions
    │  Authorization: Bearer sk-team-alpha-key
    │
    ▼
┌────────────────────────────────────────┐
│  LiteLLM Proxy (ECS Fargate)           │
│                                        │
│  1. Validate virtual key               │
│  2. Check: is this team over budget?   │
│  3. Check: can this team use this model│
│  4. Route to Bedrock (translate format)│
│  5. Log spend asynchronously           │
└───────────┬────────────────────────────┘
            │
     ┌──────┴──────┐
     ▼             ▼
┌─────────┐  ┌──────────┐
│ Bedrock │  │ Redis    │ (rate limits + cache)
│ Claude  │  │ Postgres │ (keys, teams, spend)
└─────────┘  └──────────┘
```

---

## How Does It Relate to the Other Demos?

| | Demo 1 (AgentCore) | Demo 2 (Custom Lambda) | Demo 3 (LiteLLM) |
|---|---|---|---|
| **What it governs** | Which MCP tools a developer can invoke | Which Bedrock model a team can use | Which model + how much budget per team |
| **Policy engine** | Cedar (declarative) | Python code (imperative) | LiteLLM config + virtual keys |
| **Budget enforcement** | None | Logging only | Real-time blocking |
| **Interface** | VS Code / Copilot | Browser chatbox | Any OpenAI SDK client |
| **Admin experience** | Edit Cedar policy file | Redeploy Lambda | Web UI or API call |
| **AWS endorsement** | AgentCore (preview) | Standard services | Official reference architecture |
| **Deploy time** | ~15 min | ~10 min | ~5 min local / ~20 min AWS |

---

## Files We're Adding

```
litellm-gateway-demo/
├── README.md                              # What, why, architecture, quick start
├── DEPLOYMENT.md                          # Full deployment guide (local + AWS)
├── DEMO.md                                # Live demo script (what to show)
├── QA.md                                  # ← This document
├── .env.example                           # Template for AWS creds
├── config.yaml                            # LiteLLM proxy config (models, cache, router)
├── docker-compose.yml                     # Local: LiteLLM + Redis + PostgreSQL
├── scripts/
│   ├── setup-teams.sh                     # Creates teams + virtual keys via API
│   └── test-demo.sh                       # Automated 7-test validation
└── infrastructure/
    └── cloudformation/
        └── litellm-stack.yaml             # AWS: VPC + ECS + RDS + Redis + ALB
```

---

## Testing Criteria

### Must Pass (blocks merge)

| # | Test | Expected Result |
|---|---|---|
| 1 | `docker compose up -d` completes | All 3 containers healthy within 30s |
| 2 | `./scripts/setup-teams.sh` creates teams | Outputs 2 team IDs + 2 virtual keys |
| 3 | Team Alpha → claude-haiku | HTTP 200 with response |
| 4 | Team Alpha → claude-sonnet | HTTP 200 with response |
| 5 | Team Beta → claude-haiku | HTTP 200 with response |
| 6 | Team Beta → claude-sonnet | HTTP 403 (model not allowed) |
| 7 | Invalid key → any model | HTTP 401 (unauthorized) |
| 8 | Team Beta budget set to $0.01, then request | HTTP 429 (budget exceeded) |
| 9 | Admin UI loads at /ui | Login page renders |

### Nice to Have (doesn't block)

| # | Test | Expected Result |
|---|---|---|
| 10 | CloudFormation stack deploys | Stack in CREATE_COMPLETE |
| 11 | ECS task starts and passes health check | Task RUNNING |
| 12 | ALB endpoint responds to /health | 200 OK |

---

## Open Questions

| Question | Status |
|---|---|
| Should we include the chatbox.html UI pointing at LiteLLM? | Deferred — curl demos are sufficient for now |
| Should config.yaml reference Bedrock or use the ECS Task Role? | Both: local uses env vars, AWS uses task role |
| Pin LiteLLM container version or use `main-latest`? | Using `main-latest` for now; pin before customer handoff |
| Include the litellm-research.md in this demo folder? | It's in gateway-url-ide-integration-demo/ — move? leave? | 

---

## Definition of Done

- [ ] `docker compose up && ./scripts/setup-teams.sh && ./scripts/test-demo.sh` passes all 7 tests
- [ ] DEMO.md is clear enough for a TAM to run without prior LiteLLM knowledge
- [ ] CloudFormation deploys without manual steps (single `aws cloudformation deploy` command)
- [ ] No hardcoded secrets, account IDs, or internal references
- [ ] README explains when to use Demo 3 vs Demo 2 (decision matrix)
