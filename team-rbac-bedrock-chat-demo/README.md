# Team-Based RBAC with AWS Bedrock Chat Demo

> **LLM Gateway with team-based access control, cost tracking, and guardrails**

This demo shows how to build a centralized LLM gateway that controls which teams can access which Bedrock models, tracks costs per team, and enforces content guardrails - all without changing application code.

## What This Demo Shows

### 1. **API Gateway + Lambda Proxy Architecture**
```
Browser → API Gateway (REST + API Keys) → Lambda Proxy → AWS Bedrock
              ↓
      (API key identifies team)
      (Model access enforcement)
      (Structured audit logging)
```

The Lambda proxy:
- Resolves team identity from the API key (server-side, not client-claimed)
- Checks if the team is allowed to use the requested model
- Calls Bedrock directly using the Lambda execution role
- Logs structured audit events (team, model, tokens, latency) to CloudWatch
- Returns responses to the client

### 2. **Team-Based Model Access Control**
- **Team Alpha**: Can use Haiku and Sonnet models (balanced capability + cost)
- **Team Beta**: Can only use Haiku (cost-optimized)
- Access denied at runtime if team tries unauthorized model

### 3. **Cost Tracking by Team**
- Every Bedrock API call is logged with team identifier and token counts
- Use CloudWatch Insights to query costs per team
- Real-time cost display in the UI

> **Note:** This demo uses structured CloudWatch logging for cost attribution.
> For AWS Cost Explorer integration, you'd need cost allocation tags on the
> Bedrock calls — see [COST_EXPLORER_SETUP.md](COST_EXPLORER_SETUP.md) for guidance.

### 4. **Content Guardrails** (Optional)
- Multi-lingual content filtering
- Swedish word false positive demonstration
- STRICT mode blocks innocent words, LENIENT mode uses context

---

## Quick Start

### Prerequisites
- AWS account with Bedrock access
- Python 3.11+
- AWS CLI configured
- Node.js 18+ (optional, for local server)

### Deploy Infrastructure

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for complete step-by-step instructions.

**Summary:**
```bash
# 1. Deploy CloudFormation stack
cd infrastructure/cloudformation
aws cloudformation create-stack \
  --stack-name llm-gateway-demo \
  --template-body file://main-stack.yaml \
  --capabilities CAPABILITY_IAM

# 2. Deploy Lambda functions
cd ../../lambda/gateway-proxy
./deploy.sh

# 3. Get API Gateway URL and API keys from CloudFormation outputs
aws cloudformation describe-stacks \
  --stack-name llm-gateway-demo \
  --query 'Stacks[0].Outputs'

# 4. Update chatbox.html with your values
# - API_ENDPOINT: Your API Gateway URL
# - TEAMS.team-alpha.apiKey: Team Alpha API key
# - TEAMS.team-beta.apiKey: Team Beta API key

# 5. Open chatbox.html in browser
open chatbox.html
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (chatbox.html)                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Team Alpha: API Key = abc123                       │   │
│  │  Team Beta:  API Key = xyz789                       │   │
│  └────────────────┬────────────────────────────────────┘   │
└───────────────────┼─────────────────────────────────────────┘
                    │ HTTPS + x-api-key header
                    ▼
        ┌───────────────────────────┐
        │   API Gateway             │
        │   • API key validation    │
        │   • Usage plans per team  │
        │   • CloudWatch logging    │
        └───────────┬───────────────┘
                    │
                    ▼
        ┌───────────────────────────────────────┐
        │  Lambda Proxy (gateway-proxy)         │
        │  ┌─────────────────────────────────┐  │
        │  │  1. Resolve team from API key   │  │
        │  │  2. Check model permissions     │  │
        │  │  3. Call Bedrock (invoke_model)  │  │
        │  │  4. Log audit event (team/model) │  │
        │  │  5. Apply guardrails (optional) │  │
        │  └─────────────────────────────────┘  │
        └───────────┬───────────────────────────┘
                    │
        ┌───────────┴────────┬──────────┬────────┐
        ▼                    ▼          ▼        ▼
    ┌────────┐          ┌────────┐ ┌──────┐ ┌──────┐
    │Claude  │          │Claude  │ │Claude│ │Titan │
    │Haiku   │          │Sonnet  │ │Opus  │ │...   │
    └────────┘          └────────┘ └──────┘ └──────┘
         ↓                   ↓         ↓        ↓
    (Team Alpha + Team Beta access)   (Denied)
```

---

## Repository Structure

```
team-rbac-bedrock-chat-demo/
├── README.md                           # ← You are here
├── DEPLOYMENT.md                       # Step-by-step setup guide
├── DEMO.md                             # Testing scenarios
│
├── chatbox.html                        # Browser-based chat UI
│
├── lambda/
│   ├── gateway-proxy/                  # Lambda proxy (API Gateway → Bedrock)
│   │   ├── lambda_function.py          # Main handler with IAM role assumption
│   │   ├── requirements.txt            # boto3, requests
│   │   └── deploy.sh                   # Deployment script
│   │
│   └── products-mcp-with-guardrail/    # Guardrails demo Lambda
│       ├── lambda_function.py          # MCP with Bedrock guardrails
│       ├── deploy-strict.sh            # Deploy with STRICT guardrail
│       └── deploy-lenient.sh           # Deploy without guardrail
│
├── infrastructure/cloudformation/
│   ├── main-stack.yaml                 # Complete infrastructure
│   │   • API Gateway with usage plans
│   │   • Lambda functions
│   │   • IAM roles (Team Alpha, Team Beta)
│   │   • DynamoDB tables (optional)
│   │   • CloudWatch logs
│   └── iam-roles.yaml                  # IAM role templates
│
├── COST_EXPLORER_SETUP.md              # Configure per-team cost tracking
├── GUARDRAIL_DEMO.md                   # Multi-lingual content filtering
├── GUARDRAIL_COMPARISON.md             # STRICT vs LENIENT modes
├── FRONTEND_SETUP.md                   # UI configuration
└── IAM_PRINCIPAL_COST_TRACKING_SUMMARY.md  # Cost attribution guide
```

---

## Use Cases

### 1. **Multi-Team Organization**
- Engineering team: Full model access
- Data science team: Sonnet + Haiku only
- Support team: Haiku only (cost control)

### 2. **Cost Control & Chargeback**
- Track which team is using which models
- Generate monthly invoices per team
- Set budgets and alerts per team

### 3. **Compliance & Governance**
- Centralized guardrails for all teams
- Audit logs showing team + model + prompt
- No sensitive data in application code

### 4. **Gradual Model Rollout**
- Start all teams on Haiku
- Promote alpha teams to Sonnet after testing
- Restrict Opus to specific high-value use cases

---

## Key Features

### ✅ Centralized Gateway
- Single API endpoint for all teams
- No Bedrock credentials in application code
- Easy to add new teams or models

### ✅ Team-Based Policies
- API key → team mapping enforced server-side in Lambda
- Model permissions checked per team via environment config
- Deny at the gateway, not in the app

### ✅ Cost Attribution
- Structured JSON logs with team, model, and token counts per request
- Query with CloudWatch Insights for per-team cost reports
- Real-time token counting in UI

### ✅ Content Guardrails
- Optional Bedrock Guardrails integration
- Multi-lingual false positive demonstration
- Configurable per team or per model

---

## Configuration

### Team Setup

Edit `chatbox.html` after deployment:

```javascript
const API_ENDPOINT = "https://abc123.execute-api.us-east-1.amazonaws.com/prod/invoke";

const TEAMS = {
    'team-alpha': {
        name: "Team Alpha",
        apiKey: "YOUR_TEAM_ALPHA_API_KEY_HERE",  // From CloudFormation
        color: "#232F3E"
    },
    'team-beta': {
        name: "Team Beta",
        apiKey: "YOUR_TEAM_BETA_API_KEY_HERE",   // From CloudFormation
        color: "#FF9900"
    }
};

const TEAM_MODEL_PERMISSIONS = {
    'team-alpha': [
        'us.anthropic.claude-haiku-4-5-20251001-v1:0',
        'us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    ],
    'team-beta': [
        'us.anthropic.claude-haiku-4-5-20251001-v1:0'
    ]
};
```

### Model Permissions

To change which models a team can access:

1. **Update Lambda environment variables** (for runtime enforcement):
   ```bash
   aws lambda update-function-configuration \
     --function-name gateway-proxy \
     --environment Variables={TEAM_ALPHA_MODELS="haiku,sonnet,opus"}
   ```

2. **Update IAM role policies** (for AWS-level enforcement):
   ```json
   {
       "Effect": "Allow",
       "Action": "bedrock:InvokeModel",
       "Resource": [
           "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku*",
           "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet*"
       ]
   }
   ```

3. **Update UI** (`chatbox.html`):
   ```javascript
   const TEAM_MODEL_PERMISSIONS = {
       'team-alpha': ['haiku', 'sonnet', 'opus']
   };
   ```

---

## Testing

See **[DEMO.md](DEMO.md)** for complete testing scenarios.

**Quick tests:**

1. **Team Alpha** → Try Haiku (✅ allowed), Sonnet (✅ allowed), Opus (❌ denied)
2. **Team Beta** → Try Haiku (✅ allowed), Sonnet (❌ denied)
3. Check CloudWatch logs for team IAM principal tags
4. View AWS Cost Explorer filtered by team

---

## Troubleshooting

### "403 Forbidden" when calling API
- Check API key is correct and matches what CloudFormation created
- Verify usage plan is attached to API key
- Check Lambda can be invoked by API Gateway (check permissions)

### "Model access denied"
- Check Lambda environment variables (`TEAM_ALPHA_MODELS`, `TEAM_BETA_MODELS`)
- Verify Lambda IAM role has `bedrock:InvokeModel` for that model ARN
- Check model ID format (e.g., `us.anthropic.claude-haiku-4-5-20251001-v1:0`)

### Costs not showing per team
- Query CloudWatch Insights on the Lambda log group:
  `fields team, model, input_tokens, output_tokens | filter status = 'success' | stats sum(input_tokens) by team`
- For AWS Cost Explorer integration, see [COST_EXPLORER_SETUP.md](COST_EXPLORER_SETUP.md)

### Guardrails not blocking content
- Verify guardrail ID and version in Lambda environment
- Check guardrail is in ENABLED state (not DRAFT)
- Ensure Lambda role has `bedrock:ApplyGuardrail` permission

---

## Security Considerations

- ✅ API keys validated by API Gateway usage plans
- ✅ Team identity resolved server-side from API key (not trusted from client body)
- ✅ All requests logged to CloudWatch with team attribution
- ✅ No Bedrock credentials in browser or application code
- ✅ TLS 1.2+ for all API Gateway connections
- ✅ Lambda IAM role scoped to specific Bedrock model ARNs
- ⚠️ Enable API Gateway throttling per team (usage plans configured)
- ⚠️ For production: store API key→team mapping in Secrets Manager or DynamoDB

---

## Cost Estimate

**For 10 teams, 1000 requests/day each:**

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| API Gateway | 300K requests | ~$3.00 |
| Lambda (proxy) | 300K invocations | ~$1.00 |
| CloudWatch Logs | 5 GB | ~$2.50 |
| Bedrock (Haiku 4.5) | 300K requests × 1K tokens | ~$300 |
| **Total** | | **~$306.50/month** |

*Bedrock is 97% of costs - gateway overhead is minimal. Pricing: Haiku 4.5 at $1/$5 per 1M input/output tokens.*

---

## Next Steps

- Add more teams → Just create IAM role + API key
- Add new models → Update IAM policies + Lambda env vars
- Add guardrails → Set `GUARDRAIL_ID` in Lambda env
- Monitor costs → Enable Cost Allocation Tags

---

## Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [API Gateway Usage Plans](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-usage-plans.html)
- [Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
- [Cost Allocation Tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)

---

**Built to demonstrate centralized LLM governance at scale.**
