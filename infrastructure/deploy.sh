#!/bin/bash

################################################################################
# Bedrock Governance Demos - One-Click Deployment Script
#
# This script automates the complete deployment process:
# 1. Package Lambda functions
# 2. Upload artifacts to S3
# 3. Deploy CloudFormation master stack
# 4. Output configuration values
#
# Usage:
#   ./deploy.sh [OPTIONS]
#
# Options:
#   --project-name NAME      Project name (default: bedrock-governance-demo)
#   --environment ENV        Environment: dev/staging/prod (default: dev)
#   --region REGION          AWS region (default: us-east-1)
#   --demo1-only             Deploy only Demo #1 (AgentCore Gateway)
#   --demo2-only             Deploy only Demo #2 (Browser Chat)
#   --skip-lambda-package    Skip Lambda packaging (use existing S3 artifacts)
#   --no-waf                 Disable WAF deployment
#   --no-guardrails          Disable Bedrock Guardrails
#   --help                   Show this help message
#
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PROJECT_NAME="bedrock-governance-demo"
ENVIRONMENT="dev"
AWS_REGION="us-east-1"
DEPLOY_DEMO1="true"
DEPLOY_DEMO2="true"
SKIP_LAMBDA_PACKAGE="false"
ENABLE_WAF="true"
ENABLE_GUARDRAILS="true"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --project-name)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --demo1-only)
            DEPLOY_DEMO2="false"
            shift
            ;;
        --demo2-only)
            DEPLOY_DEMO1="false"
            shift
            ;;
        --skip-lambda-package)
            SKIP_LAMBDA_PACKAGE="true"
            shift
            ;;
        --no-waf)
            ENABLE_WAF="false"
            shift
            ;;
        --no-guardrails)
            ENABLE_GUARDRAILS="false"
            shift
            ;;
        --help)
            head -n 28 "$0" | tail -n +3 | sed 's/^# //'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Derived values
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ARTIFACT_BUCKET="${PROJECT_NAME}-${ENVIRONMENT}-artifacts-${ACCOUNT_ID}"
STACK_NAME="${PROJECT_NAME}-${ENVIRONMENT}-master"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Bedrock Governance Demos - Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo -e "  Project Name:    ${PROJECT_NAME}"
echo -e "  Environment:     ${ENVIRONMENT}"
echo -e "  AWS Region:      ${AWS_REGION}"
echo -e "  AWS Account:     ${ACCOUNT_ID}"
echo -e "  Artifact Bucket: ${ARTIFACT_BUCKET}"
echo -e "  Deploy Demo #1:  ${DEPLOY_DEMO1}"
echo -e "  Deploy Demo #2:  ${DEPLOY_DEMO2}"
echo -e "  Enable WAF:      ${ENABLE_WAF}"
echo -e "  Enable Guardrails: ${ENABLE_GUARDRAILS}"
echo ""

# Check prerequisites
echo -e "${BLUE}[1/6] Checking prerequisites...${NC}"
command -v aws >/dev/null 2>&1 || { echo -e "${RED}AWS CLI not found${NC}"; exit 1; }
command -v zip >/dev/null 2>&1 || { echo -e "${RED}zip not found${NC}"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}Python 3 not found${NC}"; exit 1; }
echo -e "${GREEN}✓ All prerequisites met${NC}"

# Create S3 bucket if it doesn't exist
echo ""
echo -e "${BLUE}[2/6] Setting up S3 artifact bucket...${NC}"
if aws s3 ls "s3://${ARTIFACT_BUCKET}" 2>&1 | grep -q 'NoSuchBucket'; then
    echo "Creating bucket: ${ARTIFACT_BUCKET}"
    aws s3 mb "s3://${ARTIFACT_BUCKET}" --region "${AWS_REGION}"
    aws s3api put-bucket-encryption \
        --bucket "${ARTIFACT_BUCKET}" \
        --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
    echo -e "${GREEN}✓ Bucket created${NC}"
else
    echo -e "${GREEN}✓ Bucket already exists${NC}"
fi

# Package Lambda functions
if [ "$SKIP_LAMBDA_PACKAGE" = "false" ]; then
    echo ""
    echo -e "${BLUE}[3/6] Packaging Lambda functions...${NC}"

    LAMBDA_DIR="${REPO_ROOT}/lambda"
    BUILD_DIR="${REPO_ROOT}/build"

    mkdir -p "${BUILD_DIR}"

    # Package Demo #1 MCP servers
    if [ "$DEPLOY_DEMO1" = "true" ]; then
        echo "Packaging Demo #1 Lambda MCPs..."
        for MCP_DIR in "${LAMBDA_DIR}/mcp-servers"/*; do
            if [ -d "$MCP_DIR" ]; then
                MCP_NAME=$(basename "$MCP_DIR")
                echo "  - ${MCP_NAME}"

                cd "$MCP_DIR"
                zip -r "${BUILD_DIR}/${MCP_NAME}.zip" . -x "*.pyc" -x "__pycache__/*" -x "tests/*" -x "*.git*" >/dev/null
            fi
        done
    fi

    # Package Demo #2 gateway proxy
    if [ "$DEPLOY_DEMO2" = "true" ]; then
        echo "Packaging Demo #2 gateway proxy..."
        PROXY_DIR="${REPO_ROOT}/team-rbac-bedrock-chat-demo/lambda/gateway-proxy"
        cd "$PROXY_DIR"
        zip -r "${BUILD_DIR}/gateway-proxy.zip" . -x "*.pyc" -x "__pycache__/*" -x "tests/*" -x "*.git*" >/dev/null
    fi

    echo -e "${GREEN}✓ Lambda functions packaged${NC}"
else
    echo ""
    echo -e "${YELLOW}[3/6] Skipping Lambda packaging (using existing S3 artifacts)${NC}"
fi

# Upload artifacts to S3
echo ""
echo -e "${BLUE}[4/6] Uploading artifacts to S3...${NC}"

# Upload Lambda code
if [ "$SKIP_LAMBDA_PACKAGE" = "false" ]; then
    aws s3 sync "${BUILD_DIR}" "s3://${ARTIFACT_BUCKET}/lambda/" --exclude "*" --include "*.zip" --delete
    echo -e "${GREEN}✓ Lambda code uploaded${NC}"
fi

# Upload CloudFormation templates
aws s3 sync "${SCRIPT_DIR}/cloudformation/nested-stacks" \
    "s3://${ARTIFACT_BUCKET}/cloudformation/nested-stacks/" \
    --exclude "*" --include "*.yaml"
echo -e "${GREEN}✓ CloudFormation templates uploaded${NC}"

# Deploy CloudFormation stack
echo ""
echo -e "${BLUE}[5/6] Deploying CloudFormation stack...${NC}"
echo "Stack name: ${STACK_NAME}"

aws cloudformation deploy \
    --template-file "${SCRIPT_DIR}/cloudformation/master-stack.yaml" \
    --stack-name "${STACK_NAME}" \
    --parameter-overrides \
        ProjectName="${PROJECT_NAME}" \
        Environment="${ENVIRONMENT}" \
        DeployDemo1="${DEPLOY_DEMO1}" \
        DeployDemo2="${DEPLOY_DEMO2}" \
        Demo2EnableWAF="${ENABLE_WAF}" \
        Demo2EnableGuardrails="${ENABLE_GUARDRAILS}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "${AWS_REGION}" \
    --no-fail-on-empty-changeset

DEPLOY_STATUS=$?

if [ $DEPLOY_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ CloudFormation stack deployed successfully${NC}"
else
    echo -e "${RED}✗ CloudFormation deployment failed${NC}"
    exit 1
fi

# Get stack outputs
echo ""
echo -e "${BLUE}[6/6] Retrieving deployment outputs...${NC}"

OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query 'Stacks[0].Outputs' \
    --output json)

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Extract and display relevant outputs
if [ "$DEPLOY_DEMO1" = "true" ]; then
    REGISTRY_URL=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="Demo1RegistryUrl") | .OutputValue')
    echo -e "${BLUE}Demo #1 (AgentCore Gateway):${NC}"
    echo -e "  Registry URL: ${REGISTRY_URL}"
    echo -e "  Next steps:"
    echo -e "    1. Deploy AgentCore Gateway: cd DemoMcpGateway/agentcore && agentcore deploy"
    echo -e "    2. Update registry with gateway URL"
    echo -e "    3. Configure VS Code with registry URL: ${REGISTRY_URL}"
    echo ""
fi

if [ "$DEPLOY_DEMO2" = "true" ]; then
    API_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="Demo2ApiEndpoint") | .OutputValue')
    TEAM_ALPHA_KEY=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="Demo2TeamAlphaApiKey") | .OutputValue')
    TEAM_BETA_KEY=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="Demo2TeamBetaApiKey") | .OutputValue')

    echo -e "${BLUE}Demo #2 (Browser Chat):${NC}"
    echo -e "  API Endpoint: ${API_ENDPOINT}"
    echo -e "  Team Alpha API Key: ${TEAM_ALPHA_KEY}"
    echo -e "  Team Beta API Key:  ${TEAM_BETA_KEY}"
    echo -e "  Next steps:"
    echo -e "    1. Update chatbox HTML: team-rbac-bedrock-chat-demo/chatbox.html"
    echo -e "    2. Replace API_ENDPOINT with: ${API_ENDPOINT}"
    echo -e "    3. Replace API keys with values above"
    echo -e "    4. Open chatbox.html in browser"
    echo ""
fi

echo -e "${BLUE}Stack Management:${NC}"
echo -e "  View stack:   aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${AWS_REGION}"
echo -e "  Delete stack: aws cloudformation delete-stack --stack-name ${STACK_NAME} --region ${AWS_REGION}"
echo ""

echo -e "${GREEN}Deployment completed successfully!${NC}"
