#!/usr/bin/env python3
"""
Create a Cedar policy engine, add per-team RBAC policies, and bind to the gateway.
Team Engineering → products + orders tools
Team Support     → customers + jira tools
"""
import argparse
import boto3
import json
import time
import sys

POLICIES = {
    "engineering_products_list": {
        "team": "Engineering",
        "action": "products-mcp___list_products"
    },
    "engineering_products_search": {
        "team": "Engineering",
        "action": "products-mcp___search_products"
    },
    "engineering_products_get": {
        "team": "Engineering",
        "action": "products-mcp___get_product_by_id"
    },
    "engineering_orders_list": {
        "team": "Engineering",
        "action": "orders-mcp___list_orders"
    },
    "engineering_orders_get": {
        "team": "Engineering",
        "action": "orders-mcp___get_order_by_id"
    },
    "engineering_orders_create": {
        "team": "Engineering",
        "action": "orders-mcp___create_order"
    },
    "support_customers_list": {
        "team": "Support",
        "action": "customers-mcp___list_customers"
    },
    "support_customers_get": {
        "team": "Support",
        "action": "customers-mcp___get_customer_by_id"
    },
    "support_jira_list": {
        "team": "Support",
        "action": "jira-mcp___list_jira_tickets"
    },
}


def cedar_permit(action, team, gateway_arn):
    return (
        f'permit(\n'
        f'    principal,\n'
        f'    action == AgentCore::Action::"{action}",\n'
        f'    resource == AgentCore::Gateway::"{gateway_arn}"\n'
        f')\n'
        f'when {{\n'
        f'    principal.hasTag("team") && principal.getTag("team") == "{team}"\n'
        f'}};'
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--region', required=True)
    parser.add_argument('--account-id', required=True)
    parser.add_argument('--prefix', default='mcp-demo')
    args = parser.parse_args()

    client = boto3.client('bedrock-agentcore-control', region_name=args.region)

    # ── Find the gateway ──
    resp = client.list_gateways()
    gateways = resp.get('items', resp.get('gateways', []))
    gw = next((g for g in gateways if g.get('name') == f"{args.prefix}-gateway-jwt"), None)
    if not gw:
        print("❌ Gateway not found. Run create-gateway.py first.", file=sys.stderr)
        sys.exit(1)

    gateway_id = gw['gatewayId']
    # Fetch full details to get the ARN (list response doesn't include it)
    gw_detail = client.get_gateway(gatewayIdentifier=gateway_id)
    gateway_arn = gw_detail.get('gatewayArn', f"arn:aws:bedrock-agentcore:{args.region}:{args.account_id}:gateway/{gateway_id}")

    # ── Create or find policy engine ──
    engine_name = f"{args.prefix.replace('-','_')}_policies"
    pe_resp = client.list_policy_engines()
    engines = pe_resp.get('policyEngines', pe_resp.get('items', []))
    engine = next((e for e in engines if e.get('name') == engine_name), None)

    if not engine:
        resp = client.create_policy_engine(name=engine_name)
        engine_id = resp.get('policyEngineId', resp.get('id',''))
        engine_arn = resp.get('arn', resp.get('policyEngineArn', f"arn:aws:bedrock-agentcore:{args.region}:{args.account_id}:policy-engine/{engine_id}"))
        print(f"  Created policy engine: {engine_name}")
        time.sleep(3)
    else:
        engine_id = engine.get('policyEngineId', engine.get('id',''))
        engine_arn = engine.get('arn', engine.get('policyEngineArn', f"arn:aws:bedrock-agentcore:{args.region}:{args.account_id}:policy-engine/{engine_id}"))
        print(f"  Using existing policy engine: {engine_name}")

    # ── Create policies ──
    for name, spec in POLICIES.items():
        cedar = cedar_permit(spec['action'], spec['team'], gateway_arn)
        try:
            client.create_policy(
                policyEngineId=engine_id,
                name=name,
                definition={'cedar': {'statement': cedar}},
                enforcementMode='ENFORCED'
            )
            print(f"  ✅ Policy: {name}")
        except Exception as e:
            if 'already exists' in str(e).lower() or 'conflict' in str(e).lower():
                print(f"  ⏭️  Policy exists: {name}")
            else:
                print(f"  ⚠️  Policy {name}: {e}", file=sys.stderr)

    # ── Bind engine to gateway (ENFORCE mode) ──
    try:
        gw_cfg = client.get_gateway(gatewayIdentifier=gateway_id)
        client.update_gateway(
            gatewayIdentifier=gateway_id,
            name=gw_cfg['name'],
            roleArn=gw_cfg['roleArn'],
            authorizerType=gw_cfg['authorizerType'],
            policyEngineConfiguration={
                'arn': engine_arn,
                'mode': 'ENFORCE'
            }
        )
        print(f"  ✅ Policy engine bound to gateway (ENFORCE mode)")
    except Exception as e:
        if 'already' in str(e).lower():
            print(f"  ⏭️  Engine already bound")
        else:
            print(f"  ⚠️  Binding: {e}", file=sys.stderr)

    print("✅ Cedar RBAC setup complete")


if __name__ == '__main__':
    main()
