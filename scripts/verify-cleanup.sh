#!/bin/bash
# ============================================================================
# Verify Cleanup — Confirm nothing is left running in your account
# ============================================================================
# Use this after tearing down a demo to verify no resources remain.
# Safe to run anytime — read-only checks only.
#
# Usage: ./scripts/verify-cleanup.sh [REGION]
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

REGION="${1:-${AWS_REGION:-us-east-1}}"
PREFIX="mcp-demo"
DEMO2_STACK="${STACK_NAME:-mcp-gateway-demo}"
FOUND=0

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Verify Cleanup — Check for Leftover Resources       ║"
echo "║           Region: $REGION                                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

pass() { echo -e "  ${GREEN}✓${NC} $1"; }
found() { echo -e "  ${RED}✗${NC} $1"; FOUND=$((FOUND + 1)); }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }

# ─────────────────────────────────────────────
# Demo 1 Resources
# ─────────────────────────────────────────────
echo "━━━ Demo 1: AgentCore Gateway Resources ━━━"

# CloudFormation stack
if aws cloudformation describe-stacks --stack-name "$PREFIX" --region "$REGION" &>/dev/null 2>&1; then
  found "CloudFormation stack '$PREFIX' still exists → Run: aws cloudformation delete-stack --stack-name $PREFIX --region $REGION"
else
  pass "CloudFormation stack '$PREFIX' deleted"
fi

# Lambda functions
for fn in "${PREFIX}-ecommerce-mcp" "${PREFIX}-products-mcp" "${PREFIX}-orders-mcp" "${PREFIX}-jira-mcp" "${PREFIX}-registry"; do
  if aws lambda get-function --function-name "$fn" --region "$REGION" &>/dev/null 2>&1; then
    found "Lambda function '$fn' still exists"
  else
    pass "Lambda '$fn' deleted"
  fi
done

# IAM users
for user in "${PREFIX}-readonly" "${PREFIX}-fullaccess"; do
  if aws iam get-user --user-name "$user" &>/dev/null 2>&1; then
    found "IAM user '$user' still exists → Run: aws iam delete-user --user-name $user"
  else
    pass "IAM user '$user' deleted"
  fi
done

# IAM roles
for role in "${PREFIX}-lambda-role" "${PREFIX}-gateway-role" "${PREFIX}-registry-role"; do
  if aws iam get-role --role-name "$role" &>/dev/null 2>&1; then
    found "IAM role '$role' still exists"
  else
    pass "IAM role '$role' deleted"
  fi
done

# AgentCore Gateway (check via CLI state file)
DEPLOYED_STATE="gateway-url-ide-integration-demo/DemoMcpGateway/agentcore/.cli/deployed-state.json"
if [ -f "$DEPLOYED_STATE" ]; then
  warn "AgentCore deployed-state.json exists locally. If you haven't run 'agentcore destroy', the gateway may still be active."
else
  pass "No local AgentCore state file"
fi

echo ""

# ─────────────────────────────────────────────
# Demo 2 Resources
# ─────────────────────────────────────────────
echo "━━━ Demo 2: Team RBAC Chat Resources ━━━"

# CloudFormation stack
if aws cloudformation describe-stacks --stack-name "$DEMO2_STACK" --region "$REGION" &>/dev/null 2>&1; then
  found "CloudFormation stack '$DEMO2_STACK' still exists → Run: make destroy-demo2"
else
  pass "CloudFormation stack '$DEMO2_STACK' deleted"
fi

# Lambda function
DEMO2_FN="${DEMO2_STACK}-proxy"
if aws lambda get-function --function-name "$DEMO2_FN" --region "$REGION" &>/dev/null 2>&1; then
  found "Lambda function '$DEMO2_FN' still exists"
else
  pass "Lambda '$DEMO2_FN' deleted"
fi

# API Gateway (check by name pattern)
DEMO2_APIS=$(aws apigateway get-rest-apis --region "$REGION" --query "items[?name=='${DEMO2_STACK}-api'].id" --output text 2>/dev/null || echo "")
if [ -n "$DEMO2_APIS" ] && [ "$DEMO2_APIS" != "None" ]; then
  found "API Gateway '${DEMO2_STACK}-api' still exists (ID: $DEMO2_APIS)"
else
  pass "API Gateway '${DEMO2_STACK}-api' deleted"
fi

echo ""

# ─────────────────────────────────────────────
# CloudWatch Log Groups
# ─────────────────────────────────────────────
echo "━━━ CloudWatch Log Groups ━━━"

for lg in "/aws/lambda/${PREFIX}-ecommerce-mcp" "/aws/lambda/${PREFIX}-products-mcp" "/aws/lambda/${PREFIX}-orders-mcp" "/aws/lambda/${PREFIX}-jira-mcp" "/aws/lambda/${PREFIX}-registry" "/aws/lambda/${DEMO2_STACK}-proxy"; do
  if aws logs describe-log-groups --log-group-name-prefix "$lg" --region "$REGION" --query "logGroups[?logGroupName=='$lg']" --output text 2>/dev/null | grep -q "$lg"; then
    warn "Log group '$lg' still exists (non-critical, costs ~$0.03/GB stored)"
  else
    pass "Log group '$lg' deleted"
  fi
done

echo ""

# ─────────────────────────────────────────────
# Local Artifacts
# ─────────────────────────────────────────────
echo "━━━ Local Artifacts ━━━"

CRED_FILES=$(find . -name ".credentials-*" 2>/dev/null)
if [ -n "$CRED_FILES" ]; then
  warn "Credentials file(s) found locally: $CRED_FILES → Delete after adding to ~/.aws/credentials"
else
  pass "No local credentials files"
fi

if [ -d "build/" ]; then
  warn "build/ directory exists → Run: make clean"
else
  pass "No build artifacts"
fi

echo ""

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ $FOUND -eq 0 ]; then
  echo -e "${GREEN}✅ All clear! No demo resources found in account.${NC}"
  echo "   Your account is clean — no ongoing charges from this demo."
else
  echo -e "${RED}⚠️  $FOUND resource(s) still exist in your account.${NC}"
  echo ""
  echo "To fully clean up:"
  echo "  Demo 1: aws cloudformation delete-stack --stack-name $PREFIX --region $REGION"
  echo "  Demo 2: make destroy-demo2"
  echo "  AgentCore: cd gateway-url-ide-integration-demo/DemoMcpGateway/agentcore && agentcore destroy"
  echo ""
  echo "Then run this script again to verify."
fi

echo ""
