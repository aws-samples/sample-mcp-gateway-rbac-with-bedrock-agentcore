#!/bin/bash
# Deploy all MCP Server Lambda functions for the OAuth demo path.
# Usage: ./deploy-oauth.sh [REGION] [PREFIX]
# Called by ../../deploy.sh — uses the CFN-created role.

set -e

REGION="${1:-us-east-1}"
PREFIX="${2:-mcp-demo}"
STACK_NAME="mcp-gateway-oauth-demo"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Deploying Lambda MCP servers (prefix: ${PREFIX})..."

# Get the Lambda execution role from our CFN stack
ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='RegistryLambdaArn'].OutputValue" --output text 2>/dev/null || echo "")

# If no dedicated role from CFN, use a generic one
if [ -z "$ROLE_ARN" ] || [ "$ROLE_ARN" = "None" ]; then
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
  ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${PREFIX}-registry-role"
fi

deploy_lambda() {
  local name="${PREFIX}-${1}"
  local dir="$SCRIPT_DIR/${2}"

  if aws lambda get-function --function-name "$name" --region "$REGION" &>/dev/null; then
    (cd "$dir" && zip -q function.zip lambda_function.py && \
     aws lambda update-function-code --function-name "$name" --zip-file fileb://function.zip --region "$REGION" --no-cli-pager > /dev/null && \
     rm function.zip)
    echo "  🔄 Updated: $name"
  else
    (cd "$dir" && zip -q function.zip lambda_function.py && \
     aws lambda create-function \
       --function-name "$name" \
       --runtime python3.11 \
       --role "$ROLE_ARN" \
       --handler lambda_function.lambda_handler \
       --zip-file fileb://function.zip \
       --timeout 30 --memory-size 256 \
       --region "$REGION" --no-cli-pager > /dev/null && \
     rm function.zip)
    echo "  ✅ Created: $name"
  fi
}

deploy_lambda "ecommerce-mcp" "ecommerce-mcp"
deploy_lambda "products-mcp"  "products-mcp"
deploy_lambda "orders-mcp"    "orders-mcp"
deploy_lambda "jira-mcp"      "jira-mcp"

echo "✅ All Lambda MCP servers deployed."
