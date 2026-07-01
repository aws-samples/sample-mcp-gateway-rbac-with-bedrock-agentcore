# Bifrost AI Gateway — Setup Guide

## Architecture Overview

```
Internet
   │
   ▼
CloudFront (HTTPS, WAF, DDoS protection)
   │ VPC Origin — ALB never exposed to internet
   │
   ├──  /* ──────────────────► S3 (chatbox.html static UI)
   ├──  /v1/* ───────────────► Internal ALB → ECS (Bifrost API)
   ├──  /ui* ────────────────► Internal ALB → ECS (Bifrost Admin UI)
   │                           └── Protected by Cognito login
   └──  /metrics* ──────────► Blocked (403)

ECS Fargate Task (private subnet):
  ├── Container: maximhq/bifrost  (port 8080)
  │     Config persisted on EFS (encrypted)
  │     IAM role → Bedrock (no access keys)
  └── Container: ADOT Collector  (sidecar)
        Scrapes Bifrost Prometheus /metrics
        Exports → CloudWatch EMF (Bifrost/Gateway namespace)
        Exports → X-Ray (traces)

CloudWatch Dashboard: "bifrost-ai-gateway"
  Per-team token usage, quota bars, latency, errors, model denials
```

---

## One-Command Deployment

```bash
cd bifrost-implementation/scripts

chmod +x deploy-bifrost.sh

./deploy-bifrost.sh \
  --admin-email  you@example.com \
  --alarm-email  ops@example.com \
  --region       us-east-1
```

Deployment takes ~15 minutes (VPC + ECS + CloudFront).

---

## Post-Deploy: Configure Bifrost via Admin UI

### 1. Get your Admin UI credentials

Check your email (`admin@example.com`) for the Cognito invitation.
The subject is **"Bifrost Gateway Admin Access"**.

**Sign in at:**
```
https://<your-cloudfront-domain>/ui
```

You'll be redirected to the Cognito hosted login page.
Use the username/temporary password from the email.

### 2. Add Admin Users (AWS Console only)

Only people added to the Cognito User Pool can access the Admin UI.
No self-registration — admin-only creation enforces the "AWS console access = UI access" policy.

```bash
# Add a new admin user via CLI
aws cognito-idp admin-create-user \
  --user-pool-id <COGNITO_POOL_ID> \
  --username newuser@example.com \
  --user-attributes Name=email,Value=newuser@example.com Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL \
  --region us-east-1
```

Or via AWS Console:
1. Go to **Cognito → User Pools → bifrost-admin-pool**
2. Click **Create user**
3. Enter email, check "Send an invitation"
4. The user gets an email with a temporary password

### 3. Configure AWS Bedrock Provider

In the Bifrost Admin UI (`/ui`):

1. **Providers → Add Provider**
2. Select **AWS Bedrock**
3. Auth method: **IAM Role** (the ECS task role is pre-configured — no keys needed)
4. Region: `us-east-1`
5. Save

### 4. Create Virtual Keys for Each Team

#### Team Alpha (Haiku + Sonnet access)

1. **Virtual Keys → New Virtual Key**
2. Name: `team-alpha`
3. Provider: `bedrock`
4. Allowed models: `claude-haiku-4-5*`, `claude-sonnet-4-5*`
5. Daily token budget: `100000`
6. Monthly token budget: `2000000`
7. Save → **Copy the generated key**

#### Team Beta (Haiku only)

1. **Virtual Keys → New Virtual Key**
2. Name: `team-beta`
3. Provider: `bedrock`
4. Allowed models: `claude-haiku-4-5*` only
5. Daily token budget: `50000`
6. Monthly token budget: `1000000`
7. Save → **Copy the generated key**

### 5. Activate Keys in chatbox.html

Run from `bifrost-implementation/scripts/`:

```bash
./update-chatbox-keys.sh \
  bfk_alpha_xxxxxxxxxxxxxxxxxxxx \
  bfk_beta_xxxxxxxxxxxxxxxxxxxx
```

This patches and uploads `chatbox.html` to S3, then invalidates CloudFront.

---

## Observability: CloudWatch Dashboard

Open the dashboard:
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=bifrost-ai-gateway
```

### What You'll See

| Widget | Metric | Dimension |
|--------|--------|-----------|
| Total Requests Today | `RequestCount` (Sum) | `team` |
| Total Tokens Today | `TokensInput + TokensOutput` (Sum) | `team` |
| Quota Utilisation % | `QuotaUtilisationPct` (Max) | `team` |
| Requests/min by team | `RequestCount` (Sum/60s) | `team` |
| Token consumption | `TokensInput/Output` (stacked) | `team` |
| Error rate | `Errors` | — |
| Model denials | `ModelAccessDenied` | — |
| p50/p95/p99 latency | `LatencySeconds` | — |
| Alarm status | All 5 alarms | — |

### How OTEL Data Flows

```
Bifrost container
   │ exposes /metrics (Prometheus format)
   │ emits structured JSON logs → /bifrost/access
   ▼
ADOT Collector sidecar
   │ scrapes /metrics every 15s
   │ renames labels: virtual_key→team, provider→llm_provider
   │ filters out Go runtime noise
   ▼
CloudWatch EMF
   └── Namespace: Bifrost/Gateway
       Dimensions: team, model, llm_provider

CloudWatch Logs → Metric Filters
   └── /bifrost/access (JSON) → extract TokensInput, TokensOutput, Errors, Latency

EventBridge → Lambda (every 5 min)
   └── Reads today's token sums → computes QuotaUtilisationPct → publishes to CW
```

### Quota Alerts

| Alarm | Threshold | Action |
|-------|-----------|--------|
| `bifrost-team-alpha-quota-80pct` | Alpha reaches 80% | SNS email |
| `bifrost-team-alpha-quota-100pct` | Alpha exhausted | SNS email |
| `bifrost-team-beta-quota-100pct` | Beta exhausted | SNS email |
| `bifrost-high-error-rate` | >10 errors in 5 min | SNS email |
| `bifrost-high-latency` | p99 > 10s for 15 min | SNS email |

---

## Testing

### Test 1: Model access control

```bash
# Get your CloudFront domain
CF_DOMAIN=$(aws cloudformation describe-stacks \
  --stack-name bifrost-gw-cf --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDomainName'].OutputValue" \
  --output text)

# Team Alpha → Haiku (should succeed)
curl -s -X POST "https://${CF_DOMAIN}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <alpha-virtual-key>" \
  -d '{"model":"us.anthropic.claude-haiku-4-5-20251001-v1:0","messages":[{"role":"user","content":"Hello in 3 words"}],"max_tokens":20}' \
  | python3 -m json.tool

# Team Beta → Sonnet (should return 403)
curl -s -X POST "https://${CF_DOMAIN}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <beta-virtual-key>" \
  -d '{"model":"us.anthropic.claude-sonnet-4-5-20250929-v1:0","messages":[{"role":"user","content":"Hello"}],"max_tokens":20}'
```

### Test 2: Health check

```bash
curl -s "https://${CF_DOMAIN}/health"
# → {"status":"ok"}
```

### Test 3: Metrics blocked

```bash
curl -s "https://${CF_DOMAIN}/metrics"
# → {"error":"Access denied"}  (CloudFront Function blocks it)
```

---

## Cleanup

```bash
cd bifrost-implementation/scripts

# Delete all stacks in reverse order
REGION=us-east-1
for STACK in bifrost-gw-obs bifrost-gw-cf bifrost-gw-ecs bifrost-gw-vpc; do
  echo "Deleting $STACK..."
  aws cloudformation delete-stack --stack-name $STACK --region $REGION
  aws cloudformation wait stack-delete-complete --stack-name $STACK --region $REGION
done

# Delete S3 artifacts bucket
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET="bifrost-artifacts-${ACCOUNT}-${REGION}"
aws s3 rm s3://$BUCKET --recursive
aws s3 rb s3://$BUCKET

echo "✅ All resources deleted."
```

---

## Security Summary

| Layer | Protection |
|-------|-----------|
| **CloudFront** | HTTPS only, Shield Standard DDoS protection |
| **ALB** | Internal (private subnet), security group = CloudFront prefix list only |
| **Admin UI `/ui`** | Cognito User Pool — only AWS-console-added users can log in |
| **Metrics `/metrics`** | Blocked by CloudFront Function — returns 403 |
| **ECS task** | No public IP, private subnet, outbound via NAT |
| **Bedrock** | IAM role on task — no access keys stored anywhere |
| **Config (SQLite)** | EFS with encryption at rest + transit |
| **Secrets** | Stored in SSM Parameter Store, referenced via IAM |

---

## Costs (Estimate)

| Service | ~Monthly Cost |
|---------|--------------|
| ECS Fargate (1 task, 1 vCPU, 2GB) | ~$35 |
| ALB | ~$20 |
| CloudFront (1M requests) | ~$1 |
| NAT Gateways (2×) | ~$65 |
| EFS | ~$1 |
| CloudWatch (metrics + logs) | ~$5 |
| Lambda (quota publisher) | ~$0 |
| **Total infrastructure** | **~$127/month** |
| Bedrock (Haiku, 1K req/day) | ~$30/month |

*Reduce NAT cost by using VPC endpoints for Bedrock and CloudWatch in production.*
