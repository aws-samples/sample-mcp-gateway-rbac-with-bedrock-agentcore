# Bifrost AI Gateway — Installation Guide

> **Deploy time:** ~15-20 minutes | **AWS services:** ECS Fargate, CloudFront, Cognito, CloudWatch, S3

---

## Quick Start (Recommended)

```bash
# 1. Install prerequisites
npm install -g aws-cdk
cd bifrost-implementation/cdk && npm install

# 2. Bootstrap CDK (first time only, once per AWS account/region)
cdk bootstrap

# 3. Deploy everything
ADMIN_EMAIL=you@example.com npx cdk deploy --all --require-approval never
```

That's it. When complete, CDK prints your URLs:
- **Chat UI:** `https://xxxx.cloudfront.net/chat.html`
- **Admin UI:** `https://xxxx.cloudfront.net`
- **CloudWatch Dashboard:** printed in outputs

---

## Configuration Options

All configuration is via **environment variables** or `cdk context`. No hardcoded values.

| Variable | Default | Description |
|---|---|---|
| `ADMIN_EMAIL` | `admin@example.com` | Email for Cognito admin invite + alarm notifications |
| `BIFROST_VERSION` | `latest` | Bifrost Docker image tag (pin for production) |
| `DEPLOY_REGION` | `us-east-1` | AWS region |
| `DAILY_TOKEN_LIMIT_ALPHA` | `100000` | Team Alpha daily token quota |
| `DAILY_TOKEN_LIMIT_BETA` | `50000` | Team Beta daily token quota |
| `SKIP_CLOUDFRONT` | `false` | Set `true` to skip CloudFront + Cognito stack |
| `SKIP_GRAFANA` | `true` | Set `false` to deploy Amazon Managed Grafana + Prometheus |

**Examples:**

```bash
# Minimal deployment (no CloudFront, no Grafana)
ADMIN_EMAIL=you@example.com SKIP_CLOUDFRONT=true SKIP_GRAFANA=true \
  npx cdk deploy BifrostVpcStack BifrostStack BifrostObservabilityStack

# With Grafana
ADMIN_EMAIL=you@example.com SKIP_GRAFANA=false \
  npx cdk deploy --all

# Custom token limits and pin version
ADMIN_EMAIL=you@example.com \
  BIFROST_VERSION=v1.4.3 \
  DAILY_TOKEN_LIMIT_ALPHA=200000 \
  DAILY_TOKEN_LIMIT_BETA=100000 \
  npx cdk deploy --all

# Via CDK context (alternative to env vars)
npx cdk deploy --all \
  --context adminEmail=you@example.com \
  --context bifrostVersion=v1.4.3 \
  --context skipGrafana=false
```

---

## Selective Deployment (Skip Components)

### Core only (no CloudFront, no Grafana)

```bash
ADMIN_EMAIL=you@example.com SKIP_CLOUDFRONT=true SKIP_GRAFANA=true \
  npx cdk deploy BifrostVpcStack BifrostStack BifrostObservabilityStack
```

Then access Bifrost by port-forwarding via AWS Systems Manager:
```bash
TASK_ID=$(aws ecs list-tasks --cluster bifrost-cluster --query 'taskArns[0]' --output text)
aws ssm start-session \
  --target "ecs:bifrost-cluster_${TASK_ID##*/}_$(aws ecs describe-tasks \
    --cluster bifrost-cluster --tasks $TASK_ID \
    --query 'tasks[0].containers[0].runtimeId' --output text)" \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
# Then open: http://localhost:8080
```

### Without Grafana (most common)

```bash
ADMIN_EMAIL=you@example.com npx cdk deploy --all
# SKIP_GRAFANA defaults to true — Grafana stack is not deployed
```

### Without CloudFront

```bash
ADMIN_EMAIL=you@example.com SKIP_CLOUDFRONT=true \
  npx cdk deploy BifrostVpcStack BifrostStack BifrostObservabilityStack
```

---

## Post-Deploy: Configure Bifrost (Required)

After deployment, Bifrost needs to know about your AWS Bedrock provider and teams. This is done via the Admin UI.

### Step 1 — Sign in to Admin UI

1. Check your email (the `ADMIN_EMAIL` you set) for a Cognito invite
2. Open the **Admin UI URL** from CDK outputs
3. Log in with username/temporary password from email

### Step 2 — Add Bedrock Provider

In the Admin UI:
1. **Providers → Add Provider → bedrock**
2. Auth: **IAM Role** (leave keys blank — ECS task role handles auth)
3. Region: `us-east-1` (or your deploy region)
4. Save

### Step 3 — Create Virtual Keys for Teams

**Team Alpha** (Haiku + Sonnet):
1. **Virtual Keys → New Key**
2. Name: `team-alpha`
3. Provider: `bedrock`
4. Allowed models: `us.anthropic.claude-haiku-4-5*`, `us.anthropic.claude-sonnet-4-5*`
5. Daily budget: `100000` tokens
6. Save → **Copy the generated key** (`sk-bf-...`)

**Team Beta** (Haiku only):
1. Name: `team-beta`, Haiku only, `50000` tokens/day
2. Save → **Copy the key**

### Step 4 — Connect Chat UI

```bash
cd bifrost-implementation/scripts

# Replace with your actual virtual keys from Bifrost Admin UI
./update-chatbox-keys.sh \
  sk-bf-xxxxxxxxxxxxxxxxxxxx \
  sk-bf-yyyyyyyyyyyyyyyyyy
```

This patches `chat.html` and uploads it to S3, then invalidates CloudFront.

---

## Manual Step-by-Step Guide

If you prefer not to use CDK, here are the equivalent AWS CLI commands.

### 1. VPC

```bash
# Create VPC
aws ec2 create-vpc --cidr-block 10.10.0.0/16 --region us-east-1

# Create subnets, internet gateway, NAT gateways, route tables
# (see cloudformation/01-vpc.yaml for exact configuration)
```

### 2. ECS + Bifrost

```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name bifrost-cluster --region us-east-1

# Create task definition (generates fresh encryption key automatically)
ENCRYPTION_KEY=$(python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))")

# Store in Secrets Manager (NOT in plaintext)
aws secretsmanager create-secret \
  --name /bifrost/encryption-key \
  --secret-string "{\"key\":\"${ENCRYPTION_KEY}\"}" \
  --region us-east-1

# Create IAM roles, ECS service, ALB
# (see cloudformation/02-ecs.yaml for full configuration)
```

### 3. CloudFront

```bash
# Create S3 bucket for chatbox
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws s3 mb s3://bifrost-chatbox-${ACCOUNT} --region us-east-1

# Create CloudFront VPC Origin (for internal ALB)
ALB_ARN=$(aws elbv2 describe-load-balancers --names bifrost-alb \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text)
aws cloudfront create-vpc-origin \
  --vpc-origin-endpoint-config "Name=bifrost-alb,Arn=${ALB_ARN},HTTPPort=80,HTTPSPort=443,OriginProtocolPolicy=http-only"

# Create Cognito User Pool (for admin UI auth)
aws cognito-idp create-user-pool \
  --pool-name bifrost-admin-pool \
  --admin-create-user-config AllowAdminCreateUserOnly=true

# Create CloudFront distribution with VPC Origin
# (see cloudformation/03-cloudfront.yaml)
```

### 4. Observability

```bash
# Deploy quota publisher Lambda + CloudWatch dashboard
# (see cloudformation/04-observability.yaml)
```

### 5. Grafana (Optional)

```bash
# Prerequisites: IAM Identity Center must be enabled

# Create AMP workspace
aws amp create-workspace --alias bifrost-gateway --region us-east-1

# Create Managed Grafana
aws grafana create-workspace \
  --account-access-type CURRENT_ACCOUNT \
  --authentication-providers AWS_SSO \
  --permission-type SERVICE_MANAGED \
  --workspace-name bifrost-gateway \
  --workspace-data-sources PROMETHEUS CLOUDWATCH XRAY \
  --region us-east-1
```

---

## Cleanup

```bash
# Destroy all CDK stacks
npx cdk destroy --all --force

# Or destroy individual stacks
npx cdk destroy BifrostGrafanaStack --force
npx cdk destroy BifrostObservabilityStack --force
npx cdk destroy BifrostCloudfrontStack --force
npx cdk destroy BifrostStack --force
npx cdk destroy BifrostVpcStack --force
```

---

## Architecture

```
Internet
   │
   ▼
CloudFront (HTTPS, DDoS protection, WAF)
   │  VPC Origin — ALB never exposed to internet
   │
   ├── /* ──────────────────► Bifrost Admin UI (ECS via ALB)
   ├── /v1/* ───────────────► Bifrost API (ECS via ALB)
   ├── /chat.html ──────────► S3 Static Chat UI
   └── /metrics* ──────────► Blocked (403)

ECS Fargate (private subnet):
   Bifrost container ──────► AWS Bedrock (Claude models)
                       ──────► CloudWatch (structured JSON logs)

Lambda (every 5 min):
   QuotaPublisher ──────────► CloudWatch metrics (QuotaUtilisationPct)

CloudWatch Namespace: Bifrost/Gateway
   Metrics: RequestCount, TokensInput, TokensOutput,
            ModelAccessDenied, Errors, LatencySeconds,
            QuotaUtilisationPct, DailyTokensUsed
```

---

## Security

- **No hardcoded credentials** — all secrets auto-generated and stored in AWS Secrets Manager
- **ALB is internal** — never directly accessible from internet, only via CloudFront VPC Origin
- **Admin UI** — protected by Cognito (invite-only, no self-registration)
- **Bedrock access** — via IAM role on ECS task, no API keys
- **Config encryption** — Bifrost uses auto-generated 32-char key stored in Secrets Manager
- **All resources tagged** — `auto-delete=no`, `project=bifrost-gateway`, `ManagedBy=CDK`

---

## Cost Estimate

| Service | ~Monthly Cost |
|---|---|
| ECS Fargate (1 vCPU, 3GB) | ~$35 |
| ALB | ~$20 |
| CloudFront (1M requests) | ~$1 |
| NAT Gateways (2×) | ~$65 |
| CloudWatch (metrics + logs) | ~$5 |
| Lambda (quota publisher) | ~$0 |
| Secrets Manager | ~$0.50 |
| **Total infrastructure** | **~$127/month** |
| Bedrock (Haiku, 1K req/day) | ~$30/month |

*Optional Grafana: ~$10/month for AMG workspace*

---

## Troubleshooting

**CDK bootstrap fails:**
```bash
aws sts get-caller-identity  # Verify credentials work
cdk bootstrap aws://ACCOUNT/REGION
```

**Bifrost health check fails:**
```bash
# Check ECS logs
aws logs tail /bifrost/container --since 10m --region us-east-1
```

**Chat returns 502:**
```bash
# Check CloudFront → ALB connectivity
curl https://YOUR_CLOUDFRONT_URL/health
# Should return: {"status":"ok"}
```

**Virtual keys lost after restart:**
- Bifrost uses in-memory SQLite — re-configure via Admin UI after restarts
- For production: use `config.json` approach (see `bifrost-config.json`)

**Grafana shows "No data":**
- Metrics appear after first requests are made through Bifrost
- Quota metrics appear within 5 minutes (Lambda publisher interval)
- Check CloudWatch namespace `Bifrost/Gateway` in AWS Console
