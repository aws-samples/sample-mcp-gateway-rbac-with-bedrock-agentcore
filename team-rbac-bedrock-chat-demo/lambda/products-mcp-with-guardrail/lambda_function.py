"""
Products MCP Server with Guardrail Integration

Demonstrates Bedrock Guardrails for multi-lingual content filtering.

Two deployment modes:
1. STRICT mode: Uses guardrail configured to block certain Swedish words
2. LENIENT mode: Language-aware guardrail that understands context

Tools:
- list_products: List all products
- search_products: Search products by keyword
- get_product_by_id: Get product details by ID
"""

import json
import os
import boto3

# Guardrail configuration from environment
GUARDRAIL_ID = os.environ.get('GUARDRAIL_ID', '')  # Set to guardrail ID or leave empty
GUARDRAIL_VERSION = os.environ.get('GUARDRAIL_VERSION', 'DRAFT')

# Initialize Bedrock Runtime client
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')

# Sample product data
SAMPLE_PRODUCTS = [
    {
        "id": "PROD-001",
        "name": "Wireless Mouse",
        "category": "electronics",
        "price": 29.99,
        "stock": 150,
        "description": "Ergonomic wireless mouse with 2.4GHz connectivity"
    },
    {
        "id": "PROD-002",
        "name": "USB-C Cable",
        "category": "electronics",
        "price": 12.99,
        "stock": 0,
        "description": "Durable USB-C charging and data cable, 6ft length - Currently out of stock"
    },
    {
        "id": "PROD-003",
        "name": "Laptop Stand",
        "category": "accessories",
        "price": 45.00,
        "stock": 80,
        "description": "Adjustable aluminum laptop stand for better ergonomics with quick height adjustment"
    },
    {
        "id": "PROD-004",
        "name": "Mechanical Keyboard",
        "category": "electronics",
        "price": 89.99,
        "stock": 45,
        "description": "RGB mechanical keyboard with blue switches"
    },
    {
        "id": "PROD-005",
        "name": "Desk Organizer",
        "category": "accessories",
        "price": 24.50,
        "stock": 120,
        "description": "Multi-compartment desk organizer for office supplies with removable dividers"
    },
    {
        "id": "PROD-006",
        "name": "Monitor Arm",
        "category": "accessories",
        "price": 79.99,
        "stock": 60,
        "description": "Adjustable single monitor arm mount with gas spring"
    },
    {
        "id": "PROD-007",
        "name": "Webcam HD",
        "category": "electronics",
        "price": 59.99,
        "stock": 95,
        "description": "1080p HD webcam with built-in microphone"
    },
    {
        "id": "PROD-008",
        "name": "Headphone Stand",
        "category": "accessories",
        "price": 19.99,
        "stock": 200,
        "description": "Sleek aluminum headphone stand with cable holder"
    }
]


def apply_guardrail(content):
    """
    Apply Bedrock Guardrail to content

    Returns: (is_blocked, filtered_content, action)
    """
    if not GUARDRAIL_ID:
        # No guardrail configured - pass through
        return False, content, "NONE"

    try:
        response = bedrock_runtime.apply_guardrail(
            guardrailIdentifier=GUARDRAIL_ID,
            guardrailVersion=GUARDRAIL_VERSION,
            source='OUTPUT',
            content=[
                {
                    'text': {
                        'text': content
                    }
                }
            ]
        )

        action = response.get('action', 'NONE')

        if action == 'GUARDRAIL_INTERVENED':
            # Content was blocked
            outputs = response.get('outputs', [])
            filtered_text = outputs[0]['text'] if outputs else content
            return True, filtered_text, action
        else:
            # Content passed
            return False, content, action

    except Exception as e:
        print(f"Guardrail error: {str(e)}")
        # On error, pass through content but log the error
        return False, content, f"ERROR: {str(e)}"


def lambda_handler(event, context):
    """MCP Server Lambda Handler with Guardrail Integration"""
    try:
        # Check if called via API Gateway (has 'body' field)
        if 'body' in event:
            # API Gateway format
            import json as json_lib
            body = json_lib.loads(event['body']) if isinstance(event['body'], str) else event['body']
            method = body.get('method')
            params = body.get('params', {})
        else:
            # Direct Lambda invocation
            method = event.get('method')
            params = event.get('params', {})

        # Log guardrail configuration
        guardrail_mode = "STRICT" if GUARDRAIL_ID else "LENIENT"
        print(f"Guardrail Mode: {guardrail_mode}")
        if GUARDRAIL_ID:
            print(f"Guardrail ID: {GUARDRAIL_ID}")

        # Process MCP request
        if method == 'tools/list':
            result = mcp_tools_list()
        elif method == 'tools/call':
            result = mcp_tools_call(params)
        else:
            result = mcp_error(f"Unknown method: {method}")

        # Return based on invocation type
        if 'body' in event:
            # API Gateway response
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Api-Key',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS'
                },
                'body': json.dumps(result)
            }
        else:
            # Direct Lambda invocation
            return result

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

        error_response = mcp_error(str(e))

        if 'body' in event:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(error_response)
            }
        else:
            return error_response


def mcp_tools_list():
    """Return list of available tools"""
    return {
        "jsonrpc": "2.0",
        "result": {
            "tools": [
                {
                    "name": "demo-products-mcp___list_products",
                    "description": "List all products with optional filtering by category",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Filter by product category",
                                "enum": ["electronics", "accessories"]
                            },
                            "in_stock_only": {
                                "type": "boolean",
                                "description": "Only show products with stock > 0"
                            }
                        }
                    }
                },
                {
                    "name": "demo-products-mcp___search_products",
                    "description": "Search products by keyword in name or description",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "keyword": {
                                "type": "string",
                                "description": "Search keyword"
                            }
                        },
                        "required": ["keyword"]
                    }
                },
                {
                    "name": "demo-products-mcp___get_product_by_id",
                    "description": "Get product details by product ID",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "Product ID (e.g., PROD-001)"
                            }
                        },
                        "required": ["product_id"]
                    }
                }
            ]
        }
    }


def mcp_tools_call(params):
    """Execute tool call"""
    tool_name = params.get('name', '')
    arguments = params.get('arguments', {})

    if tool_name == 'demo-products-mcp___list_products':
        return list_products(arguments)
    elif tool_name == 'demo-products-mcp___search_products':
        return search_products(arguments)
    elif tool_name == 'demo-products-mcp___get_product_by_id':
        return get_product_by_id(arguments)
    else:
        return mcp_error(f"Unknown tool: {tool_name}")


def list_products(args):
    """List products with optional filtering"""
    products = SAMPLE_PRODUCTS

    # Apply category filter
    if 'category' in args:
        products = [p for p in products if p['category'] == args['category']]

    # Apply stock filter
    if args.get('in_stock_only'):
        products = [p for p in products if p['stock'] > 0]

    # Generate response content
    response_content = json.dumps({
        "products": products,
        "total": len(products)
    }, indent=2)

    # Apply guardrail
    is_blocked, filtered_content, action = apply_guardrail(response_content)

    if is_blocked:
        print(f"⚠️  Guardrail blocked content - Action: {action}")
        return mcp_error(f"Content blocked by guardrail. The guardrail detected potentially inappropriate content. Guardrail: {GUARDRAIL_ID}")

    print(f"✅ Guardrail passed - Action: {action}")

    return {
        "jsonrpc": "2.0",
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": filtered_content
                }
            ],
            "metadata": {
                "guardrail_action": action,
                "guardrail_id": GUARDRAIL_ID or "none"
            }
        }
    }


def search_products(args):
    """Search products by keyword"""
    keyword = args.get('keyword', '').lower()

    if not keyword:
        return mcp_error("keyword is required")

    # Search in name and description
    results = [
        p for p in SAMPLE_PRODUCTS
        if keyword in p['name'].lower() or keyword in p['description'].lower()
    ]

    # Generate response content
    response_content = json.dumps({
        "products": results,
        "total": len(results),
        "keyword": keyword
    }, indent=2)

    # Apply guardrail
    is_blocked, filtered_content, action = apply_guardrail(response_content)

    if is_blocked:
        print(f"⚠️  Guardrail blocked content - Action: {action}")
        return mcp_error(f"Content blocked by guardrail. Swedish words were detected in search results. Guardrail: {GUARDRAIL_ID}")

    print(f"✅ Guardrail passed - Action: {action}")

    return {
        "jsonrpc": "2.0",
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": filtered_content
                }
            ],
            "metadata": {
                "guardrail_action": action,
                "guardrail_id": GUARDRAIL_ID or "none"
            }
        }
    }


def get_product_by_id(args):
    """Get product by ID"""
    product_id = args.get('product_id')

    if not product_id:
        return mcp_error("product_id is required")

    product = next((p for p in SAMPLE_PRODUCTS if p['id'] == product_id), None)

    if not product:
        return mcp_error(f"Product not found: {product_id}")

    # Generate response content
    response_content = json.dumps(product, indent=2)

    # Apply guardrail
    is_blocked, filtered_content, action = apply_guardrail(response_content)

    if is_blocked:
        print(f"⚠️  Guardrail blocked content - Action: {action}")
        return mcp_error(f"Content blocked by guardrail. Product description contains Swedish words. Guardrail: {GUARDRAIL_ID}")

    print(f"✅ Guardrail passed - Action: {action}")

    return {
        "jsonrpc": "2.0",
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": filtered_content
                }
            ],
            "metadata": {
                "guardrail_action": action,
                "guardrail_id": GUARDRAIL_ID or "none"
            }
        }
    }


def mcp_error(message):
    """Return MCP error response"""
    return {
        "jsonrpc": "2.0",
        "error": {
            "code": -32000,
            "message": message
        }
    }
