# Frontend Setup Instructions

## Chatbox Setup

### Step 1: Deploy Infrastructure

Deploy the CloudFormation stack first (see [DEPLOYMENT.md](DEPLOYMENT.md)):

```bash
aws cloudformation deploy \
  --template-file infrastructure/cloudformation/main-stack.yaml \
  --stack-name llm-gateway-demo \
  --parameter-overrides S3ArtifactBucket=<YOUR_BUCKET> \
  --capabilities CAPABILITY_NAMED_IAM
```

### Step 2: Get API Endpoint and Keys

```bash
# Get the API endpoint
aws cloudformation describe-stacks --stack-name llm-gateway-demo \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text

# Get Team Alpha API key value
ALPHA_KEY_ID=$(aws cloudformation describe-stacks --stack-name llm-gateway-demo \
  --query 'Stacks[0].Outputs[?OutputKey==`TeamAlphaApiKeyId`].OutputValue' --output text)
aws apigateway get-api-key --api-key $ALPHA_KEY_ID --include-value --query value --output text

# Get Team Beta API key value
BETA_KEY_ID=$(aws cloudformation describe-stacks --stack-name llm-gateway-demo \
  --query 'Stacks[0].Outputs[?OutputKey==`TeamBetaApiKeyId`].OutputValue' --output text)
aws apigateway get-api-key --api-key $BETA_KEY_ID --include-value --query value --output text
```

### Step 3: Update chatbox.html

Open `chatbox.html` and replace the placeholder values:

```javascript
const API_ENDPOINT = "https://<YOUR_API_ID>.execute-api.us-east-1.amazonaws.com/prod/invoke";

const TEAMS = {
    'team-alpha': {
        name: "Team Alpha",
        apiKey: "<YOUR_TEAM_ALPHA_API_KEY>",  // From Step 2
        color: "#232F3E"
    },
    'team-beta': {
        name: "Team Beta",
        apiKey: "<YOUR_TEAM_BETA_API_KEY>",   // From Step 2
        color: "#FF9900"
    }
};
```

### Step 4: Open in Browser

```bash
open chatbox.html
```

No web server needed — it's a static HTML file that calls API Gateway directly.

---

## Optional: Guardrails Integration

If you want to add Bedrock Guardrails for PII filtering:

### Create a Guardrail

```bash
aws bedrock create-guardrail \
  --name "pii-filter" \
  --sensitive-information-policy-config '{
    "piiEntitiesConfig": [
      {"type": "NAME", "action": "BLOCK"},
      {"type": "EMAIL", "action": "ANONYMIZE"},
      {"type": "PHONE", "action": "ANONYMIZE"},
      {"type": "SSN", "action": "BLOCK"},
      {"type": "CREDIT_DEBIT_CARD_NUMBER", "action": "BLOCK"}
    ]
  }' \
  --blocked-input-messaging "Content blocked: PII detected" \
  --blocked-output-messaging "Response blocked: contains PII"
```

### Update CloudFormation

Redeploy with guardrail enabled:

```bash
aws cloudformation deploy \
  --template-file infrastructure/cloudformation/main-stack.yaml \
  --stack-name llm-gateway-demo \
  --parameter-overrides \
    S3ArtifactBucket=<YOUR_BUCKET> \
    EnableGuardrail=true \
    GuardrailId=<YOUR_GUARDRAIL_ID> \
  --capabilities CAPABILITY_NAMED_IAM
```

### Test PII Blocking

In the chatbox, try sending:
- "My BankID personal number is 199001011234" → ❌ Blocked (PII)
- "How does BankID authentication work?" → ✅ Allowed (general question)
- "Call me at +46 70 123 4567" → ❌ Blocked (phone number)

---

## Architecture

```
Browser (chatbox.html)
    ↓ HTTPS + x-api-key
API Gateway (REST)
    ↓ Validates API key + usage plan
Lambda Proxy
    ↓ Team-based model governance
    ↓ Optional: bedrock:ApplyGuardrail
AWS Bedrock
    ↓ Model inference
Response → Browser
```

---

## Troubleshooting

### "403 Forbidden"
- Check that your API key is correct in chatbox.html
- Verify the API key is associated with a usage plan
- If testing model access: Team Beta cannot use Sonnet (only Haiku)

### "Network Error" or CORS issues
- Verify the API endpoint URL includes `/prod/invoke`
- Check that the OPTIONS method is configured for CORS (included in CloudFormation)

### No response from model
- Verify Bedrock model access is enabled in your account
- Check CloudWatch logs: `/aws/lambda/<stack-name>-proxy`

---

## CloudWatch Insights Queries

After running the demo, use these queries to analyze usage:

```sql
-- Cost attribution by team
fields @timestamp, team, model, input_tokens, output_tokens
| filter status = 'success'
| stats sum(input_tokens) as total_input, sum(output_tokens) as total_output by team

-- Denied model access attempts
fields @timestamp, team, model, status
| filter status = 'model_denied'
| stats count() by team, model

-- Latency analysis
fields @timestamp, team, model, latency_seconds
| filter status = 'success'
| stats avg(latency_seconds), max(latency_seconds), p95(latency_seconds) by model
```

---

**Files:**
- Frontend: `chatbox.html`
- Lambda: `lambda/gateway-proxy/lambda_function.py`
- Infrastructure: `infrastructure/cloudformation/main-stack.yaml`
