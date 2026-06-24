#!/bin/bash
# Cleanup all demo resources

set -e

REGION=${AWS_REGION:-us-east-1}
STACK_NAME="mcp-gateway-demo"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              Cleanup MCP Gateway Demo Resources               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "⚠️  This will DELETE all demo resources:"
echo "   • CloudFormation stack: $STACK_NAME"
echo "   • Lambda functions: demo-ecommerce-mcp, demo-products-mcp, demo-orders-mcp"
echo "   • Lambda function: mcp-gateway-proxy"
echo "   • AgentCore Gateway and targets"
echo "   • IAM roles"
echo ""
read -p "Are you sure? (type 'yes' to confirm): " confirm

if [ "$confirm" != "yes" ]; then
  echo "Aborted."
  exit 0
fi

echo ""
echo "🧹 Starting cleanup..."
echo ""

# Delete Lambda functions
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Deleting Lambda functions"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

for func in demo-ecommerce-mcp demo-products-mcp demo-orders-mcp mcp-gateway-proxy; do
  if aws lambda get-function --function-name "$func" --region "$REGION" &>/dev/null; then
    echo "🗑️  Deleting: $func"
    aws lambda delete-function \
      --function-name "$func" \
      --region "$REGION" \
      --no-cli-pager
    echo "✅ Deleted: $func"
  else
    echo "⏭️  Skipping: $func (not found)"
  fi
done

echo ""

# Delete AgentCore Gateway (placeholder - manual step)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: AgentCore Gateway Cleanup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  Manual step required:"
echo "   1. Go to AWS Console → Bedrock → AgentCore"
echo "   2. Delete gateway: demo-mcp-gateway"
echo "   3. Delete targets: demo-ecommerce-mcp, demo-products-mcp, demo-orders-mcp"
echo ""
read -p "Press Enter when done (or Ctrl+C to skip)..."
echo ""

# Delete CloudFormation stack
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Deleting CloudFormation Stack"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &>/dev/null; then
  echo "🗑️  Deleting stack: $STACK_NAME"
  aws cloudformation delete-stack \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --no-cli-pager

  echo "⏳ Waiting for stack deletion..."
  aws cloudformation wait stack-delete-complete \
    --stack-name "$STACK_NAME" \
    --region "$REGION"

  echo "✅ Stack deleted: $STACK_NAME"
else
  echo "⏭️  Stack not found: $STACK_NAME"
fi

echo ""

# Cleanup local temporary files
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4: Cleanup Local Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -d "tmp" ]; then
  echo "🗑️  Removing tmp/ directory"
  rm -rf tmp/
  echo "✅ Removed: tmp/"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    Cleanup Complete                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ All resources cleaned up"
echo ""
