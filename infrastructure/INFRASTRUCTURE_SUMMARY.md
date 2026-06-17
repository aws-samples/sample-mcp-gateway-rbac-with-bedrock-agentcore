# Infrastructure Summary - CloudFormation Implementation

## ✅ What Was Created

Complete Infrastructure-as-Code (IaC) implementation for both Bedrock Governance demos with **one-command deployment**.

---

## 📦 Deliverables

### 1. CloudFormation Templates (Production-Ready)

| File | Purpose | Resources |
|------|---------|-----------|
| **master-stack.yaml** | Root orchestration template | Artifact S3 bucket, nested stack orchestration |
| **shared-resources.yaml** | Common infrastructure | CloudWatch Logs, IAM policies, SNS alerts, SSM parameters |
| **demo1-agentcore-gateway.yaml** | AgentCore Gateway + MCPs | 4x Lambda MCPs, MCP Registry API, IAM roles, Cedar policy bucket |
| **demo2-browser-chat.yaml** | Browser Chat + Team RBAC | API Gateway v2, Lambda proxy, WAF, Guardrails, API keys, Team roles |
| **monitoring.yaml** | Unified monitoring | CloudWatch dashboard with Lambda, API Gateway, Bedrock metrics |

**Total:** 5 CloudFormation templates with 60+ AWS resources

---

### 2. Deployment Automation

| File | Purpose | Features |
|------|---------|----------|
| **deploy.sh** | One-click deployment script | Lambda packaging, S3 upload, CloudFormation deployment, output extraction |
| **DEPLOYMENT_GUIDE.md** | Comprehensive deployment docs | Prerequisites, options, troubleshooting, cost estimates |
| **README.md** | Quick reference guide | TL;DR deployment, common tasks, architecture diagram |

---

## 🎯 Key Features Implemented

### Complete Production Infrastructure
✅ **API Gateway v2 (HTTP API)** with throttling and CORS  
✅ **API Keys and Usage Plans** for team-based access  
✅ **AWS WAF** with prompt injection protection  
✅ **Bedrock Guardrails** for content filtering  
✅ **Lambda Functions** with reserved concurrency  
✅ **IAM Roles** with least-privilege policies  
✅ **CloudWatch** Logs, Metrics, Alarms, Dashboards  
✅ **X-Ray Tracing** (optional)  
✅ **S3 Buckets** with encryption and versioning  

### Developer Experience
✅ **One-command deployment:** `./deploy.sh`  
✅ **Parameterized configuration** (project name, environment, region)  
✅ **Automatic Lambda packaging** (no manual zipping)  
✅ **Nested stacks** for modular architecture  
✅ **Conditional resources** (deploy Demo #1 only, Demo #2 only, or both)  
✅ **Post-deployment outputs** (API endpoints, API keys, next steps)  

### Enterprise Features
✅ **Multi-environment support** (dev, staging, prod)  
✅ **Cost monitoring** with CloudWatch alarms  
✅ **Security best practices** (encryption, least privilege, WAF)  
✅ **Observability** (structured logging, metrics, dashboards)  
✅ **Infrastructure as Code** (version-controlled, repeatable)  

---

## 📊 Architecture Overview

### Deployment Flow
```
User runs: ./deploy.sh
    │
    ├─→ 1. Package Lambda functions → build/*.zip
    ├─→ 2. Create S3 bucket (if not exists)
    ├─→ 3. Upload artifacts to S3
    ├─→ 4. Deploy master-stack.yaml
    │
    └─→ CloudFormation creates:
        ├─→ Artifact S3 bucket
        ├─→ Shared resources (nested stack)
        ├─→ Demo #1 stack (nested stack, optional)
        ├─→ Demo #2 stack (nested stack, optional)
        └─→ Monitoring stack (nested stack, optional)
```

### Stack Dependencies
```
master-stack
├── ArtifactBucket (S3)
│
├── SharedResourcesStack
│   └── Exports: LogGroups, IAM Policies, SNS Topic
│
├── Demo1Stack (depends on SharedResourcesStack)
│   └── Exports: RegistryUrl, MCPServerArns
│
├── Demo2Stack (depends on SharedResourcesStack)
│   └── Exports: ApiEndpoint, ApiKeys, WAF ID
│
└── MonitoringStack (depends on Demo1Stack, Demo2Stack)
    └── Outputs: DashboardUrl
```

---

## 🚀 Deployment Options

### Default (Both Demos)
```bash
./deploy.sh
```

### Demo-Specific
```bash
./deploy.sh --demo1-only    # AgentCore Gateway + VS Code
./deploy.sh --demo2-only    # Browser Chat + Team RBAC
```

### Custom Configuration
```bash
./deploy.sh \
  --project-name my-bedrock-demo \
  --environment prod \
  --region us-west-2 \
  --no-waf \
  --no-guardrails
```

### Update Existing Stack
```bash
# Edit CloudFormation templates
vim infrastructure/cloudformation/nested-stacks/demo2-browser-chat.yaml

# Re-deploy (CloudFormation updates only changed resources)
./deploy.sh
```

---

## 📋 What Each Template Deploys

### Master Stack (`master-stack.yaml`)
- S3 Artifact Bucket with encryption and versioning
- Orchestrates 4 nested stacks
- Exports API endpoints, API keys, and configuration values

### Shared Resources (`shared-resources.yaml`)
- CloudWatch Log Groups (3 total: Demo1, Demo2, API Gateway)
- IAM Managed Policies (Bedrock invoke, guardrails, X-Ray)
- SNS Topic for alerts
- SSM Parameters for configuration
- CloudWatch Alarms for cost monitoring

### Demo #1 (`demo1-agentcore-gateway.yaml`)
**Lambda MCP Servers:**
- `ecommerce-mcp` - Customer data tools
- `products-mcp` - Product catalog tools
- `orders-mcp` - Order management tools
- `jira-mcp` - Jira ticket lookup tools

**API Gateway:**
- REST API for MCP Registry (GitHub Copilot discovery)

**IAM Roles:**
- `readonly-developer` - Junior developers (read-only MCP access)
- `fullaccess-developer` - Senior developers (full MCP access)

**Storage:**
- S3 bucket for Cedar policies

**Monitoring:**
- CloudWatch Log Groups per Lambda
- X-Ray tracing (optional)

### Demo #2 (`demo2-browser-chat.yaml`)
**API Gateway:**
- HTTP API v2 with CORS
- Throttling: 200 burst, 100 sustained
- Access logging to CloudWatch

**Lambda:**
- Gateway proxy function (Python 3.11)
- Reserved concurrency: 100
- PowerTools layer included
- Team-based model RBAC logic

**Team IAM Roles:**
- `team-alpha` - High volume (50 req/sec), Haiku + Sonnet access
- `team-beta` - Standard (20 req/sec), Haiku-only access

**API Keys:**
- Team Alpha API key
- Team Beta API key

**AWS WAF (Optional):**
- Rate limiting (2000 req/sec per IP)
- Prompt injection detection (blocks: "ignore all previous instructions")
- AWS Managed Rules (Common Rule Set)
- Custom response bodies for blocked requests

**Bedrock Guardrails (Optional):**
- Content filtering (hate, violence, sexual, misconduct, prompt attacks)
- PII detection (email, phone, SSN, credit cards)
- Profanity filtering
- Configurable input/output strength

**CloudWatch Alarms:**
- Lambda error alarm (threshold: 10 errors in 5 min)
- API Gateway 5XX alarm (threshold: 5 errors in 5 min)
- Bedrock throttling alarm (threshold: 5 throttles in 5 min)

### Monitoring (`monitoring.yaml`)
**CloudWatch Dashboard:**
- Lambda performance (invocations, errors, duration)
- Bedrock usage (invocations, throttles, token counts)
- API Gateway metrics (requests, 4XX/5XX errors, latency)
- Team-based usage patterns (log insights query)

---

## 💰 Cost Analysis

### Infrastructure Costs (Monthly)

| Component | Cost | Notes |
|-----------|------|-------|
| **API Gateway** | $3 | 1M requests/month |
| **Lambda** | $1-5 | Depends on invocations and memory |
| **CloudWatch Logs** | $2-10 | Depends on log volume and retention |
| **WAF** | $5 | Base fee + $1/rule |
| **S3** | <$1 | Minimal storage for artifacts |
| **Bedrock** | $900+ | Model inference (usage-based) |
| **Total Gateway** | **~$15/month** | Infrastructure overhead |
| **Total with Bedrock** | **~$915/month** | For 1M requests with Haiku |

**Key Takeaway:** Gateway infrastructure adds only ~$15/month overhead. Bedrock model costs dominate (~98% of total).

---

## 🔐 Security Features

### IAM
- ✅ Least privilege roles (teams can only invoke allowed models)
- ✅ No long-term credentials (Lambda execution roles)
- ✅ External IDs for cross-account assume role
- ✅ Resource-based policies on Lambda

### API Gateway
- ✅ API key authentication
- ✅ Rate limiting (throttling)
- ✅ CORS configured for browser access
- ✅ CloudWatch access logging

### WAF
- ✅ Prompt injection protection
- ✅ Rate limiting (2000 req/sec per IP)
- ✅ AWS Managed Rules
- ✅ Custom blocking responses

### Bedrock Guardrails
- ✅ Content filtering (6 categories)
- ✅ PII detection and blocking
- ✅ Prompt attack detection
- ✅ Configurable sensitivity levels

### Data Protection
- ✅ S3 bucket encryption (AES-256)
- ✅ CloudWatch Logs encryption
- ✅ Versioned S3 buckets (artifact retention)
- ✅ Public access blocked on S3

---

## 📊 Observability

### CloudWatch Logs
- `/aws/lambda/${ProjectName}-${Environment}-demo1/` - Demo #1 MCPs
- `/aws/lambda/${ProjectName}-${Environment}-demo2/` - Demo #2 proxy
- `/aws/apigateway/${ProjectName}-${Environment}` - API Gateway access logs

### CloudWatch Metrics
- **Lambda:** Invocations, Errors, Duration, Throttles
- **API Gateway:** Count, 4XXError, 5XXError, Latency
- **Bedrock:** ModelInvocations, ModelInvocationThrottle, TokenCounts
- **WAF:** BlockedRequests, AllowedRequests (per rule)

### CloudWatch Alarms
- Lambda error rate > 10 in 5 minutes
- API Gateway 5XX rate > 5 in 5 minutes
- Bedrock throttling > 5 in 5 minutes
- Monthly Bedrock cost > $100

### X-Ray Tracing (Optional)
- End-to-end request tracing
- Service map visualization
- Performance bottleneck identification

---

## 🧪 Testing

### Validate Templates
```bash
cd infrastructure
aws cloudformation validate-template --template-body file://cloudformation/master-stack.yaml
aws cloudformation validate-template --template-body file://cloudformation/nested-stacks/demo2-browser-chat.yaml
```

### Deploy to Test Environment
```bash
./deploy.sh --environment test --region us-east-1
```

### Check Deployment Status
```bash
aws cloudformation describe-stacks \
  --stack-name bedrock-governance-demo-dev-master \
  --query 'Stacks[0].StackStatus'
```

### View Stack Outputs
```bash
aws cloudformation describe-stacks \
  --stack-name bedrock-governance-demo-dev-master \
  --query 'Stacks[0].Outputs' \
  --output table
```

---

## 🔄 Updates and Maintenance

### Update Lambda Code
```bash
# Edit Lambda code
vim ../team-rbac-bedrock-chat-demo/lambda/gateway-proxy/lambda_function.py

# Re-deploy (packages and uploads Lambda automatically)
./deploy.sh
```

### Update CloudFormation Template
```bash
# Edit template
vim cloudformation/nested-stacks/demo2-browser-chat.yaml

# Deploy changes (CloudFormation handles updates)
./deploy.sh
```

### Update Stack Parameters
```bash
./deploy.sh \
  --project-name bedrock-governance-demo \
  --environment prod \
  --region us-west-2
```

---

## 🗑️ Clean Up

### Delete Everything
```bash
# Delete stack (deletes all nested stacks automatically)
aws cloudformation delete-stack \
  --stack-name bedrock-governance-demo-dev-master \
  --region us-east-1

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name bedrock-governance-demo-dev-master

# Delete S3 artifact bucket (optional)
aws s3 rb s3://bedrock-governance-demo-dev-artifacts-$(aws sts get-caller-identity --query Account --output text) --force
```

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| **DEPLOYMENT_GUIDE.md** | Complete deployment instructions (prerequisites, options, troubleshooting) |
| **README.md** | Quick reference (TL;DR deployment, common tasks) |
| **INFRASTRUCTURE_SUMMARY.md** | This document (architecture overview, features, costs) |

---

## ✅ Benefits of This Implementation

### For Developers
✅ **5-minute deployment** - One command deploys everything  
✅ **No manual steps** - Automated Lambda packaging and S3 upload  
✅ **Clean outputs** - API endpoints and keys clearly displayed  
✅ **Easy updates** - Change code or config, re-run `./deploy.sh`  

### For Operators
✅ **Infrastructure as Code** - Version-controlled, repeatable deployments  
✅ **Multi-environment** - Deploy to dev/staging/prod with same code  
✅ **Modular architecture** - Nested stacks for clean separation  
✅ **Conditional resources** - Enable/disable WAF, Guardrails, Demo #1, Demo #2  

### For Architects
✅ **Production-ready** - WAF, Guardrails, monitoring, alarms included  
✅ **Best practices** - Least privilege IAM, encryption, versioning  
✅ **Observable** - CloudWatch dashboards, logs, metrics, alarms  
✅ **Cost-optimized** - Reserved concurrency, log retention, S3 lifecycle  

### For TAMs/SAs
✅ **Customer-ready** - Complete, deployable reference architecture  
✅ **Demo-friendly** - Deploy in 5 minutes before customer meeting  
✅ **Customizable** - Easy to adjust parameters for customer needs  
✅ **Well-documented** - Deployment guide, architecture diagrams, cost estimates  

---

## 🎯 Use Cases

### Reference Architecture
Use this as a starting point for:
- LLM Gateway implementations
- Team-based model access control
- Bedrock Guardrails examples
- WAF prompt injection protection
- Multi-environment deployments

### Customer Demos
Deploy quickly for:
- TAM Summit presentations
- Customer workshops
- Proof of concepts
- Architecture reviews

### Production Deployments
Customize for:
- Real team structures
- Production Bedrock models
- Specific guardrail policies
- Custom WAF rules
- Cost allocation tags

---

## 🚀 Next Steps

### For Demo #1 (AgentCore Gateway)
1. Deploy infrastructure: `./deploy.sh --demo1-only`
2. Deploy AgentCore Gateway: `cd DemoMcpGateway/agentcore && agentcore deploy`
3. Configure VS Code: Update `vscode-config/mcp.json` with registry URL
4. Test in GitHub Copilot

### For Demo #2 (Browser Chat)
1. Deploy infrastructure: `./deploy.sh --demo2-only`
2. Update chatbox HTML with API endpoint and keys from outputs
3. Open chatbox in browser
4. Test team-based model access

### For Both Demos
1. Deploy infrastructure: `./deploy.sh`
2. Follow post-deployment steps in outputs
3. Monitor CloudWatch dashboard
4. Review logs for team attribution

---

## 📞 Support

- **GitHub Issues:** Report bugs or request features
- **AWS Support:** Contact your AWS account team for AgentCore preview access
- **Documentation:** See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

---

## 📄 License

MIT-0 License. See [../LICENSE](../LICENSE).

---

**Summary:**

This infrastructure implementation provides **complete, production-ready CloudFormation** for both Bedrock Governance demos with **one-command deployment**. It includes API Gateway, Lambda, WAF, Guardrails, IAM roles, CloudWatch monitoring, and comprehensive documentation.

**Deploy in 5 minutes:** `./deploy.sh` 🚀
