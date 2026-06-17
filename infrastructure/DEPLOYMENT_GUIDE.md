# Bedrock Governance Demos - Deployment Guide

Complete CloudFormation-based deployment for both demos with one command.

## 🚀 Quick Start (5 minutes)

```bash
# Clone repository
git clone git@github.com:aws-samples/sample-mcp-gateway-rbac-with-bedrock-agentcore.git
cd sample-mcp-gateway-rbac-with-bedrock-agentcore

# Deploy everything
cd infrastructure
./deploy.sh
```

That's it! The script will:
1. ✅ Package all Lambda functions
2. ✅ Create S3 bucket for artifacts
3. ✅ Upload Lambda code and CloudFormation templates
4. ✅ Deploy complete infrastructure (API Gateway, Lambda, WAF, IAM, Guardrails)
5. ✅ Output all configuration values

---

## 📋 Prerequisites

### Required
- **AWS CLI** v2.x configured with credentials
- **Python 3.11+** (for Lambda packaging)
- **zip** command line tool
- **IAM permissions** to create:
  - CloudFormation stacks
  - Lambda functions
  - API Gateway APIs
  - IAM roles and policies
  - S3 buckets
  - WAF WebACLs (if enabled)
  - Bedrock Guardrails (if enabled)

### Optional (for Demo #1)
- **AWS Bedrock AgentCore access** (preview service - [contact AWS](https://aws.amazon.com/bedrock/))
- **AgentCore CLI**: `npm install -g @aws/agentcore-cli`
- **Node.js 18+** (for AgentCore CLI)
- **VS Code + GitHub Copilot** (for testing Demo #1)

---

## 🎯 Deployment Options

### Option 1: Deploy Both Demos (Default)
```bash
./deploy.sh
```

### Option 2: Deploy Demo #1 Only (AgentCore Gateway)
```bash
./deploy.sh --demo1-only
```

### Option 3: Deploy Demo #2 Only (Browser Chat)
```bash
./deploy.sh --demo2-only
```

### Option 4: Custom Configuration
```bash
./deploy.sh \
  --project-name my-bedrock-demo \
  --environment prod \
  --region us-west-2 \
  --no-waf \
  --no-guardrails
```

---

## 🛠️ Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--project-name NAME` | Project name prefix for all resources | `bedrock-governance-demo` |
| `--environment ENV` | Environment: dev/staging/prod | `dev` |
| `--region REGION` | AWS region | `us-east-1` |
| `--demo1-only` | Deploy only Demo #1 (AgentCore Gateway) | Deploy both |
| `--demo2-only` | Deploy only Demo #2 (Browser Chat) | Deploy both |
| `--skip-lambda-package` | Skip Lambda packaging (use existing S3 artifacts) | Package all |
| `--no-waf` | Disable WAF deployment | WAF enabled |
| `--no-guardrails` | Disable Bedrock Guardrails | Guardrails enabled |
| `--help` | Show help message | - |

---

## 📦 What Gets Deployed

### Shared Resources (Always Deployed)
- ✅ S3 bucket for Lambda artifacts and CloudFormation templates
- ✅ CloudWatch Log Groups with retention policies
- ✅ IAM managed policies for Bedrock access
- ✅ SNS topic for alerts
- ✅ CloudWatch alarms for cost monitoring

### Demo #1: AgentCore Gateway + VS Code (Optional)
- ✅ Lambda MCP servers (ecommerce, products, orders, jira)
- ✅ MCP Registry API Gateway (for GitHub Copilot discovery)
- ✅ IAM roles for developer personas (ReadOnly, FullAccess)
- ✅ S3 bucket for Cedar policies
- ✅ CloudWatch metrics and alarms

**Note:** AgentCore Gateway itself is deployed separately via `agentcore deploy` CLI command.

### Demo #2: Browser Chat + Team RBAC (Optional)
- ✅ API Gateway HTTP API with throttling
- ✅ API keys for Team Alpha and Team Beta
- ✅ Lambda proxy function for Bedrock API calls
- ✅ Team IAM roles with model-level permissions
- ✅ AWS WAF with prompt injection protection
- ✅ Bedrock Guardrails for content filtering
- ✅ CloudWatch dashboards and alarms

### Monitoring (Optional, if enabled)
- ✅ Unified CloudWatch dashboard
- ✅ Custom metrics for team usage
- ✅ Cost and performance monitoring

---

## 📊 Architecture

### CloudFormation Stack Structure
```
master-stack.yaml (Root)
├── shared-resources.yaml (Always deployed)
├── demo1-agentcore-gateway.yaml (Optional)
├── demo2-browser-chat.yaml (Optional)
└── monitoring.yaml (Optional)
```

### Deployment Flow
```
1. deploy.sh script
   ├── Package Lambda functions → build/*.zip
   ├── Upload to S3 → s3://{project}-artifacts-{account}/
   └── Deploy CloudFormation → master-stack.yaml

2. CloudFormation master stack
   ├── Creates artifact bucket
   ├── Deploys shared resources nested stack
   ├── Deploys demo1 nested stack (if enabled)
   ├── Deploys demo2 nested stack (if enabled)
   └── Deploys monitoring nested stack (if enabled)

3. Post-deployment (Manual)
   ├── Demo #1: Deploy AgentCore Gateway via CLI
   └── Demo #2: Update chatbox.html with API endpoint
```

---

## 🎬 Post-Deployment Steps

### For Demo #1 (AgentCore Gateway)

After CloudFormation completes, you'll see output like:
```
Demo #1 (AgentCore Gateway):
  Registry URL: https://abc123.execute-api.us-east-1.amazonaws.com/prod
```

**Next steps:**

1. **Deploy AgentCore Gateway** (requires preview access):
   ```bash
   cd DemoMcpGateway/agentcore
   agentcore deploy
   ```

2. **Update registry Lambda with gateway URL**:
   ```bash
   GATEWAY_URL=$(agentcore gateway describe --output json | jq -r '.gatewayUrl')
   aws lambda update-function-configuration \
     --function-name bedrock-governance-demo-dev-mcp-registry \
     --environment Variables={GATEWAY_URL=$GATEWAY_URL}
   ```

3. **Configure VS Code**:
   - Copy `vscode-config/mcp.json` to your VS Code settings
   - Update `registryUrl` with the Registry URL from step 1
   - Restart VS Code

4. **Test in VS Code**:
   - Open GitHub Copilot chat
   - Ask: "List customers" (should see MCP tools)

### For Demo #2 (Browser Chat)

After CloudFormation completes, you'll see output like:
```
Demo #2 (Browser Chat):
  API Endpoint: https://xyz789.execute-api.us-east-1.amazonaws.com/prod/invoke
  Team Alpha API Key: AbCd1234...
  Team Beta API Key:  EfGh5678...
```

**Next steps:**

1. **Update chatbox HTML**:
   ```bash
   cd team-rbac-bedrock-chat-demo
   # Edit chatbox.html and replace:
   # - API_ENDPOINT: <paste endpoint from output>
   # - TEAM_ALPHA_API_KEY: <paste Team Alpha key>
   # - TEAM_BETA_API_KEY: <paste Team Beta key>
   ```

2. **Open in browser**:
   ```bash
   open chatbox.html
   ```

3. **Test team-based access**:
   - Select Team A → Try Claude Sonnet (should work)
   - Select Team B → Try Claude Sonnet (should be denied)
   - Check CloudWatch Logs for request attribution

---

## 🔧 Configuration Parameters

### CloudFormation Parameters

You can customize the deployment by modifying `deploy.sh` or passing parameters directly:

```bash
aws cloudformation deploy \
  --template-file cloudformation/master-stack.yaml \
  --stack-name bedrock-governance-demo-dev-master \
  --parameter-overrides \
      ProjectName=my-demo \
      Environment=prod \
      DeployDemo1=true \
      DeployDemo2=true \
      Demo2TeamAlphaRateLimit=100 \
      Demo2TeamBetaRateLimit=50 \
      Demo2EnableWAF=true \
      Demo2EnableGuardrails=true \
      EnableCloudWatchDashboards=true \
      EnableXRayTracing=false \
      LambdaLogRetentionDays=7 \
  --capabilities CAPABILITY_NAMED_IAM
```

### Key Parameters

| Parameter | Description | Default | Valid Values |
|-----------|-------------|---------|--------------|
| `ProjectName` | Prefix for all resource names | `bedrock-governance-demo` | Lowercase, hyphens |
| `Environment` | Environment name | `dev` | dev, staging, prod |
| `DeployDemo1` | Deploy Demo #1 | `true` | true, false |
| `DeployDemo2` | Deploy Demo #2 | `true` | true, false |
| `Demo2TeamAlphaRateLimit` | Requests/sec for Team Alpha | `50` | 1-10000 |
| `Demo2TeamBetaRateLimit` | Requests/sec for Team Beta | `20` | 1-10000 |
| `Demo2EnableWAF` | Enable AWS WAF | `true` | true, false |
| `Demo2EnableGuardrails` | Enable Bedrock Guardrails | `true` | true, false |
| `EnableCloudWatchDashboards` | Create dashboards | `true` | true, false |
| `EnableXRayTracing` | Enable X-Ray | `false` | true, false |
| `LambdaLogRetentionDays` | Log retention period | `7` | 1-3653 days |

---

## 💰 Cost Estimate

### Monthly Costs (for testing workload)

**Demo #1 (10 developers, 100 tool calls/day):**
- AgentCore Gateway: ~$5
- Lambda (MCPs): ~$1
- CloudWatch Logs: ~$0.50
- **Total: ~$6.50/month**

**Demo #2 (10 teams, 1000 requests/day):**
- API Gateway: ~$3
- Lambda (proxy): ~$1
- CloudWatch Logs: ~$2.50
- Bedrock (Haiku): ~$900 *(model costs dominate)*
- WAF: ~$5
- **Total: ~$911.50/month**

**Combined:** ~$918/month

*Most cost is Bedrock model inference ($0.003/1K tokens). Gateway overhead is minimal.*

---

## 🐛 Troubleshooting

### Issue: CloudFormation fails with "Artifact bucket does not exist"

**Solution:** The script creates the bucket automatically. If deployment fails partway through, re-run:
```bash
./deploy.sh
```

### Issue: Lambda packaging fails

**Solution:** Ensure Python 3.11+ and zip are installed:
```bash
python3 --version  # Should be 3.11 or higher
zip --version
```

### Issue: "Access Denied" when creating resources

**Solution:** Check IAM permissions:
```bash
aws iam get-user
aws sts get-caller-identity
```

Ensure your IAM user/role has:
- `cloudformation:*`
- `lambda:*`
- `apigateway:*`
- `iam:CreateRole`, `iam:AttachRolePolicy`
- `s3:CreateBucket`, `s3:PutObject`

### Issue: Demo #1 - "AgentCore CLI not found"

**Solution:** Demo #1 requires AgentCore preview access:
```bash
# Install AgentCore CLI
npm install -g @aws/agentcore-cli
agentcore --version

# If you don't have preview access, deploy Demo #2 only:
./deploy.sh --demo2-only
```

### Issue: Demo #2 - API returns 403 Forbidden

**Solution:** Check API keys are correctly configured in chatbox.html:
```javascript
// Verify these match CloudFormation outputs
const TEAMS = {
  'team-a': {
    apiKey: "YOUR_TEAM_A_API_KEY_FROM_CLOUDFORMATION_OUTPUT"
  }
}
```

### Issue: WAF blocks legitimate requests

**Solution:** Review WAF rules in CloudFormation:
```bash
# Check WAF metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/WAFV2 \
  --metric-name BlockedRequests \
  --dimensions Name=Rule,Value=BlockPromptInjection \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum
```

To disable WAF temporarily:
```bash
./deploy.sh --no-waf
```

---

## 🗑️ Clean Up

### Delete Everything
```bash
# Get stack name
STACK_NAME="bedrock-governance-demo-dev-master"
AWS_REGION="us-east-1"

# Delete CloudFormation stack (deletes all nested stacks)
aws cloudformation delete-stack \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}"

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}"

# Delete S3 artifact bucket (optional - contains Lambda code)
ARTIFACT_BUCKET="bedrock-governance-demo-dev-artifacts-$(aws sts get-caller-identity --query Account --output text)"
aws s3 rb "s3://${ARTIFACT_BUCKET}" --force
```

### Delete Demo #1 Only
```bash
# Find Demo #1 nested stack
aws cloudformation describe-stack-resources \
  --stack-name "${STACK_NAME}" \
  --query "StackResources[?LogicalResourceId=='Demo1Stack'].PhysicalResourceId" \
  --output text

# Delete nested stack
aws cloudformation delete-stack --stack-name <demo1-stack-id>
```

### Delete Demo #2 Only
```bash
# Find Demo #2 nested stack
aws cloudformation describe-stack-resources \
  --stack-name "${STACK_NAME}" \
  --query "StackResources[?LogicalResourceId=='Demo2Stack'].PhysicalResourceId" \
  --output text

# Delete nested stack
aws cloudformation delete-stack --stack-name <demo2-stack-id>
```

---

## 🔐 Security Best Practices

### IAM Roles
- ✅ Least privilege: Team roles only have access to specific Bedrock models
- ✅ No long-term credentials: Uses IAM roles for Lambda
- ✅ External IDs for cross-account access

### API Gateway
- ✅ API keys for authentication
- ✅ Rate limiting per team (throttling)
- ✅ CORS configured for browser access
- ✅ CloudWatch logging enabled

### WAF
- ✅ Prompt injection protection
- ✅ Rate limiting (2000 req/sec per IP)
- ✅ AWS Managed Rule Sets (Common Rule Set)
- ✅ Custom response bodies for blocked requests

### Bedrock Guardrails
- ✅ Content filtering (hate, violence, sexual, misconduct)
- ✅ PII detection and blocking
- ✅ Profanity filtering
- ✅ Prompt attack detection

### Encryption
- ✅ S3 bucket encryption (AES-256)
- ✅ CloudWatch Logs encryption
- ✅ Secrets stored in environment variables (consider AWS Secrets Manager for production)

---

## 📚 Additional Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Cedar Policy Language](https://www.cedarpolicy.com/)
- [CloudFormation Best Practices](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html)

---

## 🤝 Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

---

## 📄 License

This library is licensed under the MIT-0 License. See [LICENSE](../LICENSE).

---

## 💡 Tips

### Faster Iteration
```bash
# Skip Lambda packaging if code hasn't changed
./deploy.sh --skip-lambda-package
```

### Different Environments
```bash
# Deploy to staging
./deploy.sh --environment staging --region us-west-2

# Deploy to production
./deploy.sh --environment prod --region eu-west-1
```

### Cost Optimization
```bash
# Disable WAF for dev environments
./deploy.sh --environment dev --no-waf

# Use shorter log retention
# Edit deploy.sh and change LambdaLogRetentionDays parameter
```

### Monitoring
```bash
# View CloudWatch dashboard
echo "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=bedrock-governance-demo-dev-unified"

# Tail Lambda logs
aws logs tail /aws/lambda/bedrock-governance-demo-dev-gateway-proxy --follow

# Check Bedrock usage
aws cloudwatch get-metric-statistics \
  --namespace AWS/Bedrock \
  --metric-name ModelInvocations \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

---

**Need help?** Open an issue in the GitHub repository.

**Happy building!** 🚀
