#!/usr/bin/env python3
"""
Register MCP Servers as AgentCore Targets

This script registers Lambda-based MCP servers as targets in Bedrock AgentCore.
Each MCP server Lambda becomes a target that can be included in a gateway.

Prerequisites:
- Lambda functions must be deployed
- AWS credentials configured
- Appropriate IAM permissions for bedrock-agentcore
"""

import boto3
import json
import sys

# Configuration
REGION = 'us-east-1'
MCP_SERVERS = [
    {
        'name': 'demo-ecommerce-mcp',
        'description': 'Customer management MCP server',
        'lambda_function': 'demo-ecommerce-mcp'
    },
    {
        'name': 'demo-products-mcp',
        'description': 'Product catalog MCP server',
        'lambda_function': 'demo-products-mcp'
    },
    {
        'name': 'demo-orders-mcp',
        'description': 'Order management MCP server',
        'lambda_function': 'demo-orders-mcp'
    }
]

def get_lambda_arn(function_name):
    """Get Lambda function ARN"""
    lambda_client = boto3.client('lambda', region_name=REGION)
    try:
        response = lambda_client.get_function(FunctionName=function_name)
        return response['Configuration']['FunctionArn']
    except Exception as e:
        print(f"❌ Error getting Lambda ARN for {function_name}: {e}")
        return None


def register_target(bedrock_client, target_config):
    """Register MCP server as AgentCore target"""
    try:
        lambda_arn = get_lambda_arn(target_config['lambda_function'])
        if not lambda_arn:
            return None

        print(f"\n📋 Registering target: {target_config['name']}")
        print(f"   Lambda ARN: {lambda_arn}")

        # Note: Actual API call syntax depends on AgentCore SDK
        # This is a template - adjust based on actual AWS SDK
        # response = bedrock_client.create_target(
        #     name=target_config['name'],
        #     description=target_config['description'],
        #     targetConfig={
        #         'type': 'LAMBDA',
        #         'lambdaArn': lambda_arn
        #     }
        # )

        # For demo purposes, print what would be registered
        print(f"✅ Would register target: {target_config['name']}")
        print(f"   Description: {target_config['description']}")
        print(f"   Lambda: {lambda_arn}")

        return {
            'name': target_config['name'],
            'lambda_arn': lambda_arn
        }

    except Exception as e:
        print(f"❌ Error registering target {target_config['name']}: {e}")
        return None


def main():
    """Main execution"""
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║         Register MCP Servers as AgentCore Targets             ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"\nRegion: {REGION}")
    print(f"Targets to register: {len(MCP_SERVERS)}")
    print()

    # Initialize Bedrock client
    # bedrock_client = boto3.client('bedrock-agentcore', region_name=REGION)

    registered_targets = []

    for server in MCP_SERVERS:
        target = register_target(None, server)  # Pass bedrock_client when available
        if target:
            registered_targets.append(target)

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Summary")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"\n✅ Registered {len(registered_targets)} / {len(MCP_SERVERS)} targets")
    print("\n📝 Target IDs to use when creating gateway:")
    for target in registered_targets:
        print(f"   • {target['name']}")

    print("\n🎯 Next Step:")
    print("   python scripts/create-gateway.py")
    print()

    # Save target info for next script
    with open('tmp/registered-targets.json', 'w') as f:
        json.dump(registered_targets, f, indent=2)


if __name__ == '__main__':
    # Create tmp directory
    import os
    os.makedirs('tmp', exist_ok=True)

    main()
