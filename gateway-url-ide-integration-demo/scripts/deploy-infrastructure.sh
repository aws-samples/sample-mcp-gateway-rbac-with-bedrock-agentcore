#!/bin/bash
# Deploy complete infrastructure for MCP Gateway Demo

set -e

REGION=${AWS_REGION:-us-east-1}
STACK_NAME="mcp-gateway-demo"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║      Bedrock AgentCore MCP Gateway - Infrastructure Deploy    ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Region: $REGION"
echo "Stack Name: $STACK_NAME"
echo ""

# Step 1: Deploy IAM Roles
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Deploying IAM Roles"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &>/dev/null; then
  echo "📝 Stack exists, updating..."
  aws cloudformation update-stack \
    --stack-name "$STACK_NAME" \
    --template-body file://infrastructure/cloudformation/iam-roles.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --no-cli-pager || echo "⚠️  No updates needed"

  echo "⏳ Waiting for stack update..."
  aws cloudformation wait stack-update-complete \
    --stack-name "$STACK_NAME" \
    --region "$REGION" 2>/dev/null || true
else
  echo "🆕 Creating new stack..."
  aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-body file://infrastructure/cloudformation/iam-roles.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --no-cli-pager

  echo "⏳ Waiting for stack creation..."
  aws cloudformation wait stack-create-complete \
    --stack-name "$STACK_NAME" \
    --region "$REGION"
fi

echo "✅ IAM roles deployed"
echo ""

# Step 2: Get stack outputs
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Getting Stack Outputs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

TEAM_ALPHA_ROLE=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='TeamAlphaRoleArn'].OutputValue" \
  --output text)

TEAM_BETA_ROLE=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='TeamBetaRoleArn'].OutputValue" \
  --output text)

LAMBDA_PROXY_ROLE=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='LambdaProxyRoleArn'].OutputValue" \
  --output text)

MCP_SERVER_ROLE=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='MCPServerRoleArn'].OutputValue" \
  --output text)

echo "Team Alpha Role:   $TEAM_ALPHA_ROLE"
echo "Team Beta Role:    $TEAM_BETA_ROLE"
echo "Lambda Proxy Role: $LAMBDA_PROXY_ROLE"
echo "MCP Server Role:   $MCP_SERVER_ROLE"
echo ""

# Step 3: Deploy MCP Servers
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Deploying MCP Server Lambdas"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd lambda/mcp-servers
./deploy-all.sh
cd ../..

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                Infrastructure Deployment Complete              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ All resources deployed successfully"
echo ""
echo "📋 Summary:"
echo "   • IAM Roles: Created"
echo "   • MCP Servers: Deployed (3 Lambda functions)"
echo ""
echo "🎯 Next Steps:"
echo ""
echo "1. Register MCP servers with AgentCore:"
echo "   python scripts/register-mcp-targets.py"
echo ""
echo "2. Create AgentCore Gateway:"
echo "   python scripts/create-gateway.py"
echo ""
echo "3. Deploy Gateway Proxy Lambda:"
echo "   cd lambda/gateway-proxy"
echo "   ./deploy.sh"
echo ""
echo "4. Create API Gateway (manual or CDK)"
echo ""
echo "5. Test with frontend:"
echo "   open frontend/chatbox-demo.html"
echo ""
