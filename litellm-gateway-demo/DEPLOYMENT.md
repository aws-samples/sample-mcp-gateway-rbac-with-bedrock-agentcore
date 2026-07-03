# Deployment Guide — LiteLLM Gateway on AWS

## Two Deployment Paths

| Path | Time | Cost | Best For |
|------|------|------|----------|
| **Local (Docker Compose)** | 5 min | $0 (only Bedrock usage) | Testing, development, quick demos |
| **AWS (ECS Fargate)** | 20 min | ~$82/mo infrastructure | Customer-facing demos, production |

---

## Path A: Local Deployment (Docker Compose)

### Prerequisites

- Docker Desktop installed and running
- AWS credentials with `bedrock:InvokeModel` permission
- Bedrock model access enabled in your AWS account (us-east-1)

### Steps

```bash
cd litellm-gateway-demo

# 1. Configure credentials
cp .env.example .env
# Edit .env with your AWS credentials:
#   AWS_ACCESS_KEY_ID=AKIA...
#   AWS_SECRET_ACCESS_KEY=...
#   AWS_REGION=us-east-1
#   LITELLM_MASTER_KEY=sk-demo-master-key  (change for production)

# 2. Start all services
docker compose up -d

# 3. Wait for healthy (usually 15-20s)
docker compose ps  # All should show "healthy"

# 4. Setup teams and keys
./scripts/setup-teams.sh

# 5. Test it
./scripts/test-demo.sh
```

### Verify

```bash
# Check health
curl http://localhost:4000/health

# Check models are loaded
curl http://localhost:4000/model/info \
  -H "Authorization: Bearer sk-demo-master-key"

# Open Admin UI
open http://localhost:4000/ui
# Login with: sk-demo-master-key
```

### Stop / Cleanup

```bash
docker compose down       # Stop containers (keeps data)
docker compose down -v    # Stop + delete all data
```

---

## Path B: AWS Deployment (ECS Fargate)

### Prerequisites

- AWS CLI configured with admin credentials
- Docker installed (for building the container image)
- Bedrock model access enabled in target region

### Architecture on AWS

```
Internet → ALB (HTTPS) → ECS Fargate (LiteLLM) → Bedrock
                                ↓
                    RDS PostgreSQL + ElastiCache Redis
```

### Step 1: Deploy Infrastructure

```bash
cd litellm-gateway-demo

# Set your variables
export AWS_REGION=us-east-1
export STACK_NAME=litellm-gateway-demo

# Deploy the CloudFormation stack
aws cloudformation deploy \
  --template-file infrastructure/cloudformation/litellm-stack.yaml \
  --stack-name $STACK_NAME \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    LiteLLMMasterKey=sk-your-secure-master-key \
    BedrockRegion=$AWS_REGION \
  --region $AWS_REGION

# Wait for completion (~10-15 min)
aws cloudformation wait stack-create-complete \
  --stack-name $STACK_NAME --region $AWS_REGION
```

### Step 2: Get Outputs

```bash
# Get the ALB URL
ALB_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME --region $AWS_REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerUrl`].OutputValue' \
  --output text)

echo "LiteLLM URL: http://$ALB_URL"
echo "Admin UI:    http://$ALB_URL/ui"
```

### Step 3: Setup Teams

```bash
./scripts/setup-teams.sh "http://$ALB_URL"
```

### Step 4: Test

```bash
./scripts/test-demo.sh "http://$ALB_URL"
```

### Cleanup

```bash
aws cloudformation delete-stack --stack-name $STACK_NAME --region $AWS_REGION
aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $AWS_REGION
echo "✅ All resources deleted"
```

---

## Troubleshooting

### "Connection refused" on localhost:4000

```bash
# Check container status
docker compose ps
docker compose logs litellm
```

Common causes:
- PostgreSQL not ready yet (wait 10s, retry)
- Invalid config.yaml syntax
- Port 4000 already in use

### "Could not find model" error

```bash
# Check loaded models
curl http://localhost:4000/model/info \
  -H "Authorization: Bearer sk-demo-master-key" | python3 -m json.tool
```

Ensure your AWS credentials have Bedrock access and models are enabled.

### "BudgetExceededError" during setup

The team or key budget was already exceeded. Reset it:
```bash
curl -X POST http://localhost:4000/team/update \
  -H "Authorization: Bearer sk-demo-master-key" \
  -H "Content-Type: application/json" \
  -d '{"team_id": "<TEAM_ID>", "max_budget": 200.00}'
```

### ECS Task keeps restarting

Check CloudWatch logs:
```bash
aws logs tail /ecs/litellm-gateway --follow --region $AWS_REGION
```

Common causes:
- DATABASE_URL incorrect (RDS not ready or wrong password)
- REDIS_HOST not reachable (security group issue)
- AWS credentials not passed to task (check task role)
