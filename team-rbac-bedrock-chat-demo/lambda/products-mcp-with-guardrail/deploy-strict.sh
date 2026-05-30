#!/bin/bash
# Deploy Products MCP with STRICT guardrail (blocks Swedish words)

set -e

REGION=${AWS_REGION:-us-east-1}
FUNCTION_NAME="demo-products-mcp-strict"
GUARDRAIL_ID=${GUARDRAIL_ID:-"<YOUR_STRICT_GUARDRAIL_ID>"}  # mcp-strict-english-only

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       Deploy Products MCP with STRICT Guardrail               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Function: $FUNCTION_NAME"
echo "Guardrail: $GUARDRAIL_ID (mcp-strict-english-only)"
echo "Behavior: English-only content filter"
echo ""

# Get IAM role ARN from CloudFormation
ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name mcp-gateway-demo \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`MCPServerRoleArn`].OutputValue' \
  --output text)

if [ -z "$ROLE_ARN" ]; then
  echo "❌ Error: Could not find MCPServerRoleArn from CloudFormation"
  exit 1
fi

echo "IAM Role: $ROLE_ARN"
echo ""

# Package Lambda
echo "📦 Packaging Lambda..."
zip -q function.zip lambda_function.py

# Check if function exists
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" &>/dev/null; then
  echo "🔄 Updating existing function..."
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://function.zip \
    --region "$REGION" \
    --no-cli-pager

  # Update environment variables
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --environment "Variables={GUARDRAIL_ID=$GUARDRAIL_ID,GUARDRAIL_VERSION=DRAFT}" \
    --region "$REGION" \
    --no-cli-pager

  echo "✅ Function updated: $FUNCTION_NAME"
else
  echo "🆕 Creating new function..."
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.11 \
    --role "$ROLE_ARN" \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://function.zip \
    --timeout 30 \
    --memory-size 256 \
    --environment "Variables={GUARDRAIL_ID=$GUARDRAIL_ID,GUARDRAIL_VERSION=DRAFT}" \
    --region "$REGION" \
    --no-cli-pager

  echo "✅ Function created: $FUNCTION_NAME"
fi

# Cleanup
rm function.zip

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    Deployment Complete                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ STRICT mode deployed"
echo "📍 Function: $FUNCTION_NAME"
echo "🛡️  Guardrail: mcp-strict-english-only"
echo ""
echo "Test it:"
echo "aws lambda invoke \\"
echo "  --function-name $FUNCTION_NAME \\"
echo "  --cli-binary-format raw-in-base64-out \\"
echo "  --payload '{\"method\":\"tools/call\",\"params\":{\"name\":\"demo-products-mcp___get_product_by_id\",\"arguments\":{\"product_id\":\"PROD-002\"}}}' \\"
echo "  --region $REGION \\"
echo "  /tmp/output.json && cat /tmp/output.json | jq ."
echo ""
