# Bedrock AgentCore MCP Gateway Demo
# ====================================
# Makefile for deploying and managing both demos.
#
# Usage:
#   make check          - Verify prerequisites
#   make test           - Run unit tests
#   make deploy-demo1   - Deploy Demo 1 (AgentCore Gateway + VS Code)
#   make deploy-demo2   - Deploy Demo 2 (Team RBAC + Browser Chat)
#   make clean          - Remove build artifacts
#   make help           - Show this help

.PHONY: help check test deploy-demo1 deploy-demo2 clean package-demo2

SHELL := /bin/bash
REGION ?= us-east-1
STACK_NAME ?= mcp-gateway-demo

# Colors
GREEN  := \033[0;32m
YELLOW := \033[1;33m
NC     := \033[0m

help: ## Show this help
	@echo "Bedrock AgentCore MCP Gateway Demo"
	@echo "==================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Environment variables:"
	@echo "  REGION       AWS region (default: us-east-1)"
	@echo "  STACK_NAME   CloudFormation stack name (default: mcp-gateway-demo)"
	@echo "  S3_BUCKET    S3 bucket for Lambda artifacts (required for deploy-demo2)"

# ─────────────────────────────────────────────
# Prerequisites & Testing
# ─────────────────────────────────────────────

check: ## Verify all prerequisites are met
	@./scripts/check-prerequisites.sh --all

check-demo1: ## Verify Demo 1 prerequisites
	@./scripts/check-prerequisites.sh --demo1

check-demo2: ## Verify Demo 2 prerequisites
	@./scripts/check-prerequisites.sh --demo2

test: ## Run all unit tests
	@echo "Running unit tests..."
	@python3 -m pytest tests/ -v --tb=short
	@echo ""
	@echo -e "$(GREEN)All tests passed!$(NC)"

lint: ## Lint Python code
	@echo "Linting..."
	@python3 -m flake8 \
		gateway-url-ide-integration-demo/lambda/ \
		team-rbac-bedrock-chat-demo/lambda/ \
		--max-line-length=120 --ignore=E501,W503
	@echo -e "$(GREEN)Lint passed!$(NC)"

# ─────────────────────────────────────────────
# Demo 1: AgentCore Gateway + VS Code
# ─────────────────────────────────────────────

deploy-demo1: check-demo1 ## Deploy Demo 1 (AgentCore Gateway)
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║     Deploying Demo 1: AgentCore Gateway + VS Code            ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@# Step 1: Get account info
	$(eval ACCOUNT_ID := $(shell aws sts get-caller-identity --query Account --output text))
	@echo "Account: $(ACCOUNT_ID)"
	@echo "Region:  $(REGION)"
	@echo ""
	@# Step 2: Deploy Lambda MCP servers
	@echo "Step 1/3: Deploying Lambda MCP servers..."
	@cd gateway-url-ide-integration-demo/lambda/mcp-servers && \
		AWS_REGION=$(REGION) ./deploy-all.sh
	@echo ""
	@# Step 3: Configure agentcore.json with actual values
	@echo "Step 2/3: Configuring AgentCore project..."
	@cd gateway-url-ide-integration-demo/DemoMcpGateway/agentcore && \
		sed "s/<REGION>/$(REGION)/g; s/<ACCOUNT_ID>/$(ACCOUNT_ID)/g" agentcore.json > agentcore.json.tmp && \
		mv agentcore.json.tmp agentcore.json && \
		echo '[ {"name": "default", "account": "$(ACCOUNT_ID)", "region": "$(REGION)"} ]' > aws-targets.json
	@echo ""
	@# Step 4: Deploy gateway
	@echo "Step 3/3: Deploying AgentCore Gateway..."
	@cd gateway-url-ide-integration-demo/DemoMcpGateway/agentcore && \
		cd cdk && npm install --silent && cd .. && \
		agentcore deploy
	@echo ""
	@echo -e "$(GREEN)Demo 1 deployed! Follow VSCODE_SETUP.md to configure your IDE.$(NC)"

# ─────────────────────────────────────────────
# Demo 2: Team RBAC + Browser Chat
# ─────────────────────────────────────────────

package-demo2: ## Package Demo 2 Lambda functions
	@echo "Packaging Demo 2 Lambda functions..."
	@mkdir -p build
	@cd team-rbac-bedrock-chat-demo/lambda/gateway-proxy && \
		zip -qr ../../../build/gateway-proxy.zip lambda_function.py feature_flags.py
	@echo -e "$(GREEN)Package created: build/gateway-proxy.zip$(NC)"

deploy-demo2: check-demo2 package-demo2 ## Deploy Demo 2 (Team RBAC Chat)
ifndef S3_BUCKET
	$(error S3_BUCKET is required. Set it: make deploy-demo2 S3_BUCKET=my-bucket-name)
endif
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║     Deploying Demo 2: Team RBAC + Browser Chat               ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "S3 Bucket: $(S3_BUCKET)"
	@echo "Region:    $(REGION)"
	@echo ""
	@# Upload Lambda code to S3
	@echo "Step 1/3: Uploading Lambda code to S3..."
	@aws s3 cp build/gateway-proxy.zip s3://$(S3_BUCKET)/lambda/gateway-proxy.zip --region $(REGION)
	@echo ""
	@# Deploy CloudFormation
	@echo "Step 2/3: Deploying CloudFormation stack..."
	@aws cloudformation deploy \
		--template-file team-rbac-bedrock-chat-demo/infrastructure/cloudformation/main-stack.yaml \
		--stack-name $(STACK_NAME) \
		--parameter-overrides \
			S3ArtifactBucket=$(S3_BUCKET) \
			ProxyCodeKey=lambda/gateway-proxy.zip \
			EnableGuardrail=false \
		--capabilities CAPABILITY_NAMED_IAM \
		--region $(REGION) \
		--no-fail-on-empty-changeset
	@echo ""
	@# Get outputs
	@echo "Step 3/3: Retrieving API endpoint..."
	$(eval API_ENDPOINT := $(shell aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
		--output text))
	@echo ""
	@echo -e "$(GREEN)Demo 2 deployed!$(NC)"
	@echo ""
	@echo "API Endpoint: $(API_ENDPOINT)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Update team-rbac-bedrock-chat-demo/chatbox.html with the API endpoint above"
	@echo "  2. Open chatbox.html in your browser"
	@echo "  3. Select a team and start chatting"

# ─────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────

clean: ## Remove build artifacts
	@echo "Cleaning build artifacts..."
	@rm -rf build/ tmp/
	@rm -f gateway-url-ide-integration-demo/lambda/mcp-servers/*/function.zip
	@rm -f team-rbac-bedrock-chat-demo/lambda/*/function.zip
	@echo -e "$(GREEN)Clean!$(NC)"

destroy-demo2: ## Delete Demo 2 CloudFormation stack
	@echo -e "$(YELLOW)Deleting CloudFormation stack: $(STACK_NAME)$(NC)"
	@aws cloudformation delete-stack --stack-name $(STACK_NAME) --region $(REGION)
	@echo "Waiting for deletion..."
	@aws cloudformation wait stack-delete-complete --stack-name $(STACK_NAME) --region $(REGION)
	@echo -e "$(GREEN)Stack deleted.$(NC)"
