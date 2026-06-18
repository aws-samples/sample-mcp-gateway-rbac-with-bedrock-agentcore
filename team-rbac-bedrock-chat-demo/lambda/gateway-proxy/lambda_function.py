"""
LLM Gateway Lambda Function

This Lambda acts as a proxy between API Gateway and AWS Bedrock.
It provides team-based access control and cost attribution.

Architecture:
    Browser → API Gateway (REST + API Keys) → This Lambda → AWS Bedrock Models

Key Features:
- Team identification from API Gateway API keys
- Model access control per team (e.g., Team Alpha: Haiku+Sonnet, Team Beta: Haiku only)
- Structured audit logging with team attribution (CloudWatch Insights compatible)
- Cost tracking per team
- Optional Bedrock Guardrails integration

Environment Variables:
- TEAM_ALPHA_MODELS: Comma-separated list of allowed models (e.g., "haiku,sonnet")
- TEAM_BETA_MODELS: Comma-separated list of allowed models (e.g., "haiku")
- GUARDRAIL_ID: (Optional) Bedrock Guardrail ID
- GUARDRAIL_VERSION: (Optional) Guardrail version (default: "DRAFT")
- API_KEY_TEAM_MAPPING: (Optional) JSON mapping of API keys to team names

NOTE: This is a demo. For production deployments:
- Store API key → team mappings in Secrets Manager or DynamoDB
- Add input validation and prompt sanitization
- Enable WAF on API Gateway
- Use VPC endpoints for Bedrock access
"""

import json
import boto3
import os
from datetime import datetime, timezone

# Initialize Bedrock client
bedrock = boto3.client(
    'bedrock-runtime',
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)

# Model ID mappings (short names → full Bedrock model IDs)
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
        "team": "team-alpha",
        "prompt": "What is AI?",
        "model_id": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        "max_tokens": 200
    }
    """
    request_id = 'unknown'

    try:
        # Extract request context from API Gateway
        request_context = event.get('requestContext', {})
        request_id = request_context.get('requestId', 'unknown')
        source_ip = request_context.get('identity', {}).get('sourceIp', 'unknown')

        # Get API key from API Gateway (after validation by usage plan)
        api_key = request_context.get('identity', {}).get('apiKey', 'unknown')

        # Parse request body
        body = json.loads(event.get('body', '{}'))
        team = body.get('team', 'unknown')
        prompt = body.get('prompt', '')
        model_id = body.get('model_id', MODEL_IDS['haiku'])
        max_tokens = min(body.get('max_tokens', 200), 4096)
        guardrail_id = os.environ.get('GUARDRAIL_ID')
        guardrail_version = os.environ.get('GUARDRAIL_VERSION', 'DRAFT')

        if not prompt:
            return error_response(400, "prompt is required")

        # Map API key to team to prevent spoofing
        actual_team = map_api_key_to_team(api_key)
        if actual_team is not None and actual_team != team:
            return error_response(403, f"API key does not match team {team}")

        # MODEL GOVERNANCE: Check if team has access to requested model
        if not is_model_allowed_for_team(team, model_id):
            allowed_models = get_team_allowed_models(team)

            log_audit_event({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'request_id': request_id,
                'team': team,
                'model': model_id,
                'status': 'model_denied',
                'allowed_models': allowed_models
            })

            return error_response(
                403,
                f"Team {team} is not permitted to use model {model_id}. "
                f"Allowed models: {', '.join(allowed_models)}"
            )

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
        start_time = datetime.now(timezone.utc)

        invoke_params = {
            'modelId': model_id,
            'body': json.dumps(bedrock_body)
        }

        # Add optional guardrails
        if guardrail_id:
            invoke_params['guardrailIdentifier'] = guardrail_id
            invoke_params['guardrailVersion'] = guardrail_version

        response = bedrock.invoke_model(**invoke_params)

        latency = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Parse Bedrock response
        response_body = json.loads(response['body'].read())
        usage = response_body.get('usage', {})
        assistant_message = response_body.get('content', [{}])[0].get('text', '')

        # Log successful request for cost attribution and audit
        log_audit_event({
            'timestamp': datetime.now(timezone.utc).isoformat(),
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

        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': json.dumps({
                'response': assistant_message,
                'usage': usage,
                'latency': latency,
                'team': team,
                'request_id': request_id
            })
        }

    except json.JSONDecodeError:
        return error_response(400, "Invalid JSON in request body")
    except Exception as e:
        log_audit_event({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'request_id': request_id,
            'status': 'error',
            'error': str(e)
        })
        return error_response(500, f"Internal error: {str(e)}")


def map_api_key_to_team(api_key):
    """
    Map API Gateway API key to team identifier.

    Returns None to skip validation (demo mode without key mapping).
    In production, use Secrets Manager or DynamoDB for this mapping.
    """
    mapping_json = os.environ.get('API_KEY_TEAM_MAPPING', '')
    if mapping_json:
        try:
            mapping = json.loads(mapping_json)
            return mapping.get(api_key, 'unknown')
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def is_model_allowed_for_team(team, model_id):
    """Check if a team has permission to use a specific model."""
    allowed_models = get_team_allowed_models(team)
    return model_id in allowed_models


def get_team_allowed_models(team):
    """
    Get list of full model IDs a team is allowed to use.

    Reads from Lambda environment variables:
    - TEAM_ALPHA_MODELS="haiku,sonnet"
    - TEAM_BETA_MODELS="haiku"
    """
    env_var = f"{team.upper().replace('-', '_')}_MODELS"
    models_csv = os.environ.get(env_var, 'haiku')

    short_names = [m.strip() for m in models_csv.split(',')]
    full_ids = [MODEL_IDS.get(name, name) for name in short_names]
    return full_ids


def log_audit_event(event_data):
    """
    Log structured audit event to CloudWatch Logs.

    Use CloudWatch Insights to query:
      fields @timestamp, team, model, status
      | filter status = 'model_denied'
      | stats count() by team
    """
    print(json.dumps(event_data))


def cors_headers():
    """Return standard CORS headers for API responses."""
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,x-api-key',
        'Access-Control-Allow-Methods': 'POST,OPTIONS'
    }


def error_response(status_code, message):
    """Create standardized error response."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(),
        'body': json.dumps({'error': message})
    }
