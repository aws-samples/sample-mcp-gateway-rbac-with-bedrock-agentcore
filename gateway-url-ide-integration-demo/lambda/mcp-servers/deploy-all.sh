#!/bin/bash
# Deploy all MCP Server Lambda functions

set -e  # Exit on error

REGION=${AWS_REGION:-us-east-1}
STACK_NAME="mcp-gateway-demo"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Deploy MCP Servers - Bedrock AgentCore Demo         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Region: $REGION"
echo "Stack: $STACK_NAME"
echo ""

# Get IAM role ARN from CloudFormation
echo "📋 Getting MCP Server execution role from CloudFormation..."
ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='MCPServerRoleArn'].OutputValue" \
  --output text 2>/dev/null || echo "")

if [ -z "$ROLE_ARN" ]; then
  echo "⚠️  CloudFormation stack not found or role not created"
  echo "    Please deploy IAM roles first: infrastructure/cloudformation/iam-roles.yaml"
  echo ""
  echo "    Using placeholder role ARN..."
  ROLE_ARN="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/mcp-server-execution-role"
fi

echo "✅ Using IAM Role: $ROLE_ARN"
echo ""

# Function to deploy Lambda
deploy_lambda() {
  local name=$1
  local dir=$2
  local handler=${3:-lambda_function.lambda_handler}

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Deploying: $name"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  cd "$dir"

  # Create deployment package
  echo "📦 Creating deployment package..."
  zip -q -r function.zip lambda_function.py 2>/dev/null || {
    echo "❌ Failed to create zip file"
    return 1
  }

  # Check if Lambda exists
  if aws lambda get-function --function-name "$name" --region "$REGION" &>/dev/null; then
    echo "🔄 Updating existing Lambda function..."
    aws lambda update-function-code \
      --function-name "$name" \
      --zip-file fileb://function.zip \
      --region "$REGION" \
      --no-cli-pager > /dev/null

    echo "⚙️  Updating function configuration..."
    aws lambda update-function-configuration \
      --function-name "$name" \
      --handler "$handler" \
      --runtime python3.11 \
      --timeout 30 \
      --memory-size 256 \
      --region "$REGION" \
      --no-cli-pager > /dev/null
  else
    echo "🆕 Creating new Lambda function..."
    aws lambda create-function \
      --function-name "$name" \
      --runtime python3.11 \
      --role "$ROLE_ARN" \
      --handler "$handler" \
      --zip-file fileb://function.zip \
      --timeout 30 \
      --memory-size 256 \
      --description "MCP Server for $name" \
      --region "$REGION" \
      --no-cli-pager > /dev/null
  fi

  # Cleanup
  rm function.zip

  # Get Lambda ARN
  LAMBDA_ARN=$(aws lambda get-function \
    --function-name "$name" \
    --region "$REGION" \
    --query 'Configuration.FunctionArn' \
    --output text)

  echo "✅ Deployed: $LAMBDA_ARN"
  echo ""

  cd - > /dev/null
}

# Deploy MCP Servers
echo "🚀 Starting deployment..."
echo ""

deploy_lambda "demo-ecommerce-mcp" "./ecommerce-mcp"
deploy_lambda "demo-products-mcp" "./products-mcp"
deploy_lambda "demo-orders-mcp" "./orders-mcp"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    Deployment Complete                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ All MCP servers deployed successfully"
echo ""
echo "Next Steps:"
echo "1. Register MCP servers as AgentCore targets:"
echo "   python scripts/register-mcp-targets.py"
echo ""
echo "2. Create AgentCore Gateway:"
echo "   python scripts/create-gateway.py"
echo ""
echo "3. Deploy Lambda proxy:"
echo "   cd lambda/gateway-proxy"
echo "   ./deploy.sh"
echo ""
