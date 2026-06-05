#!/usr/bin/env python3
"""Delete the AgentCore Gateway and policy engine created by deploy.sh."""
import argparse
import boto3
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--region', required=True)
    parser.add_argument('--prefix', default='mcp-demo')
    args = parser.parse_args()

    client = boto3.client('bedrock-agentcore-control', region_name=args.region)

    # Delete gateway
    gateway_name = f"{args.prefix}-gateway-jwt"
    gateways = client.list_gateways().get('gateways', [])
    gw = next((g for g in gateways if g.get('name') == gateway_name), None)
    if gw:
        gw_id = gw['gatewayId']
        # Delete targets first
        targets = client.list_gateway_targets(gatewayId=gw_id).get('targets', [])
        for t in targets:
            try:
                client.delete_gateway_target(gatewayId=gw_id, targetId=t['targetId'])
                print(f"  Deleted target: {t.get('name', t['targetId'])}")
            except Exception:
                pass
        client.delete_gateway(gatewayId=gw_id)
        print(f"  ✅ Deleted gateway: {gateway_name}")
    else:
        print(f"  ⏭️  Gateway not found: {gateway_name}")

    # Delete policy engine
    engine_name = f"{args.prefix}-policies"
    engines = client.list_policy_engines().get('policyEngines', [])
    engine = next((e for e in engines if e.get('name') == engine_name), None)
    if engine:
        client.delete_policy_engine(policyEngineId=engine['policyEngineId'])
        print(f"  ✅ Deleted policy engine: {engine_name}")
    else:
        print(f"  ⏭️  Policy engine not found: {engine_name}")

if __name__ == '__main__':
    main()
