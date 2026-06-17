#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# One-click deploy: MCP Registry + IAM Gateway + Cedar RBAC
# ============================================================================
# Prerequisites: AWS CLI configured (admin), Python 3.9+, jq
# Usage: ./deploy.sh [REGION]
#
# Creates:
#   - Lambda MCP servers (products, orders, customers, jira)
#   - AgentCore Gateway (IAM/SigV4 auth)
#   - Cedar RBAC policies (ReadOnly vs FullAccess)
#   - MCP Registry Lambda + API Gateway (serves GitHub Copilot v0.1 spec)
#   - Two IAM test users with group tags
#
# No passwords or secrets are hardcoded — IAM access keys are generated
# at deploy time and printed for you to configure as AWS profiles.
# ============================================================================

REGION="${1:-us-east-1}"
PREFIX="mcp-demo"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  MCP Registry + Gateway + Cedar RBAC — One-Click Deploy      "
echo "║  Region: $REGION"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── Prerequisites check ──
command -v aws >/dev/null 2>&1 || { echo "❌ AWS CLI not found."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python3 not found."; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "❌ jq not found. Install: brew install jq"; exit 1; }

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "📋 Account: $ACCOUNT_ID | Region: $REGION"
echo ""

# ── Step 1: Create Lambda execution role ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1/6 — Creating Lambda execution role..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

LAMBDA_ROLE="${PREFIX}-lambda-role"
if aws iam get-role --role-name "$LAMBDA_ROLE" &>/dev/null; then
  echo "  ⏭️  Role exists: $LAMBDA_ROLE"
else
  aws iam create-role \
    --role-name "$LAMBDA_ROLE" \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --no-cli-pager > /dev/null
  aws iam attach-role-policy \
    --role-name "$LAMBDA_ROLE" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  echo "  ✅ Created: $LAMBDA_ROLE"
  sleep 10  # IAM propagation
fi
LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE}"
echo ""

# ── Step 2: Deploy Lambda MCP servers ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2/6 — Deploying Lambda MCP servers..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

deploy_lambda() {
  local name="${PREFIX}-${1}"
  local dir="$SCRIPT_DIR/lambda/mcp-servers/${2}"
  (cd "$dir" && zip -q function.zip lambda_function.py)
  if aws lambda get-function --function-name "$name" --region "$REGION" &>/dev/null; then
    aws lambda update-function-code --function-name "$name" --zip-file "fileb://${dir}/function.zip" --region "$REGION" --no-cli-pager > /dev/null
    echo "  🔄 Updated: $name"
  else
    aws lambda create-function \
      --function-name "$name" --runtime python3.11 \
      --role "$LAMBDA_ROLE_ARN" --handler lambda_function.lambda_handler \
      --zip-file "fileb://${dir}/function.zip" \
      --timeout 30 --memory-size 256 --region "$REGION" --no-cli-pager > /dev/null
    echo "  ✅ Created: $name"
  fi
  rm -f "${dir}/function.zip"
}

deploy_lambda "ecommerce-mcp" "ecommerce-mcp"
deploy_lambda "products-mcp" "products-mcp"
deploy_lambda "orders-mcp" "orders-mcp"
deploy_lambda "jira-mcp" "jira-mcp"
echo ""

# ── Step 3: Deploy MCP Registry (Lambda + API Gateway via inline CFN) ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3/6 — Deploying MCP Registry (API Gateway + Lambda)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/infrastructure/cloudformation/registry-stack.yaml" \
  --stack-name "${PREFIX}-registry" \
  --region "$REGION" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides StackPrefix="$PREFIX" \
  --no-fail-on-empty-changeset 2>&1 | grep -v "^$"

REGISTRY_URL=$(aws cloudformation describe-stacks --stack-name "${PREFIX}-registry" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='RegistryUrl'].OutputValue" --output text)
echo "  ✅ Registry URL: $REGISTRY_URL"
echo ""

# ── Step 4: Create AgentCore Gateway (IAM/SigV4) ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4/6 — Creating AgentCore Gateway (IAM auth)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

GATEWAY_URL=$(python3 "$SCRIPT_DIR/scripts/create-gateway.py" 2>&1 | tail -1)
echo "  ✅ Gateway URL: $GATEWAY_URL"
echo ""

# ── Step 5: Create Cedar RBAC policies ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 5/6 — Setting up Cedar RBAC policies..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 "$SCRIPT_DIR/scripts/setup-cedar-iam.py" --region "$REGION" --account-id "$ACCOUNT_ID" --prefix "$PREFIX"
echo ""

# ── Step 6: Create test IAM users ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 6/6 — Creating test IAM users..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

create_iam_user() {
  local username="$1"
  local group_tag="$2"
  
  if aws iam get-user --user-name "$username" &>/dev/null; then
    echo "  ⏭️  User exists: $username (updating tag)"
    aws iam tag-user --user-name "$username" --tags "Key=group,Value=$group_tag"
  else
    aws iam create-user --user-name "$username" --no-cli-pager > /dev/null
    aws iam tag-user --user-name "$username" --tags "Key=group,Value=$group_tag"
    
    # Attach gateway access policy
    aws iam put-user-policy --user-name "$username" --policy-name gateway-access \
      --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"bedrock-agentcore:InvokeGateway\"],\"Resource\":\"*\"}]}"
    
    # Create access key
    KEY_OUTPUT=$(aws iam create-access-key --user-name "$username" --output json)
    ACCESS_KEY=$(echo "$KEY_OUTPUT" | jq -r '.AccessKey.AccessKeyId')
    SECRET_KEY=$(echo "$KEY_OUTPUT" | jq -r '.AccessKey.SecretAccessKey')
    
    echo "  ✅ Created: $username (group: $group_tag)"
    echo ""
    echo "     Add to ~/.aws/credentials:"
    echo "     [$username]"
    echo "     aws_access_key_id = $ACCESS_KEY"
    echo "     aws_secret_access_key = $SECRET_KEY"
    echo "     region = $REGION"
    echo ""
  fi
}

create_iam_user "${PREFIX}-readonly" "ReadOnly"
create_iam_user "${PREFIX}-fullaccess" "FullAccess"

# ── Update registry Lambda with gateway URL ──
aws lambda update-function-configuration \
  --function-name "${PREFIX}-registry" \
  --region "$REGION" \
  --environment "Variables={GATEWAY_URL=$GATEWAY_URL}" \
  --no-cli-pager > /dev/null 2>&1 || true

# ── Write VS Code config ──
mkdir -p "$SCRIPT_DIR/vscode-config"
cat > "$SCRIPT_DIR/vscode-config/mcp-generated.json" <<EOF
{
  "servers": {
    "mcp-gateway": {
      "command": "python3",
      "args": ["${SCRIPT_DIR}/npm-package/customer-gateway-proxy/bin/proxy.py"],
      "env": {
        "GATEWAY_URL": "${GATEWAY_URL}/mcp"
      }
    }
  }
}
EOF

# ── Done ──
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ DEPLOYMENT COMPLETE                                      "
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              "
echo "║  Registry URL (for GitHub Copilot admin):                    "
echo "║  $REGISTRY_URL"
echo "║                                                              "
echo "║  Gateway URL:                                                "
echo "║  $GATEWAY_URL/mcp"
echo "║                                                              "
echo "║  Test users (configure as AWS profiles):                     "
echo "║    ${PREFIX}-readonly   (group: ReadOnly)                    "
echo "║    ${PREFIX}-fullaccess (group: FullAccess)                  "
echo "║                                                              "
echo "║  RBAC:                                                       "
echo "║    ReadOnly   → list/search/get (no create/update/delete)    "
echo "║    FullAccess → all tools                                    "
echo "║                                                              "
echo "║  VS Code config: vscode-config/mcp-generated.json            "
echo "║  Copy to: ~/Library/Application Support/Code/User/mcp.json   "
echo "║                                                              "
echo "║  To test:                                                    "
echo "║    export AWS_PROFILE=${PREFIX}-readonly                     "
echo "║    code .                                                    "
echo "║                                                              "
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "For OAuth/JWT (native IDE login, no local proxy):"
echo "See OAUTH_DEMO.md for the Cognito setup guide."
