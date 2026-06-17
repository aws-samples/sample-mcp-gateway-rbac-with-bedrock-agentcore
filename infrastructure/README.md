# Infrastructure - CloudFormation Deployment

**One-command deployment for both Bedrock Governance demos.**

## 🚀 Quick Start

```bash
./deploy.sh
```

That's it! See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for detailed instructions.

---

## 📁 Directory Structure

```
infrastructure/
├── deploy.sh                           # One-click deployment script
├── DEPLOYMENT_GUIDE.md                 # Comprehensive deployment docs
├── README.md                           # This file
│
├── cloudformation/
│   ├── master-stack.yaml               # Root CloudFormation template
│   │
│   ├── nested-stacks/
│   │   ├── shared-resources.yaml       # Shared infrastructure (S3, IAM, Logs)
│   │   ├── demo1-agentcore-gateway.yaml # Demo #1: Lambda MCPs, MCP Registry
│   │   ├── demo2-browser-chat.yaml     # Demo #2: API Gateway, WAF, Guardrails
│   │   └── monitoring.yaml             # CloudWatch dashboards
│   │
│   └── parameters/
│       ├── dev.json                    # Dev environment parameters
│       ├── staging.json                # Staging environment parameters
│       └── prod.json                   # Production environment parameters
│
└── scripts/
    ├── package-lambda.sh               # Package Lambda functions
    ├── validate-templates.sh           # Validate CloudFormation templates
    └── cleanup.sh                      # Clean up deployed resources
```

---

## 🎯 What Gets Deployed

### Complete Infrastructure
- ✅ **API Gateway** - HTTP API with rate limiting
- ✅ **Lambda Functions** - MCP servers + gateway proxy
- ✅ **IAM Roles** - Team-based access control
- ✅ **AWS WAF** - Prompt injection protection
- ✅ **Bedrock Guardrails** - Content filtering
- ✅ **CloudWatch** - Logs, metrics, dashboards, alarms
- ✅ **S3 Buckets** - Artifacts and Cedar policies

### Deployment Time
- Initial deployment: **5-8 minutes**
- Subsequent updates: **2-3 minutes**

---

## 📋 Prerequisites

| Requirement | Version | Installation |
|-------------|---------|--------------|
| AWS CLI | 2.x | [Install Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| Python | 3.11+ | [Download](https://www.python.org/downloads/) |
| zip | Any | Usually pre-installed |
| IAM Permissions | Admin | Needed for first deployment |

Optional (for Demo #1 only):
- AWS Bedrock AgentCore preview access
- AgentCore CLI: `npm install -g @aws/agentcore-cli`
- Node.js 18+
- VS Code + GitHub Copilot

---

## 🎮 Deployment Options

### Deploy Everything (Default)
```bash
./deploy.sh
```

### Deploy Specific Demo
```bash
# Demo #1 only (AgentCore Gateway + VS Code)
./deploy.sh --demo1-only

# Demo #2 only (Browser Chat)
./deploy.sh --demo2-only
```

### Custom Configuration
```bash
./deploy.sh \
  --project-name my-demo \
  --environment prod \
  --region us-west-2 \
  --no-waf \
  --no-guardrails
```

### Options Reference
```
--project-name NAME      Project name (default: bedrock-governance-demo)
--environment ENV        dev/staging/prod (default: dev)
--region REGION          AWS region (default: us-east-1)
--demo1-only             Deploy only Demo #1
--demo2-only             Deploy only Demo #2
--skip-lambda-package    Use existing S3 artifacts
--no-waf                 Disable WAF
--no-guardrails          Disable Bedrock Guardrails
--help                   Show help
```

---

## 📊 Stack Architecture

```
master-stack (Root)
├── ArtifactBucket (S3)
├── shared-resources (Nested Stack)
│   ├── CloudWatch Log Groups
│   ├── IAM Managed Policies
│   ├── SNS Alert Topic
│   └── SSM Parameters
│
├── demo1-stack (Nested Stack - Optional)
│   ├── Lambda MCP Servers (ecommerce, products, orders, jira)
│   ├── MCP Registry API Gateway
│   ├── IAM Roles (ReadOnly, FullAccess developers)
│   └── S3 Bucket (Cedar policies)
│
├── demo2-stack (Nested Stack - Optional)
│   ├── API Gateway HTTP API
│   ├── Lambda Gateway Proxy
│   ├── Team IAM Roles (Alpha, Beta)
│   ├── API Keys & Usage Plans
│   ├── AWS WAF WebACL
│   └── Bedrock Guardrail
│
└── monitoring-stack (Nested Stack - Optional)
    └── CloudWatch Dashboard
```

---

## 🔄 Update Existing Stack

```bash
# Make changes to CloudFormation templates
vim cloudformation/nested-stacks/demo2-browser-chat.yaml

# Re-run deployment (CloudFormation handles updates automatically)
./deploy.sh
```

CloudFormation automatically detects changes and updates only modified resources.

---

## 🗑️ Clean Up

### Delete Everything
```bash
# Delete stack
aws cloudformation delete-stack \
  --stack-name bedrock-governance-demo-dev-master \
  --region us-east-1

# Delete artifact bucket (optional)
aws s3 rb s3://bedrock-governance-demo-dev-artifacts-$(aws sts get-caller-identity --query Account --output text) --force
```

### Quick Cleanup Script
```bash
./scripts/cleanup.sh --environment dev --region us-east-1
```

---

## 🔧 Advanced Usage

### Validate Templates Before Deployment
```bash
./scripts/validate-templates.sh
```

### Deploy with Parameter File
```bash
aws cloudformation deploy \
  --template-file cloudformation/master-stack.yaml \
  --stack-name my-stack \
  --parameter-overrides file://cloudformation/parameters/prod.json \
  --capabilities CAPABILITY_NAMED_IAM
```

### Package Lambda Functions Only
```bash
./scripts/package-lambda.sh --output-dir ./build
```

### Deploy to Multiple Regions
```bash
for region in us-east-1 us-west-2 eu-west-1; do
  ./deploy.sh --region $region --environment prod
done
```

---

## 💰 Cost Breakdown

| Component | Monthly Cost (Estimate) |
|-----------|------------------------|
| API Gateway | $3 (1M requests) |
| Lambda | $1-5 (compute time) |
| CloudWatch Logs | $2-10 (retention) |
| WAF | $5 (base + rules) |
| Bedrock Models | $900+ (usage-based) |
| **Total Gateway Overhead** | **~$15/month** |
| **Total with Bedrock** | **~$915/month** |

*Gateway infrastructure is minimal cost. Bedrock model inference dominates.*

---

## 🐛 Common Issues

| Issue | Solution |
|-------|----------|
| "Artifact bucket does not exist" | Script creates it automatically. Re-run `./deploy.sh` |
| "Access Denied" | Check IAM permissions (need CloudFormation, Lambda, IAM, S3) |
| Lambda packaging fails | Install Python 3.11+ and zip |
| AgentCore CLI not found | Demo #1 requires preview access. Use `--demo2-only` |
| API returns 403 | Check API keys in chatbox.html match CloudFormation outputs |

See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for detailed troubleshooting.

---

## 📚 Additional Documentation

- **[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)** - Complete deployment instructions
- **[../README.md](../README.md)** - Repository overview
- **[../gateway-url-ide-integration-demo/README.md](../gateway-url-ide-integration-demo/README.md)** - Demo #1 details
- **[../team-rbac-bedrock-chat-demo/README.md](../team-rbac-bedrock-chat-demo/README.md)** - Demo #2 details

---

## 🤝 Support

- **Issues:** Open a GitHub issue
- **Questions:** See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) troubleshooting section
- **AWS Support:** Contact your AWS account team for AgentCore preview access

---

## 📄 License

MIT-0 License. See [../LICENSE](../LICENSE).

---

**Made with ❤️ by AWS Solutions**

Deploy in 5 minutes: `./deploy.sh` 🚀
