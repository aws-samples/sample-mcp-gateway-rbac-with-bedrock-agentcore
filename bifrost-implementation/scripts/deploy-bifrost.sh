#!/usr/bin/env bash
# =============================================================================
# deploy-bifrost.sh — Full Bifrost AI Gateway deployment
#
# Deploys in order:
#   1. VPC + networking
#   2. ECS Fargate + EFS + ALB
#   3. CloudFront + Cognito + S3 (must run in us-east-1)
#   4. CloudWatch observability + Lambda quota publisher
#   5. Uploads chatbox.html to S3
#   6. Patches chatbox.html with live endpoints for local testing
#
# Usage:
#   ./deploy-bifrost.sh [options]
#
# Options:
#   --prefix        Stack prefix (default: bifrost)
#   --region        AWS region for ECS/ALB stacks (default: us-east-1)
#   --admin-email   Email for Cognito admin user
#   --alarm-email   Email for CloudWatch alarms
#   --stack-name    CloudFormation stack base name (default: bifrost-gw)
#   --custom-domain Optional custom domain for CloudFront
#   --encryption-key 32-byte Bifrost config encryption key (auto-generated if omitted)
# =============================================================================

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────
PREFIX="bifrost"
REGION="us-east-1"
ADMIN_EMAIL=""
ALARM_EMAIL=""
STACK_BASE="bifrost-gw"
CUSTOM_DOMAIN=""
ENCRYPTION_KEY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)         PREFIX="$2";         shift 2 ;;
    --region)         REGION="$2";         shift 2 ;;
    --admin-email)    ADMIN_EMAIL="$2";    shift 2 ;;
    --alarm-email)    ALARM_EMAIL="$2";    shift 2 ;;
    --stack-name)     STACK_BASE="$2";     shift 2 ;;
    --custom-domain)  CUSTOM_DOMAIN="$2";  shift 2 ;;
    --encryption-key) ENCRYPTION_KEY="$2"; shift 2 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CFN_DIR="$ROOT_DIR/cloudformation"
CHATBOX_DIR="$ROOT_DIR/chatbox"
QUOTA_DIR="$SCRIPT_DIR/quota-publisher"

log()  { echo "▶ $*"; }
ok()   { echo "✅ $*"; }
fail() { echo "❌ $*" >&2; exit 1; }
hr()   { echo "────────────────────────────────────────────────────────"; }

# ── Verify credentials ────────────────────────────────────────────
log "Verifying AWS credentials..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION") \
  || fail "AWS credentials not configured."
ok "Account: $ACCOUNT_ID  Region: $REGION"

# ── Auto-generate encryption key if not provided ──────────────────
if [[ -z "$ENCRYPTION_KEY" ]]; then
  ENCRYPTION_KEY=$(python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))")
  log "Generated encryption key (saved to ./.bifrost-key — keep safe)"
  echo "$ENCRYPTION_KEY" > "$SCRIPT_DIR/.bifrost-key"
  chmod 600 "$SCRIPT_DIR/.bifrost-key"
fi

# ── S3 artifact bucket ────────────────────────────────────────────
BUCKET="bifrost-artifacts-${ACCOUNT_ID}-${REGION}"
log "Ensuring S3 artifacts bucket: $BUCKET"
if ! aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
  if [[ "$REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" > /dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION" > /dev/null
  fi
  aws s3api put-public-access-block --bucket "$BUCKET" \
    --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
    --region "$REGION" > /dev/null
  ok "Created bucket: $BUCKET"
else
  ok "Bucket exists: $BUCKET"
fi

# ── Package quota publisher Lambda ────────────────────────────────
log "Packaging quota publisher Lambda..."
cd "$QUOTA_DIR"
rm -f function.zip
zip -q function.zip lambda_function.py
aws s3 cp function.zip "s3://${BUCKET}/lambda/quota-publisher.zip" --region "$REGION" > /dev/null
ok "Uploaded quota-publisher.zip"

# Helper: deploy or update a CloudFormation stack
deploy_stack() {
  local stack_name="$1"
  local template="$2"
  shift 2
  local params=("$@")

  local status
  status=$(aws cloudformation describe-stacks \
    --stack-name "$stack_name" --region "$REGION" \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

  if [[ "$status" == "DOES_NOT_EXIST" ]]; then
    log "Creating stack: $stack_name ..."
    aws cloudformation create-stack \
      --stack-name "$stack_name" \
      --template-body "file://${template}" \
      --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
      --parameters "${params[@]}" \
      --region "$REGION" > /dev/null
    aws cloudformation wait stack-create-complete \
      --stack-name "$stack_name" --region "$REGION"
    ok "Stack created: $stack_name"
  elif [[ "$status" =~ (ROLLBACK_COMPLETE|CREATE_FAILED) ]]; then
    fail "Stack $stack_name is in state $status. Delete it first."
  else
    log "Updating stack: $stack_name (status: $status) ..."
    local update_out
    update_out=$(aws cloudformation update-stack \
      --stack-name "$stack_name" \
      --template-body "file://${template}" \
      --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
      --parameters "${params[@]}" \
      --region "$REGION" 2>&1 || true)
    if echo "$update_out" | grep -q "No updates are to be performed"; then
      ok "Stack already up to date: $stack_name"
    else
      aws cloudformation wait stack-update-complete \
        --stack-name "$stack_name" --region "$REGION"
      ok "Stack updated: $stack_name"
    fi
  fi
}

# Helper: get CloudFormation output
get_output() {
  aws cloudformation describe-stacks \
    --stack-name "$1" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" \
    --output text
}

hr
log "Step 1/4: VPC + Networking"
deploy_stack "${STACK_BASE}-vpc" "$CFN_DIR/01-vpc.yaml" \
  "ParameterKey=StackPrefix,ParameterValue=${PREFIX}"

hr
log "Step 2/4: ECS Fargate + ALB + EFS"
# Upload ADOT config to S3
log "Uploading ADOT collector config to S3..."
aws s3 cp "$ROOT_DIR/otel/collector-config.yaml" \
  "s3://${BUCKET}/config/adot-collector.yaml" \
  --region "$REGION" > /dev/null
ok "Uploaded adot-collector.yaml"

deploy_stack "${STACK_BASE}-ecs" "$CFN_DIR/02-ecs.yaml" \
  "ParameterKey=StackPrefix,ParameterValue=${PREFIX}" \
  "ParameterKey=BifrostEncryptionKey,ParameterValue=${ENCRYPTION_KEY}" \
  "ParameterKey=S3ArtifactBucket,ParameterValue=${BUCKET}"

ALB_DNS=$(get_output "${STACK_BASE}-ecs" "AlbDnsName")
ok "ALB (internal): $ALB_DNS"

hr
log "Step 3/4: CloudFront + Cognito + S3 (us-east-1 only)"
CF_PARAMS=(
  "ParameterKey=StackPrefix,ParameterValue=${PREFIX}"
  "ParameterKey=AdminEmail,ParameterValue=${ADMIN_EMAIL:-admin@example.com}"
)
[[ -n "$CUSTOM_DOMAIN" ]] && CF_PARAMS+=("ParameterKey=CustomDomain,ParameterValue=${CUSTOM_DOMAIN}")
deploy_stack "${STACK_BASE}-cf" "$CFN_DIR/03-cloudfront.yaml" "${CF_PARAMS[@]}"

CF_DOMAIN=$(get_output "${STACK_BASE}-cf" "CloudFrontDomainName")
CHATBOX_BUCKET=$(get_output "${STACK_BASE}-cf" "ChatboxBucketName")
ADMIN_UI_URL=$(get_output "${STACK_BASE}-cf" "AdminUiUrl")
COGNITO_POOL=$(get_output "${STACK_BASE}-cf" "CognitoUserPoolId")
ok "CloudFront: https://$CF_DOMAIN"
ok "Admin UI:   $ADMIN_UI_URL"

hr
log "Step 4/4: CloudWatch Observability"
OBS_PARAMS=(
  "ParameterKey=StackPrefix,ParameterValue=${PREFIX}"
  "ParameterKey=S3ArtifactBucket,ParameterValue=${BUCKET}"
)
[[ -n "$ALARM_EMAIL" ]] && OBS_PARAMS+=("ParameterKey=AlarmEmail,ParameterValue=${ALARM_EMAIL}")
deploy_stack "${STACK_BASE}-obs" "$CFN_DIR/04-observability.yaml" "${OBS_PARAMS[@]}"

DASHBOARD_URL=$(get_output "${STACK_BASE}-obs" "DashboardUrl")
ok "Dashboard: $DASHBOARD_URL"

# ── Upload chatbox.html to S3 ─────────────────────────────────────
hr
log "Uploading chatbox.html to S3..."
# Patch the placeholder API endpoint in chatbox.html before upload
CHATBOX_TMP=$(mktemp /tmp/chatbox-XXXXXX.html)
cp "$CHATBOX_DIR/chatbox.html" "$CHATBOX_TMP"

# Replace API endpoint placeholder
sed -i.bak "s|BIFROST_API_ENDPOINT_PLACEHOLDER|https://${CF_DOMAIN}|g" "$CHATBOX_TMP"

# Upload to S3 (virtual keys are set AFTER Bifrost is configured via UI)
aws s3 cp "$CHATBOX_TMP" "s3://${CHATBOX_BUCKET}/chatbox.html" \
  --content-type "text/html" \
  --cache-control "no-cache" \
  --region "$REGION" > /dev/null
rm -f "$CHATBOX_TMP" "${CHATBOX_TMP}.bak"
ok "chatbox.html uploaded to s3://$CHATBOX_BUCKET"

# Invalidate CloudFront cache for chatbox
CF_DIST_ID=$(get_output "${STACK_BASE}-cf" "CloudFrontDistributionId")
aws cloudfront create-invalidation \
  --distribution-id "$CF_DIST_ID" \
  --paths "/*" > /dev/null
ok "CloudFront cache invalidated"

# ── Summary ───────────────────────────────────────────────────────
hr
cat <<EOF
╔══════════════════════════════════════════════════════════════════════╗
║         BIFROST AI GATEWAY — DEPLOYMENT COMPLETE                    ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Chat UI:     https://${CF_DOMAIN}
║  Admin UI:    $ADMIN_UI_URL
║  Dashboard:   $DASHBOARD_URL
║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  NEXT STEPS — Configure Bifrost via Admin UI:                        ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  1. Sign in at Admin UI (check your email: ${ADMIN_EMAIL:-admin@example.com})
║     Cognito Pool ID: $COGNITO_POOL
║                                                                      ║
║  2. Add AWS Bedrock provider:                                        ║
║     Providers → Add Provider → Select "bedrock"                     ║
║     Auth: IAM Role (ECS task role — no keys needed)                 ║
║     Region: $REGION                                                 ║
║                                                                      ║
║  3. Create virtual key for Team Alpha:                               ║
║     Virtual Keys → New Key → name: team-alpha                       ║
║     Models: claude-haiku-4-5*, claude-sonnet-4-5*                   ║
║     Daily budget: 100,000 tokens                                     ║
║                                                                      ║
║  4. Create virtual key for Team Beta:                                ║
║     Virtual Keys → New Key → name: team-beta                        ║
║     Models: claude-haiku-4-5* only                                  ║
║     Daily budget: 50,000 tokens                                      ║
║                                                                      ║
║  5. Copy the virtual key values and run:                             ║
║     ./update-chatbox-keys.sh <alpha-key> <beta-key>                 ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
EOF

# ── Write key update helper script ────────────────────────────────
cat > "$SCRIPT_DIR/update-chatbox-keys.sh" <<'HELPER'
#!/usr/bin/env bash
# Usage: ./update-chatbox-keys.sh <alpha-virtual-key> <beta-virtual-key>
set -euo pipefail
ALPHA_KEY="$1"
BETA_KEY="$2"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHATBOX_SRC="$ROOT_DIR/chatbox/chatbox.html"

# Get values from deployed stacks
REGION="${REGION:-us-east-1}"
STACK_BASE="bifrost-gw"
CF_DOMAIN=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_BASE}-cf" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDomainName'].OutputValue" \
  --output text)
CHATBOX_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_BASE}-cf" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ChatboxBucketName'].OutputValue" \
  --output text)
CF_DIST_ID=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_BASE}-cf" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" \
  --output text)

TMP=$(mktemp /tmp/chatbox-XXXXXX.html)
cp "$CHATBOX_SRC" "$TMP"
sed -i.bak "s|BIFROST_API_ENDPOINT_PLACEHOLDER|https://${CF_DOMAIN}|g" "$TMP"
sed -i.bak "s|BIFROST_ALPHA_VIRTUAL_KEY_PLACEHOLDER|${ALPHA_KEY}|g" "$TMP"
sed -i.bak "s|BIFROST_BETA_VIRTUAL_KEY_PLACEHOLDER|${BETA_KEY}|g" "$TMP"

aws s3 cp "$TMP" "s3://${CHATBOX_BUCKET}/chatbox.html" \
  --content-type "text/html" \
  --cache-control "no-cache" \
  --region "$REGION" > /dev/null

aws cloudfront create-invalidation \
  --distribution-id "$CF_DIST_ID" \
  --paths "/chatbox.html" > /dev/null

rm -f "$TMP" "${TMP}.bak"
echo "✅ chatbox.html updated with live virtual keys."
echo "   Open: https://${CF_DOMAIN}"
HELPER
chmod +x "$SCRIPT_DIR/update-chatbox-keys.sh"

ok "Run ./update-chatbox-keys.sh <alpha-key> <beta-key> after configuring Bifrost."
