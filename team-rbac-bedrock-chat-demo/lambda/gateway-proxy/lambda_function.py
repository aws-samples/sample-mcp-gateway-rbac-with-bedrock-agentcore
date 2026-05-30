"""
LLM Gateway Lambda Function

This Lambda acts as a proxy between API Gateway and AWS Bedrock.
It provides team-based access control and cost attribution.

Architecture:
    Browser → API Gateway → This Lambda → AWS Bedrock Models

Key Features:
- Team identification from API Gateway API keys
- Model access control per team (e.g., Team Alpha: Haiku+Sonnet, Team Beta: Haiku only)
- Audit logging with team attribution
- Cost tracking per team
- Optional guardrails integration

Environment Variables:
- TEAM_ALPHA_MODELS: Comma-separated list of allowed models (e.g., "haiku,sonnet")
- TEAM_BETA_MODELS: Comma-separated list of allowed models (e.g., "haiku")
- GUARDRAIL_ID: (Optional) Bedrock Guardrail ID
- GUARDRAIL_VERSION: (Optional) Guardrail version (default: "DRAFT")
"""

import json
import boto3
import os
from datetime import datetime

# Initialize Bedrock client - calls AWS Bedrock API directly
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# Model ID mappings (short names → full ARNs)
MODEL_IDS = {
    'haiku': 'us.anthropic.claude-3-5-haiku-20241022-v1:0',
    'sonnet': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
    'opus': 'us.anthropic.claude-opus-4-20250514-v1:0'
}


def lambda_handler(event, context):
    """
    Main handler - proxies chat requests to Bedrock with team-based governance.

    Expected Request Body:
    {
        "team": "team-alpha",           # Team identifier (validated against API key)
        "prompt": "What is AI?",        # User's chat message
        "model_id": "us.anthropic...",  # Bedrock model ID
        "max_tokens": 200               # Max response length
    }

    Returns:
    {
        "response": "AI is...",          # Model's text response
        "usage": {
            "input_tokens": 10,
            "output_tokens": 50
        },
        "latency": 1.23,
        "team": "team-alpha"
    }
    """

    try:
        # Extract request context from API Gateway
        request_context = event.get('requestContext', {})
        request_id = request_context.get('requestId', 'unknown')
        source_ip = request_context.get('identity', {}).get('sourceIp', 'unknown')

        # Get API key from API Gateway (after validation)
        # API Gateway validates the key before Lambda is invoked
        api_key = request_context.get('identity', {}).get('apiKey', 'unknown')

        # Parse request body
        body = json.loads(event.get('body', '{}'))
        team = body.get('team', 'unknown')
        prompt = body.get('prompt', '')
        model_id = body.get('model_id', MODEL_IDS['haiku'])
        max_tokens = body.get('max_tokens', 200)
        guardrail_id = body.get('guardrail_id', os.environ.get('GUARDRAIL_ID'))
        guardrail_version = body.get('guardrail_version', os.environ.get('GUARDRAIL_VERSION', 'DRAFT'))

        # SECURITY: Map API key to team to prevent spoofing
        # In production, store this mapping in AWS Secrets Manager or DynamoDB
        actual_team = map_api_key_to_team(api_key)

        # If actual_team is None, we're in demo mode (no key mapping configured)
        # and trust the team from the request body. In production, always validate.
        if actual_team is not None and actual_team != team:
            return error_response(403, f"API key does not match team {team}")

        # MODEL GOVERNANCE: Check if team has access to requested model
        allowed = is_model_allowed_for_team(team, model_id)

        if not allowed:
            allowed_models = get_team_allowed_models(team)

            # Log denied access attempt
            log_audit_event({
                'timestamp': datetime.now().isoformat(),
                'request_id': request_id,
                'team': team,
                'model': model_id,
                'status': 'model_denied',
                'allowed_models': allowed_models
            })

            return error_response(403,
                f"Team {team} is not permitted to use model {model_id}. "
                f"Allowed models: {', '.join(allowed_models)}")

        # Build Bedrock API request
        bedrock_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{
                "role": "user",
                "content": prompt
            }]
        }

        # Invoke Bedrock model
        start_time = datetime.now()

        invoke_params = {
            'modelId': model_id,
            'body': json.dumps(bedrock_body)
        }

        # Add optional guardrails
        if guardrail_id:
            invoke_params['guardrailIdentifier'] = guardrail_id
            invoke_params['guardrailVersion'] = guardrail_version

        # Call AWS Bedrock API directly (NOT AgentCore Gateway)
        response = bedrock.invoke_model(**invoke_params)

        latency = (datetime.now() - start_time).total_seconds()

        # Parse Bedrock response
        response_body = json.loads(response['body'].read())
        usage = response_body.get('usage', {})
        assistant_message = response_body.get('content', [{}])[0].get('text', '')

        # Log successful request for cost attribution and audit
        log_audit_event({
            'timestamp': datetime.now().isoformat(),
            'request_id': request_id,
            'source_ip': source_ip,
            'team': team,
            'model': model_id,
            'status': 'success',
            'input_tokens': usage.get('input_tokens', 0),
            'output_tokens': usage.get('output_tokens', 0),
            'latency_seconds': latency,
            'guardrail_applied': bool(guardrail_id)
        })

        # Return response in format expected by UI
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,x-api-key',
                'Access-Control-Allow-Methods': 'POST,OPTIONS'
            },
            'body': json.dumps({
                'response': assistant_message,
                'usage': usage,
                'latency': latency,
                'team': team,
                'request_id': request_id
            })
        }

    except Exception as e:
        # Log error for debugging
        log_audit_event({
            'timestamp': datetime.now().isoformat(),
            'request_id': request_id,
            'status': 'error',
            'error': str(e)
        })

        return error_response(500, f"Internal error: {str(e)}")


def map_api_key_to_team(api_key):
    """
    Map API Gateway API key to team identifier.

    SECURITY NOTE: This prevents clients from spoofing their team identity.
    In production, store this mapping securely in AWS Secrets Manager or DynamoDB.

    For this demo, we read the mapping from an environment variable:
      API_KEY_TEAM_MAPPING='{"key1":"team-alpha","key2":"team-beta"}'

    If no mapping is configured (common in demo mode where HTTP API doesn't
    validate keys), we trust the team field from the request body by returning
    None — the caller skips the validation check.

    Args:
        api_key: API key from API Gateway request context

    Returns:
        str or None: Team identifier, or None to skip validation (demo mode)
    """
    # Production: Use Secrets Manager or DynamoDB
    # secrets = boto3.client('secretsmanager')
    # mapping = json.loads(secrets.get_secret_value(SecretId='api-key-team-mapping')['SecretString'])
    # return mapping.get(api_key, 'unknown')

    # Demo mode: Read from environment variable if configured
    mapping_json = os.environ.get('API_KEY_TEAM_MAPPING', '')
    if mapping_json:
        try:
            mapping = json.loads(mapping_json)
            return mapping.get(api_key, 'unknown')
        except (json.JSONDecodeError, TypeError):
            pass

    # If no mapping configured, skip API key validation (demo mode).
    # The team from the request body is trusted directly.
    return None


def is_model_allowed_for_team(team, model_id):
    """
    Check if a team has permission to use a specific model.

    Model permissions can be configured via:
    - Lambda environment variables (simple, shown here)
    - DynamoDB table (flexible, production recommended)
    - IAM policies (AWS-level enforcement)

    Args:
        team: Team identifier
        model_id: Bedrock model ID

    Returns:
        bool: True if team can use this model
    """
    allowed_models = get_team_allowed_models(team)
    return model_id in allowed_models


def get_team_allowed_models(team):
    """
    Get list of models a team is allowed to use.

    Reads from Lambda environment variables:
    - TEAM_ALPHA_MODELS="haiku,sonnet"
    - TEAM_BETA_MODELS="haiku"

    Args:
        team: Team identifier

    Returns:
        list: Full model IDs allowed for this team
    """
    env_var = f"{team.upper().replace('-', '_')}_MODELS"
    models_csv = os.environ.get(env_var, 'haiku')  # Default to Haiku

    # Convert short names to full model IDs
    short_names = [m.strip() for m in models_csv.split(',')]
    full_ids = [MODEL_IDS.get(name, name) for name in short_names]

    return full_ids


def log_audit_event(event):
    """
    Log audit event to CloudWatch Logs for cost tracking and compliance.

    These logs enable:
    - Cost attribution per team (filter by team in CloudWatch Insights)
    - Security auditing (who accessed what model when)
    - Usage analytics (which teams use which models)

    Args:
        event: Dict with audit information
    """
    print(json.dumps(event))  # CloudWatch Logs


def error_response(status_code, message):
    """
    Create standardized error response.

    Args:
        status_code: HTTP status code
        message: Error message

    Returns:
        dict: API Gateway proxy response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,x-api-key',
            'Access-Control-Allow-Methods': 'POST,OPTIONS'
        },
        'body': json.dumps({
            'error': message
        })
    }
