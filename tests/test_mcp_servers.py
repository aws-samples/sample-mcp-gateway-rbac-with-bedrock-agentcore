"""
Unit tests for MCP Server Lambda functions (Demo 1)

Tests the MCP JSON-RPC protocol implementation and tool functionality
for all three MCP servers (ecommerce, products, orders).

Run with: python -m pytest tests/test_mcp_servers.py -v
"""

import json
import sys
import os
import importlib

# Add lambda directories to path (Demo 1 MCP servers)
_BASE = os.path.join(os.path.dirname(__file__), '..', 'gateway-url-ide-integration-demo', 'lambda', 'mcp-servers')
sys.path.insert(0, os.path.join(_BASE, 'ecommerce-mcp'))
sys.path.insert(0, os.path.join(_BASE, 'products-mcp'))
sys.path.insert(0, os.path.join(_BASE, 'orders-mcp'))


def _reload_handler():
    """Reload lambda_function module to avoid cross-test contamination."""
    if 'lambda_function' in sys.modules:
        del sys.modules['lambda_function']
    import lambda_function
    return lambda_function.lambda_handler


class TestEcommerceMCP:
    """Test Ecommerce MCP Server"""

    def setup_method(self):
        # Ensure ecommerce-mcp is first in path
        ecommerce_path = os.path.join(_BASE, 'ecommerce-mcp')
        if ecommerce_path in sys.path:
            sys.path.remove(ecommerce_path)
        sys.path.insert(0, ecommerce_path)
        self.handler = _reload_handler()

    def test_tools_list(self):
        """Test that tools/list returns available tools"""
        event = {'method': 'tools/list'}
        result = self.handler(event, None)

        assert result['jsonrpc'] == '2.0'
        assert 'result' in result
        assert 'tools' in result['result']
        assert len(result['result']['tools']) == 2  # list_customers, get_customer_by_id

    def test_list_customers(self):
        """Test list_customers tool"""
        event = {
            'method': 'tools/call',
            'params': {
                'name': 'demo-ecommerce-mcp___list_customers',
                'arguments': {}
            }
        }
        result = self.handler(event, None)

        assert result['jsonrpc'] == '2.0'
        assert 'result' in result
        content = json.loads(result['result']['content'][0]['text'])
        assert 'customers' in content
        assert len(content['customers']) == 5

    def test_get_customer_by_id(self):
        """Test get_customer_by_id tool"""
        event = {
            'method': 'tools/call',
            'params': {
                'name': 'demo-ecommerce-mcp___get_customer_by_id',
                'arguments': {'customer_id': 'CUST-001'}
            }
        }
        result = self.handler(event, None)

        assert result['jsonrpc'] == '2.0'
        assert 'result' in result
        content = json.loads(result['result']['content'][0]['text'])
        assert content['id'] == 'CUST-001'
        assert content['name'] == 'Acme Corporation'

    def test_customer_not_found(self):
        """Test error handling for non-existent customer"""
        event = {
            'method': 'tools/call',
            'params': {
                'name': 'demo-ecommerce-mcp___get_customer_by_id',
                'arguments': {'customer_id': 'CUST-999'}
            }
        }
        result = self.handler(event, None)

        assert result['jsonrpc'] == '2.0'
        assert 'error' in result
        assert 'not found' in result['error']['message'].lower()


class TestProductsMCP:
    """Test Products MCP Server"""

    def setup_method(self):
        products_path = os.path.join(_BASE, 'products-mcp')
        if products_path in sys.path:
            sys.path.remove(products_path)
        sys.path.insert(0, products_path)
        self.handler = _reload_handler()

    def test_tools_list(self):
        """Test that tools/list returns available tools"""
        event = {'method': 'tools/list'}
        result = self.handler(event, None)

        assert result['jsonrpc'] == '2.0'
        assert len(result['result']['tools']) == 3  # list, search, get_by_id

    def test_list_products(self):
        """Test list_products tool"""
        event = {
            'method': 'tools/call',
            'params': {
                'name': 'demo-products-mcp___list_products',
                'arguments': {}
            }
        }
        result = self.handler(event, None)

        assert 'result' in result
        content = json.loads(result['result']['content'][0]['text'])
        assert len(content['products']) == 8

    def test_search_products(self):
        """Test search_products tool"""
        event = {
            'method': 'tools/call',
            'params': {
                'name': 'demo-products-mcp___search_products',
                'arguments': {'keyword': 'mouse'}
            }
        }
        result = self.handler(event, None)

        assert 'result' in result
        content = json.loads(result['result']['content'][0]['text'])
        assert content['total'] >= 1
        assert 'mouse' in content['products'][0]['name'].lower()


class TestOrdersMCP:
    """Test Orders MCP Server"""

    def setup_method(self):
        orders_path = os.path.join(_BASE, 'orders-mcp')
        if orders_path in sys.path:
            sys.path.remove(orders_path)
        sys.path.insert(0, orders_path)
        self.handler = _reload_handler()

    def test_tools_list(self):
        """Test that tools/list returns available tools"""
        event = {'method': 'tools/list'}
        result = self.handler(event, None)

        assert result['jsonrpc'] == '2.0'
        assert len(result['result']['tools']) == 3  # list, get_by_id, create

    def test_list_orders(self):
        """Test list_orders tool"""
        event = {
            'method': 'tools/call',
            'params': {
                'name': 'demo-orders-mcp___list_orders',
                'arguments': {}
            }
        }
        result = self.handler(event, None)

        assert 'result' in result
        content = json.loads(result['result']['content'][0]['text'])
        assert len(content['orders']) == 4

    def test_create_order(self):
        """Test create_order tool"""
        event = {
            'method': 'tools/call',
            'params': {
                'name': 'demo-orders-mcp___create_order',
                'arguments': {
                    'customer_id': 'CUST-001',
                    'items': [
                        {'product_id': 'PROD-001', 'quantity': 2}
                    ]
                }
            }
        }
        result = self.handler(event, None)

        assert 'result' in result
        content = json.loads(result['result']['content'][0]['text'])
        assert content['order']['customer_id'] == 'CUST-001'
        assert content['order']['status'] == 'pending'
