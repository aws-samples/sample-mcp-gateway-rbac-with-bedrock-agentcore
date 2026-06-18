#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Demo 1: AgentCore MCP Gateway — Deploy Infrastructure + Lambda Code
# ============================================================================
# Prerequisites: AWS CLI configured, Python 3.11+, AgentCore CLI (npm install -g @aws/agentcore-cli)
# Usage: ./deploy.sh [REGION]
#
# What this does:
#   Step 1: CloudFormation → Lambda functions, IAM roles, test users, MCP registry
#   Step 2: Deploy actual Lambda code to the functions
#   Step 3: Deploy AgentCore Gateway (via agentcore CLI)
#   Step 4: Update registry with gateway URL
#   Step 5: Create access keys for test users
# ============================================================================

REGION="${1:-${AWS_REGION:-us-east-1}}"
PREFIX="mcp-demo"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Demo 1: AgentCore MCP Gateway — Full Deployment            ║"
echo "║  Region: $REGION                                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── Prerequisites check ──
command -v aws >/dev/null 2>&1 || { echo "❌ AWS CLI not found."; exit 1; }
command -v agentcore >/dev/null 2>&1 || { echo "❌ AgentCore CLI not found. Install: npm install -g @aws/agentcore-cli"; exit 1; }

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "📋 Account: $ACCOUNT_ID | Region: $REGION"
echo ""

# ── Step 1: Deploy CloudFormation ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1/5 — Deploying CloudFormation (Lambda + IAM + Registry)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/infrastructure/cloudformation/demo1-stack.yaml" \
  --stack-name "$PREFIX" \
  --region "$REGION" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides StackPrefix="$PREFIX" \
  --no-fail-on-empty-changeset

REGISTRY_URL=$(aws cloudformation describe-stacks --stack-name "$PREFIX" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='RegistryUrl'].OutputValue" --output text)

echo "  ✅ CloudFormation deployed"
echo "  ✅ Registry URL: $REGISTRY_URL"
echo ""

# ── Step 2: Deploy Lambda code ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2/5 — Deploying Lambda code..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

bash "$SCRIPT_DIR/lambda/mcp-servers/deploy-lambdas.sh" "$REGION" "$PREFIX"
echo ""

# ── Step 3: Configure and deploy AgentCore Gateway ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3/5 — Deploying AgentCore Gateway..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd "$SCRIPT_DIR/DemoMcpGateway/agentcore"

# Generate aws-targets.json from template
sed "s/<YOUR_AWS_ACCOUNT_ID>/$ACCOUNT_ID/g; s/us-east-1/$REGION/g" \
  aws-targets.json.template > aws-targets.json

# Update agentcore.json with actual values (write to temp, don't destroy template)
sed "s/<REGION>/$REGION/g; s/<ACCOUNT_ID>/$ACCOUNT_ID/g" agentcore.json > agentcore.json.resolved
mv agentcore.json agentcore.json.template.bak
mv agentcore.json.resolved agentcore.json

# Install CDK deps and deploy
(cd cdk && npm install --silent)
agentcore deploy

# Restore template
mv agentcore.json.template.bak agentcore.json

# Extract gateway URL from deployed state
GATEWAY_URL=$(cat .cli/deployed-state.json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('gateways',[{}])[0].get('url',''))" 2>/dev/null || echo "")

if [ -z "$GATEWAY_URL" ]; then
  echo "  ⚠️  Could not extract gateway URL from deployed state."
  echo "  Check: cat .cli/deployed-state.json"
  echo "  You'll need to manually update the registry Lambda."
else
  echo "  ✅ Gateway URL: $GATEWAY_URL"
fi

cd "$SCRIPT_DIR"
echo ""

# ── Step 4: Update registry with gateway URL ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4/5 — Updating registry with gateway URL..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -n "$GATEWAY_URL" ]; then
  aws lambda update-function-configuration \
    --function-name "${PREFIX}-registry" \
    --region "$REGION" \
    --environment "Variables={GATEWAY_URL=$GATEWAY_URL}" \
    --no-cli-pager > /dev/null 2>&1
  echo "  ✅ Registry updated with gateway URL"
else
  echo "  ⏭️  Skipped (no gateway URL available)"
fi
echo ""

# ── Step 5: Create access keys for test users ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 5/5 — Creating access keys for test IAM users..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "  Creating key for ${PREFIX}-readonly..."
READONLY_KEY=$(aws iam create-access-key --user-name "${PREFIX}-readonly" --output json 2>/dev/null || echo "EXISTS")
if [ "$READONLY_KEY" != "EXISTS" ]; then
  RO_AK=$(echo "$READONLY_KEY" | python3 -c "import json,sys; print(json.load(sys.stdin)['AccessKey']['AccessKeyId'])")
  RO_SK=$(echo "$READONLY_KEY" | python3 -c "import json,sys; print(json.load(sys.stdin)['AccessKey']['SecretAccessKey'])")
  echo "  [${PREFIX}-readonly]"
  echo "  aws_access_key_id = $RO_AK"
  echo "  aws_secret_access_key = $RO_SK"
  echo "  region = $REGION"
else
  echo "  ⏭️  Key already exists for ${PREFIX}-readonly"
fi

echo ""
echo "  Creating key for ${PREFIX}-fullaccess..."
FULL_KEY=$(aws iam create-access-key --user-name "${PREFIX}-fullaccess" --output json 2>/dev/null || echo "EXISTS")
if [ "$FULL_KEY" != "EXISTS" ]; then
  FA_AK=$(echo "$FULL_KEY" | python3 -c "import json,sys; print(json.load(sys.stdin)['AccessKey']['AccessKeyId'])")
  FA_SK=$(echo "$FULL_KEY" | python3 -c "import json,sys; print(json.load(sys.stdin)['AccessKey']['SecretAccessKey'])")
  echo "  [${PREFIX}-fullaccess]"
  echo "  aws_access_key_id = $FA_AK"
  echo "  aws_secret_access_key = $FA_SK"
  echo "  region = $REGION"
else
  echo "  ⏭️  Key already exists for ${PREFIX}-fullaccess"
fi

# ── Done ──
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ DEPLOYMENT COMPLETE                                     ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                             ║"
echo "║  Registry URL: $REGISTRY_URL"
echo "║  Gateway URL:  ${GATEWAY_URL:-<check deployed-state.json>}"
echo "║                                                             ║"
echo "║  Test users:                                                ║"
echo "║    ${PREFIX}-readonly   → list/search/get only              ║"
echo "║    ${PREFIX}-fullaccess → all tools including create        ║"
echo "║                                                             ║"
echo "║  Add credentials to ~/.aws/credentials, then:              ║"
echo "║    export AWS_PROFILE=${PREFIX}-readonly                    ║"
echo "║    code .   (VS Code with GitHub Copilot)                  ║"
echo "║                                                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
