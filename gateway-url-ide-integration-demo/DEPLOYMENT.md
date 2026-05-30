# Deployment Guide - AgentCore Gateway with Lambda MCPs

This guide walks you through deploying the complete demo from scratch.

## Overview

You'll deploy in this order:
1. **Lambda MCPs** (ecommerce, products, orders, jira) - The backend services
2. **AgentCore Gateway** - The centralized authorization layer
3. **VS Code Integration** - Connect GitHub Copilot to the gateway

## Prerequisites

- AWS CLI configured with admin credentials
- Node.js 18+ (for AgentCore CLI)
- Python 3.11+
- AWS account with Bedrock AgentCore access (⚠️ AgentCore is in preview - contact AWS)

## Step 1: Create Lambda Execution Role

The Lambda functions need an IAM role to execute. Create it manually:

```bash
# Create trust policy
cat > /tmp/lambda-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create the role
aws iam create-role \
  --role-name mcp-lambda-execution-role \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json

# Attach basic Lambda execution policy
aws iam attach-role-policy \
  --role-name mcp-lambda-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Wait for role to be ready
sleep 10

echo "✅ Lambda execution role created: mcp-lambda-execution-role"
```

## Step 2: Deploy Lambda MCPs

Deploy each Lambda function that will be exposed as MCP tools:

```bash
cd lambda/mcp-servers

# Get your AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-us-east-1}
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/mcp-lambda-execution-role"

echo "Deploying Lambda MCPs..."
echo "Region: $REGION"
echo "Role: $ROLE_ARN"
echo ""

# Deploy Customers MCP (ecommerce-mcp)
cd ecommerce-mcp
zip -q function.zip lambda_function.py

aws lambda create-function \
  --function-name demo-ecommerce-mcp \
  --runtime python3.11 \
  --role "$ROLE_ARN" \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 30 \
  --memory-size 256 \
  --region "$REGION"

rm function.zip
echo "✅ Deployed: demo-ecommerce-mcp"
cd ..

# Deploy Products MCP
cd products-mcp
zip -q function.zip lambda_function.py

aws lambda create-function \
  --function-name demo-products-mcp \
  --runtime python3.11 \
  --role "$ROLE_ARN" \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 30 \
  --memory-size 256 \
  --region "$REGION"

rm function.zip
echo "✅ Deployed: demo-products-mcp"
cd ..

# Deploy Orders MCP
cd orders-mcp
zip -q function.zip lambda_function.py

aws lambda create-function \
  --function-name demo-orders-mcp \
  --runtime python3.11 \
  --role "$ROLE_ARN" \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 30 \
  --memory-size 256 \
  --region "$REGION"

rm function.zip
echo "✅ Deployed: demo-orders-mcp"
cd ..

# Deploy Jira MCP
cd jira-mcp
zip -q function.zip lambda_function.py

aws lambda create-function \
  --function-name demo-jira-mcp \
  --runtime python3.11 \
  --role "$ROLE_ARN" \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 30 \
  --memory-size 256 \
  --region "$REGION"

rm function.zip
echo "✅ Deployed: demo-jira-mcp"
cd ..

echo ""
echo "✅ All Lambda MCPs deployed successfully!"
```

## Step 3: Update AgentCore Configuration

Update the Lambda ARNs in the AgentCore configuration:

```bash
cd ../../DemoMcpGateway/agentcore

# Get your AWS account ID and region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-us-east-1}

# Update agentcore.json with actual values
sed -i.bak "s/<REGION>/$REGION/g" agentcore.json
sed -i.bak "s/<ACCOUNT_ID>/$ACCOUNT_ID/g" agentcore.json

echo "✅ Updated agentcore.json with your account ID and region"

# Create aws-targets.json from template
cat > aws-targets.json <<EOF
[
  {
    "name": "default",
    "account": "$ACCOUNT_ID",
    "region": "$REGION"
  }
]
EOF

echo "✅ Created aws-targets.json"
```

**For macOS users:** Use `sed -i '' "s/<REGION>/$REGION/g" agentcore.json` instead.

## Step 4: Deploy AgentCore Gateway

Now deploy the gateway that will wrap your Lambda MCPs:

```bash
# Install AgentCore CLI globally
npm install -g @aws/agentcore-cli

# Verify installation
agentcore --version

# Install CDK dependencies (REQUIRED - first time only)
cd cdk
npm install
cd ..

# Deploy the gateway
agentcore deploy

# The output will show your Gateway URL like:
# https://abc123.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp
# 
# SAVE THIS URL - you'll need it for VS Code configuration
```

The gateway will:
- Register all 4 Lambda MCPs as tools
- Attach Cedar RBAC policies
- Enable AWS IAM authorization

## Step 5: Update Cedar Policy with Gateway ARN

After deployment, update the Cedar policy with the actual Gateway ARN:

```bash
# Get the Gateway ARN from deployed-state.json
GATEWAY_ARN=$(cat .cli/deployed-state.json | jq -r '.gateways[0].arn')

# Update the Cedar policy
sed -i.bak "s|<YOUR_GATEWAY_ARN>|$GATEWAY_ARN|g" ../policies/rbac-policy.cedar

echo "✅ Updated rbac-policy.cedar with Gateway ARN: $GATEWAY_ARN"

# Redeploy to apply the updated policy
agentcore deploy
```

**For macOS users:** Use `sed -i '' "s|<YOUR_GATEWAY_ARN>|$GATEWAY_ARN|g" ../policies/rbac-policy.cedar`

## Step 6: Create Test IAM Users

Create two IAM users with different permission levels:

```bash
cd ../../scripts

# Run the user creation script (if available)
# Or create manually:

# Create ReadOnly user
aws iam create-user --user-name test-developer-readonly
aws iam tag-user \
  --user-name test-developer-readonly \
  --tags Key=group,Value=ReadOnly

# Create FullAccess user
aws iam create-user --user-name test-developer-fullaccess
aws iam tag-user \
  --user-name test-developer-fullaccess \
  --tags Key=group,Value=FullAccess

# Attach gateway access policy to both users
aws iam put-user-policy \
  --user-name test-developer-readonly \
  --policy-name gateway-access \
  --policy-document file://../iam-policies/simple-gateway-access.json

aws iam put-user-policy \
  --user-name test-developer-fullaccess \
  --policy-name gateway-access \
  --policy-document file://../iam-policies/simple-gateway-access.json

# Create access keys
aws iam create-access-key --user-name test-developer-readonly
aws iam create-access-key --user-name test-developer-fullaccess

# Save the access keys - you'll need to add them to ~/.aws/credentials
```

## Step 7: Configure AWS Credentials

Add the IAM user credentials to `~/.aws/credentials`:

```ini
[test-readonly]
aws_access_key_id = AKIA...  # From previous step
aws_secret_access_key = ...
region = us-east-1

[test-fullaccess]
aws_access_key_id = AKIA...  # From previous step
aws_secret_access_key = ...
region = us-east-1
```

## Step 8: Configure VS Code

See [VSCODE_SETUP.md](VSCODE_SETUP.md) for detailed VS Code and GitHub Copilot configuration.

Quick summary:
```bash
# Copy MCP config
cp vscode-config/mcp.json ~/Library/Application\ Support/Code/User/mcp.json

# Edit mcp.json and replace <YOUR_GATEWAY_URL> with the URL from Step 4

# Launch VS Code with a specific profile
export AWS_PROFILE=test-readonly
code .
```

## Verification

Test the deployment:

```bash
# Test ReadOnly user can list customers
export AWS_PROFILE=test-readonly
aws lambda invoke \
  --function-name demo-ecommerce-mcp \
  --cli-binary-format raw-in-base64-out \
  --payload '{}' \
  /tmp/output.json && cat /tmp/output.json
```

## Troubleshooting

### "Lambda function not found"
Make sure you deployed all Lambda functions in Step 2.

### "Access Denied" when deploying gateway
Your AWS credentials need permissions for:
- Lambda (invoke functions)
- Bedrock AgentCore (create/update gateway)
- IAM (read tags)

### "Policy evaluation failed"
Check that:
1. Cedar policy has the correct Gateway ARN
2. IAM users have the correct tags (`group=ReadOnly` or `group=FullAccess`)
3. Gateway access policy is attached to IAM users

### Gateway URL not showing
Run `cat .cli/deployed-state.json | jq -r '.gateways[0].url'` to retrieve it.

## Cleanup

To delete all resources:

```bash
# Delete Lambda functions
aws lambda delete-function --function-name demo-ecommerce-mcp
aws lambda delete-function --function-name demo-products-mcp
aws lambda delete-function --function-name demo-orders-mcp
aws lambda delete-function --function-name demo-jira-mcp

# Delete AgentCore Gateway
cd DemoMcpGateway/agentcore
agentcore destroy

# Delete IAM users
aws iam delete-access-key --user-name test-developer-readonly --access-key-id <KEY_ID>
aws iam delete-user-policy --user-name test-developer-readonly --policy-name gateway-access
aws iam delete-user --user-name test-developer-readonly

aws iam delete-access-key --user-name test-developer-fullaccess --access-key-id <KEY_ID>
aws iam delete-user-policy --user-name test-developer-fullaccess --policy-name gateway-access
aws iam delete-user --user-name test-developer-fullaccess

# Delete IAM role
aws iam detach-role-policy --role-name mcp-lambda-execution-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name mcp-lambda-execution-role
```

## Next Steps

- Read [DEMO.md](DEMO.md) for testing scenarios
- Review [VSCODE_SETUP.md](VSCODE_SETUP.md) for IDE integration details
- Explore Cedar policies in `DemoMcpGateway/policies/` to customize RBAC rules
