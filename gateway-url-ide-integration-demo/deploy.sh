#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# One-click deploy: MCP Registry + OAuth Gateway + Cedar RBAC
# ============================================================================
# Prerequisites: AWS CLI configured, Python 3.9+, jq
# Usage: ./deploy.sh [REGION]
# ============================================================================

REGION="${1:-us-east-1}"
STACK_NAME="mcp-gateway-oauth-demo"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  MCP Registry + OAuth Gateway + Cedar RBAC — One-Click Deploy"
echo "║  Region: $REGION"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
command -v aws >/dev/null 2>&1 || { echo "❌ AWS CLI not found. Install: https://aws.amazon.com/cli/"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python3 not found."; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "❌ jq not found. Install: brew install jq"; exit 1; }

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "📋 AWS Account: $ACCOUNT_ID"
echo "📋 Region: $REGION"
echo ""

# ── Step 1: Deploy CloudFormation (Cognito + Registry Lambda + API Gateway) ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1/5 — Deploying Cognito + Registry Lambda + API Gateway..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/infrastructure/cloudformation/oauth-registry-stack.yaml" \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --parameter-overrides StackPrefix=mcp-demo \
  --no-fail-on-empty-changeset

# Get outputs
COGNITO_POOL_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolId'].OutputValue" --output text)
COGNITO_CLIENT_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoClientId'].OutputValue" --output text)
COGNITO_DOMAIN=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoDomain'].OutputValue" --output text)
REGISTRY_URL=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='RegistryUrl'].OutputValue" --output text)

echo "✅ Cognito Pool: $COGNITO_POOL_ID"
echo "✅ OAuth Client: $COGNITO_CLIENT_ID"
echo "✅ Registry URL: $REGISTRY_URL"
echo ""

# ── Step 2: Deploy Lambda MCP servers ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2/5 — Deploying Lambda MCP servers..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

bash "$SCRIPT_DIR/lambda/mcp-servers/deploy-all.sh" "$REGION"
echo ""

# ── Step 3: Create AgentCore Gateway (CUSTOM_JWT) ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3/5 — Creating AgentCore Gateway (OAuth/JWT)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

GATEWAY_URL=$(python3 "$SCRIPT_DIR/scripts/create-gateway-oauth.py" \
  --region "$REGION" \
  --cognito-pool-id "$COGNITO_POOL_ID" \
  --cognito-client-id "$COGNITO_CLIENT_ID" \
  --account-id "$ACCOUNT_ID")

echo "✅ Gateway URL: $GATEWAY_URL"
echo ""

# ── Step 4: Create Cedar policies + bind to gateway ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4/5 — Setting up Cedar RBAC policies..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 "$SCRIPT_DIR/scripts/setup-cedar-oauth.py" \
  --region "$REGION" \
  --account-id "$ACCOUNT_ID"

echo ""

# ── Step 5: Create test users ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 5/5 — Creating test users..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 "$SCRIPT_DIR/scripts/create-oauth-users.py" \
  --region "$REGION" \
  --pool-id "$COGNITO_POOL_ID"

echo ""

# ── Step 6: Update registry Lambda with gateway URL ──
echo "Updating registry with gateway URL..."
aws lambda update-function-configuration \
  --function-name mcp-demo-registry \
  --region "$REGION" \
  --environment "Variables={GATEWAY_URL=$GATEWAY_URL}" \
  --no-cli-pager > /dev/null

# ── Step 7: Write VS Code config ──
cat > "$SCRIPT_DIR/vscode-config/mcp-oauth.json" <<EOF
{
  "servers": {
    "mcp-gateway": {
      "type": "http",
      "url": "${GATEWAY_URL}/mcp"
    }
  }
}
EOF

# ── Done ──
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ DEPLOYMENT COMPLETE                                     "
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                             "
echo "║  Registry URL (paste into GitHub Copilot admin):            "
echo "║  $REGISTRY_URL"
echo "║                                                             "
echo "║  Gateway URL (what developers connect to):                  "
echo "║  $GATEWAY_URL/mcp"
echo "║                                                             "
echo "║  Test credentials:                                          "
echo "║  alice@example.com / DemoPass123!  (team: Engineering)      "
echo "║  bob@example.com   / DemoPass123!  (team: Support)          "
echo "║                                                             "
echo "║  OAuth Client ID (if VS Code prompts):                      "
echo "║  $COGNITO_CLIENT_ID"
echo "║                                                             "
echo "║  RBAC:                                                      "
echo "║  Engineering → products + orders (list, search, get)        "
echo "║  Support     → customers + jira  (list, get)                "
echo "║                                                             "
echo "║  VS Code config: vscode-config/mcp-oauth.json               "
echo "║  Copy to: ~/Library/Application Support/Code/User/mcp.json  "
echo "║                                                             "
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Next: Copy mcp-oauth.json to VS Code, restart, and log in as alice or bob."
echo "See DEMO.md for the step-by-step walkthrough."
