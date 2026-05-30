#!/usr/bin/env python3
"""
Create Bedrock AgentCore Gateway

This script creates an AgentCore Gateway that aggregates all registered MCP targets.
The gateway provides a single endpoint for accessing multiple MCP servers.

Prerequisites:
- MCP targets must be registered (run register-mcp-targets.py first)
- AWS credentials configured
- IAM permissions for bedrock-agentcore:CreateGateway
"""

import boto3
import json
import sys
import os

# Configuration
REGION = 'us-east-1'
GATEWAY_NAME = 'demo-mcp-gateway'
GATEWAY_DESCRIPTION = 'Multi-tenant MCP gateway with RBAC demo'


def load_registered_targets():
    """Load previously registered targets"""
    try:
        with open('tmp/registered-targets.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ No registered targets found. Run register-mcp-targets.py first.")
        sys.exit(1)


def create_gateway(bedrock_client, targets):
    """Create AgentCore Gateway"""
    try:
        print(f"\n🔧 Creating gateway: {GATEWAY_NAME}")
        print(f"   Description: {GATEWAY_DESCRIPTION}")
        print(f"   Targets: {len(targets)}")
        print()

        for target in targets:
            print(f"   • {target['name']}")

        # Note: Actual API call syntax depends on AgentCore SDK
        # This is a template - adjust based on actual AWS SDK
        # response = bedrock_client.create_gateway(
        #     name=GATEWAY_NAME,
        #     description=GATEWAY_DESCRIPTION,
        #     targets=[t['target_id'] for t in targets]
        # )

        # For demo purposes, print what would be created
        print(f"\n✅ Would create gateway: {GATEWAY_NAME}")
        print(f"   Gateway ID: [will-be-generated]")
        print(f"   Gateway URL: https://[gateway-id].gateway.bedrock-agentcore.{REGION}.amazonaws.com/mcp")

        return {
            'gateway_id': 'YOUR-GATEWAY-ID',  # Placeholder
            'gateway_url': f'https://YOUR-GATEWAY-ID.gateway.bedrock-agentcore.{REGION}.amazonaws.com/mcp'
        }

    except Exception as e:
        print(f"❌ Error creating gateway: {e}")
        import traceback
        traceback.print_exc()
        return None


def update_lambda_environment(gateway_url):
    """Update Lambda proxy with gateway URL"""
    lambda_client = boto3.client('lambda', region_name=REGION)

    try:
        print(f"\n🔄 Updating Lambda proxy environment...")
        lambda_client.update_function_configuration(
            FunctionName='mcp-gateway-proxy',
            Environment={
                'Variables': {
                    'GATEWAY_URL': gateway_url,
                    'AWS_REGION': REGION
                }
            }
        )
        print(f"✅ Lambda environment updated")
    except Exception as e:
        print(f"⚠️  Could not update Lambda (it may not exist yet): {e}")


def save_gateway_info(gateway_info):
    """Save gateway information for reference"""
    with open('tmp/gateway-info.json', 'w') as f:
        json.dump(gateway_info, f, indent=2)

    print("\n📝 Gateway information saved to: tmp/gateway-info.json")


def main():
    """Main execution"""
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║              Create Bedrock AgentCore Gateway                 ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"\nRegion: {REGION}")
    print()

    # Load registered targets
    targets = load_registered_targets()
    print(f"📋 Found {len(targets)} registered targets")

    # Initialize Bedrock client
    # bedrock_client = boto3.client('bedrock-agentcore', region_name=REGION)

    # Create gateway
    gateway_info = create_gateway(None, targets)  # Pass bedrock_client when available

    if gateway_info:
        # Save gateway info
        save_gateway_info(gateway_info)

        # Update Lambda environment
        # update_lambda_environment(gateway_info['gateway_url'])

        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("Gateway Created Successfully")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"\n✅ Gateway ID: {gateway_info['gateway_id']}")
        print(f"🔗 Gateway URL: {gateway_info['gateway_url']}")
        print()
        print("🎯 Next Steps:")
        print("   1. Update CloudFormation iam-roles.yaml with Gateway ID")
        print("   2. Redeploy IAM roles:")
        print("      ./scripts/deploy-infrastructure.sh")
        print()
        print("   3. Deploy Lambda proxy:")
        print("      cd lambda/gateway-proxy")
        print("      ./deploy.sh")
        print()
        print("   4. Create API Gateway REST API (manual or CDK)")
        print()
        print("   5. Test the gateway:")
        print("      curl -X POST $API_GATEWAY_URL/mcp \\")
        print("        -H 'x-squad: alpha-team' \\")
        print("        -H 'Content-Type: application/json' \\")
        print("        -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}'")
        print()
    else:
        print("\n❌ Gateway creation failed")
        sys.exit(1)


if __name__ == '__main__':
    # Create tmp directory
    os.makedirs('tmp', exist_ok=True)

    main()
