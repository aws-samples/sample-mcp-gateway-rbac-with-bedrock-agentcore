# LiteLLM Gateway — Demo Script

## Overview

This demo shows enterprise LLM governance using LiteLLM as a managed gateway:
- **Team-based model access** (same story as Demo 2, zero custom code)
- **Real-time budget enforcement** (LiteLLM blocks at threshold, not just logs)
- **Admin dashboard** (non-technical ops can manage teams)

**Setup time:** 5 minutes (local) | 20 minutes (AWS)

---

## Before the Demo

```bash
cd litellm-gateway-demo

# Start services
docker compose up -d

# Setup teams (wait ~10s for LiteLLM to initialize)
chmod +x scripts/setup-teams.sh
./scripts/setup-teams.sh

# Note the keys from the output — you'll need them
```

---

## Demo Part 1: Team Model Access Control

### Team Alpha — Allowed Models (Haiku + Sonnet)

```bash
# ✅ Team Alpha can use Haiku
curl http://localhost:4000/chat/completions \
  -H "Authorization: Bearer <TEAM_ALPHA_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-haiku", "messages": [{"role": "user", "content": "What is cloud computing in one sentence?"}]}'

# ✅ Team Alpha can use Sonnet
curl http://localhost:4000/chat/completions \
  -H "Authorization: Bearer <TEAM_ALPHA_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet", "messages": [{"role": "user", "content": "Explain serverless architecture"}]}'
```

### Team Beta — Restricted to Haiku Only

```bash
# ✅ Team Beta can use Haiku
curl http://localhost:4000/chat/completions \
  -H "Authorization: Bearer <TEAM_BETA_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-haiku", "messages": [{"role": "user", "content": "Hello!"}]}'

# ❌ Team Beta DENIED on Sonnet
curl http://localhost:4000/chat/completions \
  -H "Authorization: Bearer <TEAM_BETA_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet", "messages": [{"role": "user", "content": "Hello!"}]}'

# Expected: 403 with "model not allowed for team"
```

**Key point:** Same API format, same endpoint — just different keys get different access.

---

## Demo Part 2: Budget Enforcement

### Show Current Spend

```bash
# Check Team Beta's remaining budget
curl http://localhost:4000/team/info?team_id=<TEAM_BETA_ID> \
  -H "Authorization: Bearer <MASTER_KEY>"
```

### Burn Through Budget (for demo)

To show budget blocking, temporarily set a very low budget:

```bash
# Set Team Beta budget to $0.01 (will hit after 1-2 requests)
curl -X POST http://localhost:4000/team/update \
  -H "Authorization: Bearer <MASTER_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"team_id": "<TEAM_BETA_ID>", "max_budget": 0.01}'

# Make a request — might succeed
curl http://localhost:4000/chat/completions \
  -H "Authorization: Bearer <TEAM_BETA_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-haiku", "messages": [{"role": "user", "content": "Tell me a joke"}]}'

# Make another — should get 429 BudgetExceededError
curl http://localhost:4000/chat/completions \
  -H "Authorization: Bearer <TEAM_BETA_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-haiku", "messages": [{"role": "user", "content": "Another joke please"}]}'

# Expected: HTTP 429 — "Budget has been exceeded! ..."
```

**Key point:** This is REAL blocking. The request never reaches Bedrock. Compare to Demo 2 where we only log denials.

---

## Demo Part 3: Admin Dashboard

Open: http://localhost:4000/ui

Login with the master key.

**Show:**
1. **Usage tab** — spend by team, by model, by day
2. **Teams tab** — team-alpha has 2 models, team-beta has 1
3. **Keys tab** — virtual keys with their budgets and usage
4. **Create a new team** — takes 30 seconds, no code deployment

---

## Demo Part 4: Adding a New Team (Live)

```bash
# Create Team Gamma with Opus access and $1000 budget
curl -X POST http://localhost:4000/team/new \
  -H "Authorization: Bearer <MASTER_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "team_alias": "team-gamma",
    "models": ["claude-haiku", "claude-sonnet", "claude-opus"],
    "max_budget": 1000.00,
    "budget_duration": "1mo"
  }'

# Generate their key
curl -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer <MASTER_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"team_id": "<NEW_TEAM_ID>", "key_alias": "team-gamma-key"}'

# Test it immediately — no redeploy needed
curl http://localhost:4000/chat/completions \
  -H "Authorization: Bearer <NEW_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-opus", "messages": [{"role": "user", "content": "Hello from Team Gamma!"}]}'
```

**Key point:** Zero downtime, zero code changes, zero redeployment. Config-driven governance.

---

## Summary Table

| Action | Demo 2 (Custom Lambda) | Demo 3 (LiteLLM) |
|---|---|---|
| Team Alpha uses Sonnet | ✅ (custom code) | ✅ (config) |
| Team Beta denied Sonnet | ❌ 403 (custom code) | ❌ 403 (built-in) |
| Budget exceeded | Logged only | **Actually blocked (429)** |
| Add new team | Redeploy Lambda | API call (30 sec) |
| View spend by team | CloudWatch query | Admin UI dashboard |
| Switch model provider | Rewrite Lambda code | Edit config.yaml |

---

## Talking Points

1. **"Zero code governance"** — All RBAC is configuration, not application logic
2. **"Real budget enforcement"** — Pre-call check, not post-hoc alerting
3. **"AWS-endorsed"** — Official reference architecture in AWS Solutions Library
4. **"OpenAI-compatible"** — Any app using the OpenAI SDK works without changes
5. **"Add teams without deploying"** — Platform team manages access, dev teams just use their key

---

## Cleanup

```bash
docker compose down -v  # Removes containers + data volumes
```
