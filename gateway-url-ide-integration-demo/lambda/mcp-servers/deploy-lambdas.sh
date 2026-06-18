#!/bin/bash
# Deploy Lambda code to existing functions (created by CloudFormation)
#
# Prerequisites: CloudFormation stack already deployed (demo1-stack.yaml)
# Usage: ./deploy-lambdas.sh [REGION] [STACK_PREFIX]

set -e

REGION="${1:-${AWS_REGION:-us-east-1}}"
PREFIX="${2:-mcp-demo}"

echo "Deploying Lambda code to existing functions..."
echo "Region: $REGION | Prefix: $PREFIX"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

deploy_code() {
  local name="${PREFIX}-${1}"
  local dir="${SCRIPT_DIR}/${2}"

  echo -n "  ${name}... "
  (cd "$dir" && zip -q function.zip lambda_function.py)
  aws lambda update-function-code \
    --function-name "$name" \
    --zip-file "fileb://${dir}/function.zip" \
    --region "$REGION" \
    --no-cli-pager > /dev/null
  rm -f "${dir}/function.zip"
  echo "✅"
}

deploy_code "ecommerce-mcp" "ecommerce-mcp"
deploy_code "products-mcp" "products-mcp"
deploy_code "orders-mcp" "orders-mcp"
deploy_code "jira-mcp" "jira-mcp"

echo ""
echo "✅ All Lambda code deployed. Functions are ready for AgentCore Gateway."
