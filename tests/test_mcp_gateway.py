"""
Unit tests for MCP Gateway Demo

Tests cover:
- MCP server tool handlers (via API Gateway format)
- Feature flag logic
- Gateway proxy model permission logic
"""

import json
import sys
import os
import pytest

# Add lambda paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'gateway-url-ide-integration-demo', 'lambda', 'mcp-servers', 'ecommerce-mcp'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'team-rbac-bedrock-chat-demo', 'lambda', 'gateway-proxy'))


# ─────────────────────────────────────────────
# Ecommerce MCP Tests (API Gateway format)
# ─────────────────────────────────────────────
class TestEcommerceMcpApiGateway:
    """Test Ecommerce MCP Server via API Gateway invocation format."""

    def setup_method(self):
        import importlib
        if 'lambda_function' in sys.modules:
            del sys.modules['lambda_function']
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'gateway-url-ide-integration-demo', 'lambda', 'mcp-servers', 'ecommerce-mcp'))
        import lambda_function as ecommerce
        self.handler = ecommerce.lambda_handler

    def test_tools_list(self):
        event = {'body': json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})}
        response = self.handler(event, None)
        body = json.loads(response['body'])
        tools = body['result']['tools']
        tool_names = [t['name'] for t in tools]
        assert 'demo-ecommerce-mcp___list_customers' in tool_names
        assert 'demo-ecommerce-mcp___get_customer_by_id' in tool_names

    def test_list_customers(self):
        event = {'body': json.dumps({
            'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
            'params': {'name': 'demo-ecommerce-mcp___list_customers', 'arguments': {}}
        })}
        response = self.handler(event, None)
        body = json.loads(response['body'])
        content = json.loads(body['result']['content'][0]['text'])
        assert len(content['customers']) > 0
        assert content['customers'][0]['id'] == 'CUST-001'

    def test_get_customer_by_id(self):
        event = {'body': json.dumps({
            'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
            'params': {'name': 'demo-ecommerce-mcp___get_customer_by_id', 'arguments': {'customer_id': 'CUST-001'}}
        })}
        response = self.handler(event, None)
        body = json.loads(response['body'])
        content = json.loads(body['result']['content'][0]['text'])
        assert content['name'] == 'Acme Corporation'

    def test_unknown_tool(self):
        event = {'body': json.dumps({
            'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call',
            'params': {'name': 'demo-ecommerce-mcp___nonexistent', 'arguments': {}}
        })}
        response = self.handler(event, None)
        body = json.loads(response['body'])
        assert 'error' in body


# ─────────────────────────────────────────────
# Feature Flags Tests
# ─────────────────────────────────────────────
class TestFeatureFlags:
    """Test feature flag logic with mocked AppConfig responses."""

    def setup_method(self):
        # Ensure we can import feature_flags
        path = os.path.join(os.path.dirname(__file__), '..', 'team-rbac-bedrock-chat-demo', 'lambda', 'gateway-proxy')
        if path not in sys.path:
            sys.path.insert(0, path)

    def test_is_enabled_returns_true_when_flag_enabled(self):
        """Test that enabled flags return True."""
        import feature_flags
        feature_flags._cached_flags = {
            'values': {
                'guardrail_enabled': {'enabled': True, 'teams': 'alpha-team,beta-team'},
                'team_alpha_access': {'enabled': True},
                'team_beta_access': {'enabled': True}
            }
        }
        feature_flags._cache_expiry = float('inf')

        assert feature_flags.is_enabled('team_alpha_access') is True
        assert feature_flags.is_enabled('team_beta_access') is True

    def test_is_enabled_returns_false_when_flag_disabled(self):
        """Test that disabled flags return False."""
        import feature_flags
        feature_flags._cached_flags = {
            'values': {
                'team_alpha_access': {'enabled': False},
                'team_beta_access': {'enabled': True}
            }
        }
        feature_flags._cache_expiry = float('inf')

        assert feature_flags.is_enabled('team_alpha_access') is False
        assert feature_flags.is_enabled('team_beta_access') is True

    def test_is_team_enabled(self):
        """Test team-specific access check."""
        import feature_flags
        feature_flags._cached_flags = {
            'values': {
                'alpha_team_access': {'enabled': True},
                'beta_team_access': {'enabled': False}
            }
        }
        feature_flags._cache_expiry = float('inf')

        assert feature_flags.is_team_enabled('alpha-team') is True
        assert feature_flags.is_team_enabled('beta-team') is False

    def test_is_guardrail_enabled_for_team(self):
        """Test guardrail flag with team filtering."""
        import feature_flags
        feature_flags._cached_flags = {
            'values': {
                'guardrail_enabled': {'enabled': True, 'teams': 'alpha-team'}
            }
        }
        feature_flags._cache_expiry = float('inf')

        assert feature_flags.is_guardrail_enabled('alpha-team') is True
        assert feature_flags.is_guardrail_enabled('beta-team') is False

    def test_defaults_to_enabled_when_no_cache(self):
        """Test graceful degradation when AppConfig unavailable."""
        import feature_flags
        feature_flags._cached_flags = None
        feature_flags._cache_expiry = 0

        assert feature_flags.is_enabled('anything') is True
        assert feature_flags.is_guardrail_enabled() is True


# ─────────────────────────────────────────────
# Gateway Proxy Model Permission Tests
# ─────────────────────────────────────────────
class TestGatewayProxyPermissions:
    """Test model permission logic in the Demo 2 gateway proxy."""

    def setup_method(self):
        os.environ['TEAM_ALPHA_MODELS'] = 'haiku,sonnet'
        os.environ['TEAM_BETA_MODELS'] = 'haiku'

        # Force the gateway-proxy path to be first so we import the right module
        proxy_path = os.path.join(os.path.dirname(__file__), '..', 'team-rbac-bedrock-chat-demo', 'lambda', 'gateway-proxy')
        proxy_path = os.path.abspath(proxy_path)

        # Remove any other lambda_function paths that might conflict
        if 'lambda_function' in sys.modules:
            del sys.modules['lambda_function']

        # Temporarily prepend the proxy path
        sys.path.insert(0, proxy_path)

    def teardown_method(self):
        # Clean up to avoid polluting other tests
        proxy_path = os.path.join(os.path.dirname(__file__), '..', 'team-rbac-bedrock-chat-demo', 'lambda', 'gateway-proxy')
        proxy_path = os.path.abspath(proxy_path)
        if proxy_path in sys.path:
            sys.path.remove(proxy_path)
        if 'lambda_function' in sys.modules:
            del sys.modules['lambda_function']

    def test_team_alpha_allowed_models(self):
        """Team Alpha should have access to haiku and sonnet."""
        import lambda_function as gw
        allowed = gw.get_team_allowed_models('team-alpha')
        assert gw.MODEL_IDS['haiku'] in allowed
        assert gw.MODEL_IDS['sonnet'] in allowed
        assert gw.MODEL_IDS['opus'] not in allowed

    def test_team_beta_allowed_models(self):
        """Team Beta should only have access to haiku."""
        import lambda_function as gw
        allowed = gw.get_team_allowed_models('team-beta')
        assert gw.MODEL_IDS['haiku'] in allowed
        assert gw.MODEL_IDS['sonnet'] not in allowed

    def test_model_allowed_check(self):
        """is_model_allowed_for_team should correctly validate."""
        import lambda_function as gw
        assert gw.is_model_allowed_for_team('team-alpha', gw.MODEL_IDS['haiku']) is True
        assert gw.is_model_allowed_for_team('team-alpha', gw.MODEL_IDS['sonnet']) is True
        assert gw.is_model_allowed_for_team('team-alpha', gw.MODEL_IDS['opus']) is False
        assert gw.is_model_allowed_for_team('team-beta', gw.MODEL_IDS['haiku']) is True
        assert gw.is_model_allowed_for_team('team-beta', gw.MODEL_IDS['sonnet']) is False
