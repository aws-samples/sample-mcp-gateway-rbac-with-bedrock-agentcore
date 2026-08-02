# Session Handoff — Bifrost AI Gateway Project
> Last updated: July 2026
> Written for: YOUR_ALIAS
> Purpose: Complete state snapshot so you (or Kiro) can resume with zero context loss after ~1 month away

---

## TL;DR — What Was Built

You built a **production-grade AI Gateway** on AWS using [Bifrost](https://github.com/maximhq/bifrost), deployed to your AWS account, and published as open-source code on GitHub. The repo contains three independent demos; this handoff covers Demo #3 (Bifrost) which is the main work done in this session.

---

## 1. AWS Account & Live Resources

| Item | Value |
|---|---|
| **AWS Account ID** | `YOUR_AWS_ACCOUNT_ID` |
| **Region** | `us-east-1` |
| **IAM Identity** | Isengard short-lived credentials (rotate every ~10 min) |

### Live CloudFormation Stacks (all CREATE_COMPLETE / UPDATE_COMPLETE)

| Stack Name | What It Does |
|---|---|
| `bifrost-gw-vpc` | VPC, private/public subnets, NAT gateways, security groups |
| `bifrost-gw-ecs` | ECS Fargate cluster + service, internal ALB, EFS filesystem |
| `bifrost-gw-cf` | CloudFront distribution, Cognito user pool, S3 chatbox bucket |
| `bifrost-gw-obs` | CloudWatch dashboard, alarms, SNS topic, quota publisher Lambda |

### Live Endpoints

| Resource | URL / ID |
|---|---|
| **Admin UI** | `https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net` |
| **Chat UI** | `https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net/chat.html` |
| **Health check** | `https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net/health` → `{"status":"ok"}` |
| **CloudFront dist** | `YOUR_CF_DISTRIBUTION_ID` |
| **ECS Cluster** | `bifrost-cluster` |
| **ECS Service** | `bifrost-service` |
| **Internal ALB** | `bifrost-alb` (internal, not publicly accessible) |
| **S3 chatbox bucket** | `bifrost-chatbox-YOUR_AWS_ACCOUNT_ID` |
| **S3 artifacts bucket** | `bifrost-artifacts-YOUR_AWS_ACCOUNT_ID-us-east-1` |

### Grafana

| Resource | Value |
|---|---|
| **Grafana workspace** | `YOUR_GRAFANA_WORKSPACE_ID` |
| **Grafana URL** | `https://YOUR_GRAFANA_WORKSPACE_ID.grafana-workspace.us-east-1.amazonaws.com` |
| **Dashboard** | `bifrost-gateway-main` (Bifrost AI Gateway Team Observability) |
| **Dashboard URL** | `https://YOUR_GRAFANA_WORKSPACE_ID.grafana-workspace.us-east-1.amazonaws.com/d/bifrost-gateway-main/bifrost-ai-gateway-team-observability` |
| **SSO user (Grafana admin)** | `YOUR_SSO_USERNAME` (ID: `YOUR_SSO_USER_ID`) |
| **CloudWatch datasource** | UID `YOUR_DATASOURCE_UID`, name `CloudWatch-Bifrost` |
| **AMP workspace** | `YOUR_AMP_WORKSPACE_ID` (created, not yet wired to ADOT) |

### SSM Parameters (in account)

| Path | Contents |
|---|---|
| `/bifrost/encryption-key` | Bifrost 32-char config encryption key |
| `/bifrost/virtual-keys/team-alpha` | Team Alpha virtual key value (SSM SecureString) |
| `/bifrost/virtual-keys/team-beta` | Team Beta virtual key value (SSM SecureString) |
| `/bifrost/live-keys/team-alpha` | `sk-bf-XXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX` |
| `/bifrost/live-keys/team-beta` | `sk-bf-YYYYY-YYYY-YYYY-YYYY-YYYYYYYYYYYY` |
| `/bifrost/api-endpoint` | CloudFront URL |

### CloudWatch

| Resource | Name |
|---|---|
| Dashboard | `bifrost-ai-gateway` |
| Metrics namespace | `Bifrost/Gateway` |
| Log groups | `/bifrost/container`, `/bifrost/access`, `/bifrost/audit`, `/bifrost/metrics` |
| Alarms | `bifrost-team-alpha-quota-80pct`, `bifrost-team-alpha-quota-100pct`, `bifrost-team-beta-quota-100pct`, `bifrost-high-error-rate` |
| Quota Lambda | `bifrost-quota-publisher` (runs every 5 min, publishes `QuotaUtilisationPct`) |

---

## 2. GitHub Repository

| Item | Value |
|---|---|
| **Repo** | `https://github.com/aws-samples/sample-mcp-gateway-rbac-with-bedrock-agentcore` |
| **Your fork** | `https://github.com/YOUR_GITHUB_USER/sample-mcp-gateway-rbac-with-bedrock-agentcore` |
| **Write access** | Yes — YOUR_ALIAS has write access to aws-samples repo directly |

### Branch State

| Branch | Status | Description |
|---|---|---|
| `main` | `b891be9` (behind — needs PR #14 merged) | Original + PR #11 merged (Bifrost basics) |
| `Bifrost-implementation` | `953255a` ✅ latest | All Bifrost work including CDK + README |
| `merge-bifrost-final` | `8760b19` | Squash of all Bifrost work, ready for merge to main |

### Open PRs

| PR | Title | Status |
|---|---|---|
| **#14** | Add Demo 3: Bifrost AI Gateway — CDK TypeScript, self-deployable | **OPEN — needs merge** |

> **Action needed when you return:** Merge PR #14 into main. URL: `https://github.com/aws-samples/sample-mcp-gateway-rbac-with-bedrock-agentcore/pull/14`

### Key Files

| File | Purpose |
|---|---|
| `bifrost-implementation/INSTALL.md` | Full customer installation guide (CDK + manual) |
| `bifrost-implementation/cdk/` | CDK TypeScript app — 5 stacks |
| `bifrost-implementation/cloudformation/` | Manual CloudFormation alternative (4 templates) |
| `bifrost-implementation/bifrost-config.json` | Bifrost config template (env var references, no secrets) |
| `bifrost-implementation/task-def.json` | ECS task def TEMPLATE (all account IDs are placeholders) |
| `bifrost-implementation/scripts/deploy-bifrost.sh` | Full deploy script (auto-generates key) |
| `bifrost-implementation/scripts/update-chatbox-keys.sh` | Patches chatbox.html with live virtual keys |
| `bifrost-implementation/scripts/.bifrost-key` | YOUR local encryption key (gitignored — DO NOT commit) |
| `bifrost-implementation/scripts/quota-publisher/lambda_function.py` | Quota publisher Lambda source |
| `README.md` | Updated — documents all 3 demos side-by-side |

---

## 3. Architecture Overview

```
Internet (HTTPS)
      │
      ▼
CloudFront (YOUR_CF_DISTRIBUTION_ID)
YOUR_CLOUDFRONT_DOMAIN.cloudfront.net
      │  VPC Origin
      │
      ├── /* ──────────────► Bifrost Admin UI  (internal ALB → ECS)
      ├── /v1/* ───────────► Bifrost API       (internal ALB → ECS)
      ├── /chat.html ──────► S3 chatbox bucket (static HTML)
      └── /metrics* ───────► Blocked 403

ECS Fargate — bifrost-service (private subnet, 1 task, 1 vCPU / 3 GB)
  Container: maximhq/bifrost:latest
  Port: 8080
  Config store: EFS (bifrost-data volume, /app/data)
  Encryption key: Secrets Manager /bifrost/encryption-key
      │
      ├──► AWS Bedrock (via IAM task role — no API keys)
      │    Models: us.anthropic.claude-haiku-4-5, claude-sonnet-4-5
      └──► CloudWatch Logs (/bifrost/container, /bifrost/access)

Lambda: bifrost-quota-publisher
  Runs every 5 min → CloudWatch metric QuotaUtilisationPct per team

Amazon Managed Grafana (YOUR_GRAFANA_WORKSPACE_ID)
  Datasource: CloudWatch-Bifrost (YOUR_DATASOURCE_UID)
  Dashboard: bifrost-gateway-main
```

---

## 4. Known Issues / Incomplete Items

### 4a. Bifrost Virtual Keys Reset on Container Restart
- **Problem:** Bifrost stores virtual keys in-memory/SQLite. When ECS replaces the task container, all configured keys are lost.
- **Partial fix:** EFS is mounted at `/app/data` which *should* persist SQLite across restarts. This was the goal of EFS integration.
- **Status:** EFS mount is configured in CDK and CloudFormation. Whether the SQLite actually persists needs validation on next resume.
- **Workaround today:** After every restart, re-configure via Admin UI or use SSM values in `/bifrost/live-keys/`.
- **Long-term fix option:** Use `bifrost-config.json` approach with virtual key values read from SSM env vars at startup.

### 4b. ADOT Sidecar Not Running
- **Problem:** The ADOT (AWS Distro for OpenTelemetry) sidecar container was removed from the running task to prevent OOM kills (task definition rev 6/7 had OOM issues with 1024 CPU / 3072 MB).
- **Impact:** Bifrost metrics are NOT flowing to Amazon Managed Prometheus (AMP). CloudWatch gets metrics via the quota publisher Lambda, but native Bifrost Prometheus metrics are not scraped.
- **Fix when ready:** Either increase task size to 2048 CPU / 4096 MB and re-add ADOT sidecar, OR just rely on CloudWatch (which already works).

### 4c. PR #14 Not Merged to Main
- `main` branch is at `b891be9` (PR #11 merge)
- `Bifrost-implementation` and `merge-bifrost-final` branches have all the new CDK + INSTALL.md work
- PR #14 needs to be merged: `https://github.com/aws-samples/sample-mcp-gateway-rbac-with-bedrock-agentcore/pull/14`

### 4d. CDK Has Not Been Tested Fresh (Synthesize-Only)
- The CDK TypeScript app was written and reviewed but NOT synthesized/deployed from scratch via `cdk deploy`.
- The live account was deployed via CloudFormation templates, not CDK.
- There may be TypeScript compilation errors in the CDK app (the editor shows "Cannot find module 'aws-cdk-lib'" which is a missing `npm install` issue, not a real error).
- **Test before claiming CDK works:** `cd bifrost-implementation/cdk && npm install && npx cdk synth`

### 4e. Grafana Panels May Show "No Data"
- Panels depend on Bifrost generating traffic and writing to `/bifrost/access` log group
- If Bifrost was restarted and virtual keys were lost, no new traffic = no metrics
- Fix: Re-configure virtual keys via Admin UI, then send test traffic

---

## 5. Resumption Checklist (What to Do When You Return)

When you come back in ~1 month, give Kiro this file and say:
> "Resume the Bifrost project. Use SESSION_HANDOFF.md. Validate everything is running, check for GitHub changes, and update me."

Kiro should then do the following (in order):

### Step 1 — Get fresh AWS credentials
Ask user to paste Isengard credentials. Credentials expire every ~10 minutes.

### Step 2 — Validate live AWS resources

```bash
# Check ECS service is running
aws ecs describe-services --cluster bifrost-cluster --services bifrost-service \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}' --output table

# Check health endpoint
curl -s https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net/health

# Check CloudWatch has recent metrics (last 24h)
aws cloudwatch get-metric-statistics \
  --namespace Bifrost/Gateway --metric-name RequestCount \
  --start-time $(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 --statistics Sum --output table

# Check CloudFormation stacks are healthy
aws cloudformation describe-stacks --query \
  'Stacks[?contains(StackName,`bifrost`)].{Name:StackName,Status:StackStatus}' --output table
```

### Step 3 — Check GitHub for changes since last session

```bash
cd /path/to/your/local/repo
git fetch origin
git -P log --oneline origin/main -10
# Check if PR #14 was merged
```

### Step 4 — Merge PR #14 if still open
PR URL: `https://github.com/aws-samples/sample-mcp-gateway-rbac-with-bedrock-agentcore/pull/14`

### Step 5 — Test CDK synth
```bash
cd bifrost-implementation/cdk
npm install
npx cdk synth --all 2>&1 | tail -20
```

### Step 6 — Validate Bifrost virtual keys still work
```bash
# Get live key from SSM
ALPHA_KEY=$(aws ssm get-parameter --name /bifrost/live-keys/team-alpha \
  --query Parameter.Value --output text)

# Send test request
curl -s https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net/v1/chat/completions \
  -H "Authorization: Bearer $ALPHA_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"us.anthropic.claude-haiku-4-5-20251001-v1:0","messages":[{"role":"user","content":"ping"}],"max_tokens":10}'
```

If this returns an error about unknown virtual key → keys were lost on restart. Re-configure:
1. Open Admin UI: `https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net`
2. Add Bedrock provider (IAM Role, region us-east-1)
3. Create virtual key `team-alpha` (Haiku + Sonnet, 100K tokens/day)
4. Create virtual key `team-beta` (Haiku only, 50K tokens/day)
5. Copy new key values → store in SSM:
   ```bash
   aws ssm put-parameter --name /bifrost/live-keys/team-alpha --value sk-bf-NEW-VALUE --type String --overwrite
   aws ssm put-parameter --name /bifrost/live-keys/team-beta  --value sk-bf-NEW-VALUE --type String --overwrite
   ```

### Step 7 — Validate Grafana dashboard
1. Open `https://YOUR_GRAFANA_WORKSPACE_ID.grafana-workspace.us-east-1.amazonaws.com/d/bifrost-gateway-main`
2. Check panels show data (may need to send traffic first — see Step 6)

---

## 6. Next Steps / Backlog (Nice to Have)

These were planned but not completed. Pick up any of these on resumption:

| Priority | Item | Notes |
|---|---|---|
| HIGH | Merge PR #14 to main | Blocked on maintainer approval or your direct merge |
| HIGH | Test CDK fresh deploy | `cdk synth` + optionally `cdk deploy` to a clean account |
| MED | Fix ADOT sidecar OOM | Increase task to 2048 CPU / 4096 MB, re-add ADOT, wire to AMP |
| MED | Validate EFS persistence | Confirm SQLite survives ECS task restart (EFS mount is configured) |
| MED | Wire AMP to Grafana | Add AMP datasource in Grafana (`YOUR_AMP_WORKSPACE_ID`) |
| LOW | `update-chatbox-keys.sh` test | Verify the script correctly patches and uploads chat.html |
| LOW | Pin Bifrost version | Change `maximhq/bifrost:latest` to a specific tag in CDK |
| LOW | Add WAF to CloudFront | Rate limiting on `/v1/*` endpoint |

---

## 7. Local Workspace State

| Item | Location |
|---|---|
| **Git repo** | `/path/to/your/local/repo` |
| **Active branch** | `Bifrost-implementation` |
| **Encryption key file** | `bifrost-implementation/scripts/.bifrost-key` (gitignored, local only) |
| **CDK node_modules** | NOT installed — run `npm install` in `bifrost-implementation/cdk/` before CDK commands |

---

## 8. Cost & Resource Cleanup

**Estimated monthly burn while idle:**
- NAT Gateways (2×): ~$65/month (largest cost, always running)
- ECS Fargate (1 task): ~$35/month
- ALB: ~$20/month
- CloudFront, CloudWatch, Secrets Manager, Lambda: ~$7/month
- **Total idle burn: ~$127/month**

**If you want to stop the burn while away:**
```bash
# Scale ECS to 0 (stops compute cost, keeps everything else)
aws ecs update-service --cluster bifrost-cluster --service bifrost-service --desired-count 0

# To resume:
aws ecs update-service --cluster bifrost-cluster --service bifrost-service --desired-count 1
```

**Full teardown (if abandoning the deployment):**
```bash
aws cloudformation delete-stack --stack-name bifrost-gw-obs --region us-east-1
aws cloudformation delete-stack --stack-name bifrost-gw-cf  --region us-east-1
# Wait for each to complete before deleting the next
aws cloudformation delete-stack --stack-name bifrost-gw-ecs --region us-east-1
aws cloudformation delete-stack --stack-name bifrost-gw-vpc --region us-east-1
```

---

## 9. Credentials & Access

| Resource | How to Access |
|---|---|
| **AWS** | Isengard short-lived credentials (paste into terminal, valid ~10 min) |
| **Admin UI** | `https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net` (Cognito login with your email) |
| **Grafana** | `https://YOUR_GRAFANA_WORKSPACE_ID.grafana-workspace.us-east-1.amazonaws.com` (SSO: YOUR_SSO_USERNAME) |
| **GitHub** | Personal Access Token — stored in your local git remote config. If pushing fails after 1 month, regenerate at: github.com → Settings → Developer settings → Personal access tokens → Tokens (classic) |

> ⚠️ The GitHub token above may expire. If pushing fails, regenerate at github.com → Settings → Developer settings → Personal access tokens.

---

## 10. Session Summary (What Was Done This Session)

1. **Reviewed Demo 2 (team-rbac)** and fixed deprecated Claude model IDs, IAM ARN patterns
2. **Built full Bifrost implementation** from scratch:
   - 4 CloudFormation stacks deployed to AWS
   - CloudFront distribution with VPC Origin (ALB never exposed)
   - ECS Fargate running Bifrost container with EFS persistence
   - Virtual keys for Team Alpha (Haiku+Sonnet) and Team Beta (Haiku only)
   - CloudWatch dashboard with quota gauges, request metrics, latency percentiles
3. **Added Amazon Managed Grafana** with CloudWatch datasource and Bifrost dashboard
4. **Built CDK TypeScript app** (5 stacks) for customer self-deployment
5. **Wrote INSTALL.md** — full guide with CDK quick-start + manual step-by-step alternative
6. **Security sweep** — gitignored `.bifrost-key`, replaced all hardcoded account IDs in `task-def.json` with documented placeholders
7. **Updated README** — documented all 3 demos side-by-side
8. **Tagged all 28+ resources** with `auto-delete=no`
9. **Pushed all work to GitHub** on `Bifrost-implementation` branch, opened **PR #14** for main

---

*This document is committed to the repo at `SESSION_HANDOFF.md` for persistence.*
