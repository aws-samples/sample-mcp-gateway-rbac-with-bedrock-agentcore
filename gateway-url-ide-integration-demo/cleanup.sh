#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Tear down: removes everything deploy.sh created
# Usage: ./cleanup.sh [REGION]
# ============================================================================

REGION="${1:-us-east-1}"
STACK_NAME="mcp-gateway-oauth-demo"
PREFIX="mcp-demo"

echo "⚠️  This will delete ALL demo resources in $REGION."
read -p "Continue? (y/N) " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || exit 0

echo ""
echo "Deleting Lambda MCP servers..."
for fn in products-mcp orders-mcp ecommerce-mcp jira-mcp; do
    aws lambda delete-function --function-name "${PREFIX}-${fn}" --region "$REGION" 2>/dev/null && echo "  ✅ ${fn}" || echo "  ⏭️  ${fn} (not found)"
done

echo ""
echo "Deleting AgentCore Gateway + policies..."
python3 scripts/cleanup-gateway.py --region "$REGION" --prefix "$PREFIX" 2>/dev/null || echo "  ⏭️  gateway cleanup skipped"

echo ""
echo "Deleting CloudFormation stack..."
aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION" 2>/dev/null || true
echo "  ✅ Stack deleted"

echo ""
echo "Deleting IAM role..."
aws iam delete-role-policy --role-name "${PREFIX}-gateway-role" --policy-name GatewayAccess 2>/dev/null || true
aws iam delete-role --role-name "${PREFIX}-gateway-role" 2>/dev/null && echo "  ✅ IAM role" || echo "  ⏭️  role (not found)"

echo ""
echo "✅ Cleanup complete."
