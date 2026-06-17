#!/usr/bin/env python3
"""
Create an AgentCore Gateway with CUSTOM_JWT auth (Cognito).
Adds Lambda MCP targets (products, orders, customers, jira).
Outputs the gateway URL.

This is the OAuth/JWT path — developers log in with their identity via the
browser (no local proxy, no IAM keys on the laptop).
"""
import argparse
import boto3
import json
import time
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--region', required=True)
    parser.add_argument('--cognito-pool-id', required=True)
    parser.add_argument('--cognito-client-id', required=True)
    parser.add_argument('--account-id', required=True)
    parser.add_argument('--prefix', default='mcp-demo')
    args = parser.parse_args()

    client = boto3.client('bedrock-agentcore-control', region_name=args.region)
    iam = boto3.client('iam')

    gateway_name = f"{args.prefix}-gateway-jwt"
    cognito_issuer = f"https://cognito-idp.{args.region}.amazonaws.com/{args.cognito_pool_id}"

    # ── Check if gateway already exists ──
    existing = client.list_gateways()
    for gw in existing.get('gateways', []):
        if gw.get('name') == gateway_name:
            url = gw.get('url', '')
            print(url, end='')
            return

    # ── Create gateway execution role ──
    role_name = f"{args.prefix}-gateway-role"
    trust = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    })
    try:
        role_resp = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=trust,
            Description="AgentCore Gateway role for MCP demo"
        )
        role_arn = role_resp['Role']['Arn']
        # Attach Lambda invoke + policy engine permissions
        policy_doc = json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["lambda:InvokeFunction"],
                    "Resource": f"arn:aws:lambda:{args.region}:{args.account_id}:function:{args.prefix}-*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:EvaluatePolicy",
                        "bedrock-agentcore:AuthorizeAction",
                        "bedrock-agentcore:GetPolicyEngine"
                    ],
                    "Resource": "*"
                }
            ]
        })
        iam.put_role_policy(RoleName=role_name, PolicyName='GatewayAccess', PolicyDocument=policy_doc)
        time.sleep(10)  # Wait for IAM propagation
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = f"arn:aws:iam::{args.account_id}:role/{role_name}"

    # ── Create gateway ──
    resp = client.create_gateway(
        name=gateway_name,
        description="MCP Gateway with OAuth/JWT auth and Cedar RBAC — no local proxy needed",
        roleArn=role_arn,
        protocolConfiguration={'mcp': {}},
        authorizationConfiguration={
            'customJWTAuthorization': {
                'issuerUrl': cognito_issuer,
                'allowedAudiences': [args.cognito_client_id],
                'allowedClients': [args.cognito_client_id]
            }
        }
    )
    gateway_id = resp['gatewayId']

    # Wait for gateway to be READY
    for _ in range(30):
        gw = client.get_gateway(gatewayId=gateway_id)
        if gw.get('status') == 'READY':
            break
        time.sleep(5)

    gateway_url = gw.get('url', f"https://{gateway_id}.gateway.bedrock-agentcore.{args.region}.amazonaws.com")

    # ── Add Lambda targets ──
    targets = [
        (f"{args.prefix}-products-mcp", "products-mcp", "Product catalog tools"),
        (f"{args.prefix}-orders-mcp", "orders-mcp", "Order management tools"),
        (f"{args.prefix}-ecommerce-mcp", "customers-mcp", "Customer data tools"),
        (f"{args.prefix}-jira-mcp", "jira-mcp", "Jira ticket tools"),
    ]
    for lambda_name, target_name, desc in targets:
        lambda_arn = f"arn:aws:lambda:{args.region}:{args.account_id}:function:{lambda_name}"
        try:
            client.create_gateway_target(
                gatewayId=gateway_id,
                name=target_name,
                description=desc,
                targetConfiguration={
                    'lambdaTarget': {
                        'lambdaArn': lambda_arn
                    }
                }
            )
        except Exception as e:
            if 'already exists' not in str(e).lower():
                print(f"Warning: Could not add target {target_name}: {e}", file=sys.stderr)

    print(gateway_url, end='')


if __name__ == '__main__':
    main()
