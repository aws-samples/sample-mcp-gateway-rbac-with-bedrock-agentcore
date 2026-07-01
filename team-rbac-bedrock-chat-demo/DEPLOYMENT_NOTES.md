# Demo 2 — Quick Deployment Notes

> **No manual edits required.** `deploy.sh` handles everything end-to-end.

## Prerequisites

| Tool | Check |
|------|-------|
| AWS CLI | `aws --version` |
| Python 3.11+ | `python3 --version` |
| AWS credentials configured | `aws sts get-caller-identity` |
| Bedrock model access enabled | AWS Console → Bedrock → Model access |

**Required Bedrock models to enable in your region:**
- Claude 3.5 Haiku (`anthropic.claude-3-5-haiku-20241022-v1:0`)
- Claude 3.5 Sonnet (`anthropic.claude-3-5-sonnet-20241022-v2:0`)
- Claude Opus 4 (`anthropic.claude-opus-4-20250514-v1:0`) — optional, used only by Team Alpha to demo a denied request

---

## Deploy (one command)

```bash
cd team-rbac-bedrock-chat-demo
chmod +x deploy.sh

# Minimal deployment
./deploy.sh

# With alarm email and custom stack name
./deploy.sh --email you@example.com --stack-name my-llm-demo --region us-east-1
```

The script:
1. Creates an S3 bucket (`llm-gateway-artifacts-<account>-<region>`) — idempotent
2. Packages and uploads both Lambda functions
3. Creates or updates the CloudFormation stack
4. Enables Bedrock Model Invocation Logging
5. Retrieves API keys and patches `chatbox.html` in-place

When it finishes you'll see:
```
════════════════════════════════════════════════════════
  DEPLOYMENT COMPLETE
  API Endpoint:   https://xxx.execute-api.us-east-1.amazonaws.com/prod/invoke
  ...
════════════════════════════════════════════════════════
```

---

## Open the UI

```bash
open chatbox.html           # macOS
# or
python3 -m http.server 8080 # then open http://localhost:8080/chatbox.html
```

---

## What the demo shows

| Action | Expected result |
|--------|-----------------|
| Team Alpha → Haiku | ✅ Response |
| Team Alpha → Sonnet | ✅ Response |
| Team Alpha → Opus 4 | ❌ 403 Model access denied |
| Team Beta → Haiku | ✅ Response |
| Team Beta → Sonnet | ❌ 403 Model access denied |

Audit log in CloudWatch: `/aws/lambda/<stack>-proxy`

---

## Update Lambda code (after code changes)

Just re-run `./deploy.sh` — it detects the existing stack and updates Lambda code + CFN in one pass.

---

## Teardown

```bash
cd team-rbac-bedrock-chat-demo

STACK_NAME=llm-gateway-demo   # or your custom name
REGION=us-east-1
BUCKET="llm-gateway-artifacts-$(aws sts get-caller-identity --query Account --output text)-${REGION}"

aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION
aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION

# Remove S3 artifacts
aws s3 rm s3://$BUCKET/lambda/ --recursive
aws s3 rb s3://$BUCKET --region $REGION
```

---

## Architecture

```
chatbox.html (browser)
      │  POST /prod/invoke
      │  x-api-key: <team key>
      ▼
API Gateway (REST)
  • Per-team API keys
  • Usage plans (rate + quota limits)
      │
      ▼
Lambda: gateway-proxy
  • Maps API key → team (via env var API_KEY_TEAM_MAPPING or header)
  • Checks model permission: TEAM_ALPHA_MODELS / TEAM_BETA_MODELS env vars
  • Calls bedrock:InvokeModel
  • Tracks tokens in DynamoDB (daily + monthly budgets)
  • Logs structured JSON to CloudWatch
      │
      ▼
AWS Bedrock (Claude models)
      │
      ▼
Lambda: token-metric-publisher
  (triggered by CloudWatch Logs subscription on /aws/bedrock/invocation-logs)
  • Publishes Bedrock/PerUser CloudWatch metrics for per-team cost tracking
```

---

## Known limitations (demo-grade)

- `chatbox.html` contains live API keys after deploy. Do not commit after running `deploy.sh`.
- `API_KEY_TEAM_MAPPING` env var is empty by default — team identity comes from the `team` field in the request body, not the API key. For production, populate this mapping in Secrets Manager.
- Bedrock invocation logging captures prompts/responses in CloudWatch. Disable for sensitive workloads.
