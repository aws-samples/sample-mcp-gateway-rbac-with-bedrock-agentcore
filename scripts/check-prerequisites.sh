#!/bin/bash
# Prerequisites Check Script
# Validates that all required tools and access are available before deployment.
#
# Usage: ./scripts/check-prerequisites.sh [--demo1] [--demo2] [--all]
#   --demo1  Check prerequisites for Demo 1 (AgentCore Gateway + VS Code)
#   --demo2  Check prerequisites for Demo 2 (Team RBAC + Browser Chat)
#   --all    Check all prerequisites (default)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

pass() { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; ERRORS=$((ERRORS + 1)); }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; WARNINGS=$((WARNINGS + 1)); }

# Parse arguments
CHECK_DEMO1=false
CHECK_DEMO2=false

case "${1:-all}" in
  --demo1) CHECK_DEMO1=true ;;
  --demo2) CHECK_DEMO2=true ;;
  --all|"") CHECK_DEMO1=true; CHECK_DEMO2=true ;;
  *)
    echo "Usage: $0 [--demo1] [--demo2] [--all]"
    exit 1
    ;;
esac

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Prerequisites Check - MCP Gateway Demo              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# ─────────────────────────────────────────────
# Common Prerequisites
# ─────────────────────────────────────────────
echo "━━━ Common Prerequisites ━━━"

# AWS CLI
if command -v aws &>/dev/null; then
  AWS_VERSION=$(aws --version 2>&1 | head -1)
  pass "AWS CLI installed: $AWS_VERSION"
else
  fail "AWS CLI not installed. Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
fi

# AWS credentials
if aws sts get-caller-identity &>/dev/null 2>&1; then
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
  IDENTITY=$(aws sts get-caller-identity --query Arn --output text 2>/dev/null)
  pass "AWS credentials configured (Account: $ACCOUNT_ID)"
  pass "Identity: $IDENTITY"
else
  fail "AWS credentials not configured or expired. Run: aws configure"
fi

# Python
if command -v python3 &>/dev/null; then
  PY_VERSION=$(python3 --version 2>&1)
  PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.minor)")
  if [ "$PY_MAJOR" -ge 11 ]; then
    pass "Python: $PY_VERSION"
  else
    fail "Python 3.11+ required, found: $PY_VERSION"
  fi
else
  fail "Python 3 not installed"
fi

# pip/boto3
if python3 -c "import boto3" &>/dev/null 2>&1; then
  pass "boto3 installed"
else
  warn "boto3 not installed. Run: pip install boto3"
fi

# zip
if command -v zip &>/dev/null; then
  pass "zip command available"
else
  fail "zip not installed (needed for Lambda packaging)"
fi

# jq (optional but helpful)
if command -v jq &>/dev/null; then
  pass "jq installed (optional, for JSON parsing)"
else
  warn "jq not installed (optional). Install: brew install jq"
fi

echo ""

# ─────────────────────────────────────────────
# AWS Service Access
# ─────────────────────────────────────────────
echo "━━━ AWS Service Access ━━━"

# Check region
REGION=${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}
pass "Target region: $REGION"

# Lambda access
if aws lambda list-functions --max-items 1 --region "$REGION" &>/dev/null 2>&1; then
  pass "Lambda access confirmed"
else
  fail "Cannot access AWS Lambda. Check IAM permissions."
fi

# CloudFormation access
if aws cloudformation list-stacks --max-items 1 --region "$REGION" &>/dev/null 2>&1; then
  pass "CloudFormation access confirmed"
else
  fail "Cannot access CloudFormation. Check IAM permissions."
fi

# Bedrock access
if aws bedrock list-foundation-models --max-results 1 --region "$REGION" &>/dev/null 2>&1; then
  pass "Bedrock access confirmed"
else
  warn "Cannot access Bedrock. You may need to enable model access in the Bedrock console."
fi

echo ""

# ─────────────────────────────────────────────
# Demo 1 Prerequisites
# ─────────────────────────────────────────────
if [ "$CHECK_DEMO1" = true ]; then
  echo "━━━ Demo 1: AgentCore Gateway + VS Code ━━━"

  # Node.js
  if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version)
    NODE_MAJOR=$(echo "$NODE_VERSION" | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
      pass "Node.js: $NODE_VERSION"
    else
      fail "Node.js 18+ required, found: $NODE_VERSION"
    fi
  else
    fail "Node.js not installed. Install: https://nodejs.org/"
  fi

  # npm
  if command -v npm &>/dev/null; then
    pass "npm: $(npm --version)"
  else
    fail "npm not installed"
  fi

  # AgentCore CLI
  if command -v agentcore &>/dev/null; then
    pass "AgentCore CLI installed: $(agentcore --version 2>/dev/null || echo 'version unknown')"
  else
    warn "AgentCore CLI not installed. Install: npm install -g @aws/agentcore-cli"
    warn "Note: AgentCore is a preview service. Contact AWS for access."
  fi

  # AgentCore service access
  if aws bedrock-agent list-agents --max-results 1 --region "$REGION" &>/dev/null 2>&1; then
    pass "Bedrock Agent access confirmed"
  else
    warn "Cannot verify AgentCore access. This is a preview service — contact your AWS account team."
  fi

  # VS Code (optional check)
  if command -v code &>/dev/null; then
    pass "VS Code CLI available"
  else
    warn "VS Code CLI not in PATH (optional — you can still use VS Code manually)"
  fi

  echo ""
fi

# ─────────────────────────────────────────────
# Demo 2 Prerequisites
# ─────────────────────────────────────────────
if [ "$CHECK_DEMO2" = true ]; then
  echo "━━━ Demo 2: Team RBAC + Browser Chat ━━━"

  # S3 access (for Lambda code upload)
  if aws s3 ls --region "$REGION" &>/dev/null 2>&1; then
    pass "S3 access confirmed"
  else
    fail "Cannot access S3. Needed for Lambda deployment packages."
  fi

  # IAM access (for role creation)
  if aws iam list-roles --max-items 1 &>/dev/null 2>&1; then
    pass "IAM access confirmed"
  else
    fail "Cannot access IAM. Needed for creating team roles."
  fi

  # API Gateway access
  if aws apigatewayv2 get-apis --max-results 1 --region "$REGION" &>/dev/null 2>&1; then
    pass "API Gateway V2 access confirmed"
  else
    fail "Cannot access API Gateway V2. Check IAM permissions."
  fi

  # Check if Bedrock models are enabled
  if aws bedrock list-foundation-models --region "$REGION" --query "modelSummaries[?modelId=='anthropic.claude-3-5-haiku-20241022-v1:0']" --output text 2>/dev/null | grep -q "anthropic"; then
    pass "Claude 3.5 Haiku model available"
  else
    warn "Could not verify Claude 3.5 Haiku availability. Enable it in the Bedrock console."
  fi

  echo ""
fi

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
  echo -e "${GREEN}All prerequisites met! You're ready to deploy.${NC}"
  echo ""
  echo "Next steps:"
  if [ "$CHECK_DEMO1" = true ]; then
    echo "  Demo 1: cd gateway-url-ide-integration-demo && cat DEPLOYMENT.md"
  fi
  if [ "$CHECK_DEMO2" = true ]; then
    echo "  Demo 2: cd team-rbac-bedrock-chat-demo && cat DEPLOYMENT.md"
  fi
elif [ $ERRORS -eq 0 ]; then
  echo -e "${YELLOW}Prerequisites met with $WARNINGS warning(s).${NC}"
  echo "Warnings are non-blocking but may affect some features."
else
  echo -e "${RED}$ERRORS error(s) found. Fix these before deploying.${NC}"
  if [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}Also $WARNINGS warning(s) to review.${NC}"
  fi
  exit 1
fi

echo ""
