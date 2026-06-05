#!/usr/bin/env python3
"""
Create Cedar RBAC policies for IAM-based gateway auth.
ReadOnly  → list/search/get tools only
FullAccess → all tools (including create_order)
Uses IAM user tag: group = ReadOnly | FullAccess
"""
import argparse
import boto3
import time
import sys

# ReadOnly: can list/search/get but not create/update/delete
READONLY_ACTIONS = [
    "ecommerce-mcp___list_customers",
    "ecommerce-mcp___get_customer_by_id",
    "products-mcp___list_products",
    "products-mcp___search_products",
    "products-mcp___get_product_by_id",
    "orders-mcp___list_orders",
    "orders-mcp___get_order_by_id",
    "jira-mcp___list_jira_tickets",
]

# FullAccess: everything including writes
FULLACCESS_ACTIONS = READONLY_ACTIONS + [
    "orders-mcp___create_order",
]


def cedar_permit(action, group, gateway_arn):
    return (
        f'permit(\n'
        f'    principal,\n'
        f'    action == AgentCore::Action::"{action}",\n'
        f'    resource == AgentCore::Gateway::"{gateway_arn}"\n'
        f')\n'
        f'when {{\n'
        f'    principal.hasTag("group") && principal.getTag("group") == "{group}"\n'
        f'}};'
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--region', required=True)
    parser.add_argument('--account-id', required=True)
    parser.add_argument('--prefix', default='mcp-demo')
    args = parser.parse_args()

    client = boto3.client('bedrock-agentcore-control', region_name=args.region)

    # Find gateway
    gateways = client.list_gateways().get('gateways', [])
    gw = next((g for g in gateways if args.prefix in g.get('name', '')), None)
    if not gw:
        print("  ❌ Gateway not found. Run create-gateway.py first.", file=sys.stderr)
        sys.exit(1)

    gateway_id = gw['gatewayId']
    gateway_arn = gw.get('arn', f"arn:aws:bedrock-agentcore:{args.region}:{args.account_id}:gateway/{gateway_id}")

    # Create or find policy engine
    engine_name = f"{args.prefix}-policies"
    engines = client.list_policy_engines().get('policyEngines', [])
    engine = next((e for e in engines if e.get('name') == engine_name), None)

    if not engine:
        resp = client.create_policy_engine(name=engine_name)
        engine_id = resp['policyEngineId']
        engine_arn = resp.get('arn', f"arn:aws:bedrock-agentcore:{args.region}:{args.account_id}:policy-engine/{engine_id}")
        print(f"  ✅ Created policy engine: {engine_name}")
        time.sleep(3)
    else:
        engine_id = engine['policyEngineId']
        engine_arn = engine.get('arn', f"arn:aws:bedrock-agentcore:{args.region}:{args.account_id}:policy-engine/{engine_id}")
        print(f"  ⏭️  Using existing engine: {engine_name}")

    # Create ReadOnly policies (per-action)
    for action in READONLY_ACTIONS:
        name = f"readonly_{action.replace('-','_').replace('___','_')}"
        cedar = cedar_permit(action, "ReadOnly", gateway_arn)
        try:
            client.create_policy(policyEngineId=engine_id, name=name,
                                 definition={'cedar': {'statement': cedar}})
            print(f"  ✅ {name}")
        except Exception as e:
            if 'already exists' in str(e).lower() or 'conflict' in str(e).lower():
                print(f"  ⏭️  {name}")
            else:
                print(f"  ⚠️  {name}: {e}", file=sys.stderr)

    # Create FullAccess policies
    for action in FULLACCESS_ACTIONS:
        name = f"fullaccess_{action.replace('-','_').replace('___','_')}"
        cedar = cedar_permit(action, "FullAccess", gateway_arn)
        try:
            client.create_policy(policyEngineId=engine_id, name=name,
                                 definition={'cedar': {'statement': cedar}})
            print(f"  ✅ {name}")
        except Exception as e:
            if 'already exists' in str(e).lower() or 'conflict' in str(e).lower():
                print(f"  ⏭️  {name}")
            else:
                print(f"  ⚠️  {name}: {e}", file=sys.stderr)

    # Bind engine to gateway (ENFORCE mode)
    try:
        client.update_gateway(
            gatewayId=gateway_id,
            policyEngineConfiguration={'policyEngineArn': engine_arn, 'mode': 'ENFORCE'}
        )
        print(f"  ✅ Policy engine bound (ENFORCE)")
    except Exception as e:
        if 'already' in str(e).lower():
            print(f"  ⏭️  Already bound")
        else:
            print(f"  ⚠️  {e}", file=sys.stderr)

    print("  ✅ Cedar RBAC complete (ReadOnly + FullAccess)")


if __name__ == '__main__':
    main()
