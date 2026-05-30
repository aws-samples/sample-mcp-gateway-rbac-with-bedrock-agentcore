# Deployment Guide - Team-Based RBAC LLM Gateway

This guide walks you through deploying the complete LLM gateway from scratch.

## Overview

You'll deploy:
1. Lambda proxy function (Python code) - **Required**
2. CloudFormation stack (API Gateway, IAM roles) - **Required**
3. Browser chatbox UI (configure with API endpoint) - **Required**
4. Optional MCP Lambda functions (for guardrail testing) - **Optional**

**Total time:** ~15 minutes (minimal deployment), ~30 minutes (with optional MCP servers)

### What's Required vs Optional

**Minimal Deployment (Core Demo 2):**
- ✅ Lambda proxy function (gateway-proxy)
- ✅ API Gateway
- ✅ Chatbox UI
- ✅ Team-based model access control

**Optional Components (for Guardrail Testing):**
- ⚪ Ecommerce MCP Lambda
- ⚪ Products MCP Lambda (with Bedrock Guardrails)
- ⚪ Orders MCP Lambda
- ⚪ AppConfig (feature flags)

Most users only need the **minimal deployment** to test team-based model access.

---

## Prerequisites

- AWS CLI configured with admin credentials
- Python 3.11+
- AWS account with Bedrock access
- Basic familiarity with AWS Lambda and API Gateway

---

## Step 1: Package Lambda Function

The Lambda proxy needs to be packaged before deployment.

```bash
cd team-rbac-bedrock-chat-demo/lambda/gateway-proxy

# Create deployment package
zip function.zip lambda_function.py

echo "✅ Lambda package created: function.zip"
```

---

## Step 2: Upload Lambda Code to S3 (One-Time Setup)

CloudFormation needs Lambda code in S3. Create a bucket if you don't have one:

```bash
# Set your bucket name (must be globally unique)
BUCKET_NAME="my-llm-gateway-artifacts-$(date +%s)"
REGION="us-east-1"

# Create S3 bucket
aws s3 mb s3://${BUCKET_NAME} --region ${REGION}

# Upload Lambda code
aws s3 cp function.zip s3://${BUCKET_NAME}/lambda/gateway-proxy.zip

echo "✅ Lambda code uploaded to s3://${BUCKET_NAME}/lambda/gateway-proxy.zip"

# Note: If you're deploying with MCP servers (ecommerce, products, orders),
# package and upload those as well:
# aws s3 cp ecommerce-mcp.zip s3://${BUCKET_NAME}/lambda/ecommerce-mcp.zip
# aws s3 cp products-mcp.zip s3://${BUCKET_NAME}/lambda/products-mcp.zip
# aws s3 cp orders-mcp.zip s3://${BUCKET_NAME}/lambda/orders-mcp.zip
```

**Save this bucket name - you'll need it in Step 3!**

---

## Step 3: Deploy CloudFormation Stack

Deploy the infrastructure stack:

```bash
cd ../../infrastructure/cloudformation

# Use the bucket name from Step 2
BUCKET_NAME="your-bucket-name-here"

# Deploy stack (minimal - just proxy function)
aws cloudformation create-stack \
  --stack-name llm-gateway-demo \
  --template-body file://main-stack.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameters \
    ParameterKey=S3ArtifactBucket,ParameterValue=${BUCKET_NAME} \
    ParameterKey=ProxyCodeKey,ParameterValue=lambda/gateway-proxy.zip \
    ParameterKey=EnableGuardrail,ParameterValue=false \
  --region us-east-1

# If deploying with MCP servers, add these parameters:
#    ParameterKey=EcommerceMcpCodeKey,ParameterValue=lambda/ecommerce-mcp.zip \
#    ParameterKey=ProductsMcpCodeKey,ParameterValue=lambda/products-mcp.zip \
#    ParameterKey=OrdersMcpCodeKey,ParameterValue=lambda/orders-mcp.zip \
#    ParameterKey=EnableGuardrail,ParameterValue=true \

# Wait for stack creation (takes ~3-5 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name llm-gateway-demo \
  --region us-east-1

echo "✅ CloudFormation stack created!"
```

### If Stack Creation Fails

Check the error:
```bash
aws cloudformation describe-stack-events \
  --stack-name llm-gateway-demo \
  --region us-east-1 \
  --max-items 5
```

Common issues:
- **"S3 bucket does not exist"** → Check bucket name is correct
- **"Access Denied"** → Check your AWS credentials have admin permissions
- **"Bedrock not available"** → Check Bedrock is enabled in your region

---

## Step 4: Get API Gateway Endpoint

Retrieve the API Gateway URL from CloudFormation outputs:

```bash
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name llm-gateway-demo \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text)

echo "API Gateway Endpoint: $API_ENDPOINT"

# Save this - you'll need it for the chatbox!
```

**Example output:** `https://abc123xyz.execute-api.us-east-1.amazonaws.com/mcp`

---

## Step 5: Configure Chatbox UI

The current template uses **HTTP API Gateway** (not REST API), which **does not support API keys**.

You have two options:

### Option A: Use Without Authentication (Quick Test)

Update `chatbox.html` to remove API key requirement:

```bash
cd ../../

# Update API endpoint
sed -i.bak "s|const API_ENDPOINT = .*|const API_ENDPOINT = \"${API_ENDPOINT}\";|g" chatbox.html

# Since HTTP API doesn't use API keys, remove the x-api-key header
# Edit chatbox.html manually:
# - Find the fetch() call around line 857
# - Remove the 'x-api-key': team.apiKey header
# OR just test with placeholder keys (they won't be validated)
```

### Option B: Add REST API with API Keys (Recommended for Production)

To enable API key authentication, you need to:

1. **Switch to REST API Gateway** in CloudFormation template, or
2. **Add Amazon Cognito** for authentication, or
3. **Use IAM authentication** (requires AWS credentials in browser)

For this demo, we'll keep it simple and use **Option A** (no authentication).

---

## Step 6: Test the Deployment

### Test 1: Command Line Test

```bash
# Test the Lambda directly
curl -X POST "${API_ENDPOINT}" \
  -H "Content-Type: application/json" \
  -d '{
    "team": "team-alpha",
    "prompt": "Say hello in 5 words",
    "model_id": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "max_tokens": 50
  }'

# Expected: JSON response with "response" field containing Claude's answer
```

If you get a response, the Lambda and Bedrock integration works! ✅

### Test 2: Open Chatbox

```bash
# Open in browser
open chatbox.html

# Or use a local server
python3 -m http.server 8000
# Then open: http://localhost:8000/chatbox.html
```

**In the browser:**
1. Click "Team Alpha"
2. Type a message
3. Click Send
4. You should get a response from Claude Haiku

---

## Step 7: Verify Team Model Permissions

The Lambda enforces model permissions via environment variables:
- **Team Alpha:** Can use Haiku and Sonnet
- **Team Beta:** Can only use Haiku

Test this by trying different models in the chatbox UI.

---

## Troubleshooting

### "AccessDeniedException: bedrock:InvokeModel"

**Cause:** Lambda execution role doesn't have Bedrock permissions.

**Fix:**
```bash
# Check Lambda role
aws cloudformation describe-stacks \
  --stack-name llm-gateway-demo \
  --query 'Stacks[0].Outputs[?OutputKey==`ProxyFunctionArn`].OutputValue' \
  --output text

# The role should have bedrock:InvokeModel permission
# If not, update the CloudFormation template and redeploy
```

---

### "Internal Server Error" from Lambda

**Cause:** Check CloudWatch Logs for detailed error.

**Fix:**
```bash
# Get Lambda function name
FUNCTION_NAME="llm-gateway-demo-gateway-proxy"

# View recent logs
aws logs tail /aws/lambda/${FUNCTION_NAME} --follow
```

Common errors:
- `ModuleNotFoundError: No module named 'boto3'` → Lambda package missing dependencies
- `Environment variable not set` → Check Lambda environment variables

---

### Chatbox shows "Network Error"

**Cause:** CORS issue or wrong API endpoint.

**Fix:**
1. Check API endpoint in `chatbox.html` matches CloudFormation output
2. Check browser console (F12) for detailed error
3. Verify CORS is enabled in API Gateway

---

### "Model not allowed" error

**Cause:** Lambda environment variables not set correctly.

**Fix:**
```bash
# Check Lambda environment variables
aws lambda get-function-configuration \
  --function-name llm-gateway-demo-gateway-proxy \
  --query 'Environment.Variables'

# Should show:
# {
#   "TEAM_ALPHA_MODELS": "haiku,sonnet",
#   "TEAM_BETA_MODELS": "haiku"
# }

# If wrong, update and redeploy CloudFormation stack
```

---

## Cleanup

To delete all resources:

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack \
  --stack-name llm-gateway-demo \
  --region us-east-1

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name llm-gateway-demo \
  --region us-east-1

# Delete S3 bucket
aws s3 rm s3://${BUCKET_NAME}/lambda/gateway-proxy.zip
aws s3 rb s3://${BUCKET_NAME}

echo "✅ All resources deleted!"
```

---

## Known Limitations

### No API Key Authentication

The current CloudFormation template uses **HTTP API Gateway**, which does **not support API keys**.

**Impact:**
- Anyone with the API endpoint can call your Lambda
- No per-team rate limiting
- No usage tracking per API key

**For production use**, consider:
1. **Switch to REST API Gateway** (supports API keys and usage plans)
2. **Add Amazon Cognito** for user authentication
3. **Use IAM authentication** with AWS credentials
4. **Add AWS WAF** for IP-based access control

---

### Hardcoded Team Mapping

The Lambda has a placeholder `map_api_key_to_team()` function that always returns `"team-alpha"`.

**For production:**
1. Store API key → team mapping in **AWS Secrets Manager** or **DynamoDB**
2. Update the `map_api_key_to_team()` function to read from that storage
3. Implement proper API key validation

**Example with Secrets Manager:**
```python
def map_api_key_to_team(api_key):
    secrets = boto3.client('secretsmanager')
    mapping = json.loads(
        secrets.get_secret_value(SecretId='api-key-mapping')['SecretString']
    )
    return mapping.get(api_key, 'unknown')
```

---

### Missing Cost Attribution

To enable per-team cost tracking in AWS Cost Explorer:

1. **Enable Cost Allocation Tags:**
   ```bash
   aws ce create-cost-category-definition \
     --name "Team" \
     --rules '[{"Value": "team-alpha", "Rule": {...}}]'
   ```

2. **Tag Bedrock requests** with team identifier (requires custom implementation)

3. **Wait 24 hours** for Cost Explorer data

See [COST_EXPLORER_SETUP.md](COST_EXPLORER_SETUP.md) for detailed instructions.

---

## Next Steps

- Read [DEMO.md](DEMO.md) for testing scenarios
- Add API key authentication for production
- Set up CloudWatch alarms for Lambda errors
- Configure AWS Budgets for cost alerts
- Review CloudWatch logs for audit trail

---

## Production Checklist

Before deploying to production:

- [ ] Add REST API Gateway with API keys (or Cognito auth)
- [ ] Store API key mapping in Secrets Manager (not hardcoded)
- [ ] Enable CloudWatch log retention (default is forever)
- [ ] Set up CloudWatch alarms for Lambda errors
- [ ] Configure AWS WAF for DDoS protection
- [ ] Enable AWS CloudTrail for audit logging
- [ ] Set up AWS Budgets for cost alerts
- [ ] Test model permission enforcement thoroughly
- [ ] Document incident response procedures

---

**Deployment complete! 🎉**

Your LLM gateway is now running with direct Bedrock API integration.

**Note:** This demo shows the architecture pattern. For production use, add proper authentication, monitoring, and error handling.
