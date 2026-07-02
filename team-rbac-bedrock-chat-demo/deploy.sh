#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Fully automated deployment for Team RBAC Bedrock Chat Demo
#
# What this script does:
#   1. Packages both Lambda functions
#   2. Creates a unique S3 bucket (if needed) and uploads artifacts
#   3. Deploys / updates the CloudFormation stack
#   4. Enables Bedrock Model Invocation Logging
#   5. Fetches all outputs (API endpoint + API key values)
#   6. Patches chatbox.html in-place — no manual edits needed
#
# Usage:
#   ./deploy.sh [--email you@example.com] [--stack-name my-stack]
#
# Optional flags:
#   --email        SNS alarm notification email (default: none)
#   --stack-name   CloudFormation stack name    (default: llm-gateway-demo)
#   --region       AWS region                   (default: us-east-1)
#   --daily-limit  Daily token limit per team   (default: 100000)
# =============================================================================

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
STACK_NAME="llm-gateway-demo"
REGION="us-east-1"
ALARM_EMAIL=""
DAILY_TOKEN_LIMIT="100000"
MONTHLY_TOKEN_LIMIT="2000000"

# ── Parse flags ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --email)        ALARM_EMAIL="$2";        shift 2 ;;
    --stack-name)   STACK_NAME="$2";         shift 2 ;;
    --region)       REGION="$2";             shift 2 ;;
    --daily-limit)  DAILY_TOKEN_LIMIT="$2";  shift 2 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

# ── Resolve directories ───────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROXY_DIR="$SCRIPT_DIR/lambda/gateway-proxy"
PUBLISHER_DIR="$SCRIPT_DIR/lambda/token-metric-publisher"
CFN_DIR="$SCRIPT_DIR/infrastructure/cloudformation"
CHATBOX="$SCRIPT_DIR/chatbox.html"

log()  { echo "▶ $*"; }
ok()   { echo "✅ $*"; }
fail() { echo "❌ $*" >&2; exit 1; }

# ── Verify AWS credentials ────────────────────────────────────────────────────
log "Verifying AWS credentials..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION") \
  || fail "AWS credentials not configured. Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN."
ok "Account: $ACCOUNT_ID  Region: $REGION"

# ── S3 bucket (unique per account+region) ─────────────────────────────────────
BUCKET_NAME="llm-gateway-artifacts-${ACCOUNT_ID}-${REGION}"
log "Ensuring S3 bucket: $BUCKET_NAME"
if ! aws s3api head-bucket --bucket "$BUCKET_NAME" --region "$REGION" 2>/dev/null; then
  if [[ "$REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$BUCKET_NAME" --region "$REGION" > /dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET_NAME" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION" > /dev/null
  fi
  ok "Created bucket: $BUCKET_NAME"
else
  ok "Bucket already exists: $BUCKET_NAME"
fi

# Block public access
aws s3api put-public-access-block --bucket "$BUCKET_NAME" \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
  --region "$REGION" > /dev/null

# ── Package Lambda: gateway-proxy ─────────────────────────────────────────────
log "Packaging Lambda: gateway-proxy..."
cd "$PROXY_DIR"
rm -f function.zip
zip -q function.zip lambda_function.py feature_flags.py
aws s3 cp function.zip "s3://${BUCKET_NAME}/lambda/gateway-proxy.zip" --region "$REGION" > /dev/null
ok "Uploaded gateway-proxy.zip"

# ── Package Lambda: token-metric-publisher ────────────────────────────────────
log "Packaging Lambda: token-metric-publisher..."
cd "$PUBLISHER_DIR"
rm -f function.zip
zip -q function.zip lambda_function.py
aws s3 cp function.zip "s3://${BUCKET_NAME}/lambda/token-metric-publisher.zip" --region "$REGION" > /dev/null
ok "Uploaded token-metric-publisher.zip"

# ── Build CloudFormation parameters ───────────────────────────────────────────
CFN_PARAMS=(
  "ParameterKey=S3ArtifactBucket,ParameterValue=${BUCKET_NAME}"
  "ParameterKey=ProxyCodeKey,ParameterValue=lambda/gateway-proxy.zip"
  "ParameterKey=TokenMetricPublisherCodeKey,ParameterValue=lambda/token-metric-publisher.zip"
  "ParameterKey=DailyTokenLimit,ParameterValue=${DAILY_TOKEN_LIMIT}"
  "ParameterKey=MonthlyTokenLimit,ParameterValue=${MONTHLY_TOKEN_LIMIT}"
)
[[ -n "$ALARM_EMAIL" ]] && CFN_PARAMS+=("ParameterKey=AlarmEmail,ParameterValue=${ALARM_EMAIL}")

# ── Deploy / update CloudFormation stack ──────────────────────────────────────
log "Checking CloudFormation stack: $STACK_NAME..."
STACK_STATUS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [[ "$STACK_STATUS" == "DOES_NOT_EXIST" ]]; then
  log "Creating new stack..."
  aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-body "file://${CFN_DIR}/main-stack.yaml" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters "${CFN_PARAMS[@]}" \
    --region "$REGION" > /dev/null
  log "Waiting for stack creation (this takes ~3-5 minutes)..."
  aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME" --region "$REGION"
  ok "Stack created."
elif [[ "$STACK_STATUS" =~ (ROLLBACK_COMPLETE|CREATE_FAILED|DELETE_FAILED) ]]; then
  fail "Stack is in state $STACK_STATUS. Delete it first: aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION"
else
  log "Updating existing stack (status: $STACK_STATUS)..."
  # Update Lambda code in place before CFN update
  aws lambda update-function-code \
    --function-name "${STACK_NAME}-proxy" \
    --s3-bucket "$BUCKET_NAME" \
    --s3-key lambda/gateway-proxy.zip \
    --region "$REGION" > /dev/null 2>&1 || true
  aws lambda update-function-code \
    --function-name "${STACK_NAME}-token-publisher" \
    --s3-bucket "$BUCKET_NAME" \
    --s3-key lambda/token-metric-publisher.zip \
    --region "$REGION" > /dev/null 2>&1 || true

  UPDATE_OUTPUT=$(aws cloudformation update-stack \
    --stack-name "$STACK_NAME" \
    --template-body "file://${CFN_DIR}/main-stack.yaml" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters "${CFN_PARAMS[@]}" \
    --region "$REGION" 2>&1 || true)

  if echo "$UPDATE_OUTPUT" | grep -q "No updates are to be performed"; then
    ok "Stack already up to date."
  else
    log "Waiting for stack update..."
    aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME" --region "$REGION"
    ok "Stack updated."
  fi
fi

# ── Fetch stack outputs ────────────────────────────────────────────────────────
log "Fetching stack outputs..."
get_output() {
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
    --output text
}

API_ENDPOINT=$(get_output "ApiEndpoint")
ALPHA_KEY_ID=$(get_output "TeamAlphaApiKeyId")
BETA_KEY_ID=$(get_output "TeamBetaApiKeyId")
BEDROCK_LOGGING_ROLE=$(get_output "BedrockLoggingRoleArn")
ALARM_TOPIC=$(get_output "AlarmTopicArn")

# Resolve actual API key values (not just IDs)
log "Retrieving API key values..."
ALPHA_API_KEY=$(aws apigateway get-api-key \
  --api-key "$ALPHA_KEY_ID" --include-value \
  --query 'value' --output text --region "$REGION")
BETA_API_KEY=$(aws apigateway get-api-key \
  --api-key "$BETA_KEY_ID" --include-value \
  --query 'value' --output text --region "$REGION")

ok "API Endpoint:     $API_ENDPOINT"
ok "Team Alpha Key:   ${ALPHA_API_KEY:0:8}... (truncated)"
ok "Team Beta Key:    ${BETA_API_KEY:0:8}... (truncated)"

# ── Enable Bedrock Model Invocation Logging ────────────────────────────────────
log "Enabling Bedrock Model Invocation Logging..."
aws bedrock put-model-invocation-logging-configuration \
  --logging-config "{
    \"cloudWatchConfig\": {
      \"logGroupName\": \"/aws/bedrock/invocation-logs\",
      \"roleArn\": \"${BEDROCK_LOGGING_ROLE}\"
    },
    \"textDataDeliveryEnabled\": true,
    \"imageDataDeliveryEnabled\": false,
    \"embeddingDataDeliveryEnabled\": false
  }" \
  --region "$REGION" > /dev/null
ok "Bedrock invocation logging enabled → /aws/bedrock/invocation-logs"

# ── Patch chatbox.html in-place ───────────────────────────────────────────────
log "Patching chatbox.html with live configuration..."

# Create a Python patcher to reliably replace the JS constants
python3 << PATCHEOF
import re, sys

html_path = "${CHATBOX}"
with open(html_path, "r") as f:
    content = f.read()

# Replace API_ENDPOINT
content = re.sub(
    r'const API_ENDPOINT\s*=\s*"[^"]*"',
    'const API_ENDPOINT = "${API_ENDPOINT}"',
    content
)

# Replace Team Alpha apiKey
content = re.sub(
    r"(name:\s*\"Team Alpha\"[^}]*apiKey:\s*\")[^\"]*\"",
    r'\g<1>${ALPHA_API_KEY}"',
    content,
    flags=re.DOTALL
)

# Replace Team Beta apiKey
content = re.sub(
    r"(name:\s*\"Team Beta\"[^}]*apiKey:\s*\")[^\"]*\"",
    r'\g<1>${BETA_API_KEY}"',
    content,
    flags=re.DOTALL
)

# Remove the manual configuration comment block
content = content.replace(
    "        // ⚠️ CONFIGURATION REQUIRED\n"
    "        // After deploying the CloudFormation stack, replace these placeholders:\n"
    "        // 1. Get API endpoint from stack outputs: ApiEndpoint\n"
    "        // 2. Get API key values: aws apigateway get-api-key --api-key <KEY_ID> --include-value --query value --output text\n",
    "        // ✅ Auto-configured by deploy.sh — do not edit manually\n"
)

with open(html_path, "w") as f:
    f.write(content)

print("Patched successfully.")
PATCHEOF

ok "chatbox.html updated — no manual edits required"

# ── Print summary ─────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  DEPLOYMENT COMPLETE"
echo "════════════════════════════════════════════════════════"
echo "  Stack:          $STACK_NAME"
echo "  Region:         $REGION"
echo "  API Endpoint:   $API_ENDPOINT"
echo "  Alarm SNS:      $ALARM_TOPIC"
echo "  Daily limit:    $DAILY_TOKEN_LIMIT tokens/team"
echo ""
echo "  Next steps:"
echo "  1. Open chatbox.html in your browser"
echo "  2. Select a team and start chatting"
echo "  3. Monitor tokens: CloudWatch → Bedrock/PerUser namespace"
echo "  4. View logs:      CloudWatch → /aws/lambda/${STACK_NAME}-proxy"
if [[ -n "$ALARM_EMAIL" ]]; then
echo "  5. Confirm SNS subscription in your inbox: $ALARM_EMAIL"
fi
echo "════════════════════════════════════════════════════════"

# NOTE: chatbox.html is committed with placeholder values.
# This script patches it locally with live keys after deployment.
# Do NOT commit chatbox.html after running deploy.sh — the live keys
# should not be stored in source control.
