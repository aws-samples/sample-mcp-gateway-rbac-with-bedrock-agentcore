"""
LLM Gateway Lambda — Team-Based Model Governance Proxy

Routes chat requests to AWS Bedrock with per-team model access control,
structured audit logging, and optional guardrail integration.

Architecture:
    Browser → API Gateway (REST + API Keys) → This Lambda → AWS Bedrock

Environment Variables:
    TEAM_ALPHA_MODELS  Comma-separated allowed model short names (e.g., "haiku,sonnet")
    TEAM_BETA_MODELS   Comma-separated allowed model short names (e.g., "haiku")
    GUARDRAIL_ID       (Optional) Bedrock Guardrail ID
    GUARDRAIL_VERSION  (Optional) Guardrail version (default: "DRAFT")
    API_KEY_TEAM_MAPPING  (Optional) JSON mapping of API keys to team names
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

import boto3

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Model short names → full Bedrock model IDs (cross-region inference profiles)
MODEL_IDS: dict[str, str] = {
    "haiku": os.environ.get("MODEL_ID_HAIKU", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
    "sonnet": os.environ.get("MODEL_ID_SONNET", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    "opus": os.environ.get("MODEL_ID_OPUS", "us.anthropic.claude-opus-4-20250514-v1:0"),
}

MAX_TOKENS_LIMIT = 4096

# Bedrock client (initialized once per Lambda container)
_bedrock = boto3.client(
    "bedrock-runtime",
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
)


# ─────────────────────────────────────────────────────────────────────────────
# Lambda Handler
# ─────────────────────────────────────────────────────────────────────────────


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Entry point. Parses the API Gateway event and orchestrates governance + invocation.

    Expected body: {"team": "team-alpha", "prompt": "...", "model_id": "...", "max_tokens": 200}
    """
    request_id = event.get("requestContext", {}).get("requestId", "unknown")

    try:
        request = _parse_request(event)
        _validate_team_identity(request)
        _enforce_model_governance(request)
        response = _invoke_bedrock(request)
        _log_success(request, response)
        return _success_response(request, response)

    except ClientError as e:
        return _error_response(e.status_code, e.message)
    except json.JSONDecodeError:
        return _error_response(400, "Invalid JSON in request body")
    except Exception as e:
        _log_audit({"request_id": request_id, "status": "error", "error": str(e)})
        # Don't expose internal details to clients
        return _error_response(500, "An internal error occurred. Check CloudWatch logs.")


# ─────────────────────────────────────────────────────────────────────────────
# Request Processing Pipeline
# ─────────────────────────────────────────────────────────────────────────────


class ClientError(Exception):
    """Raised for client-facing errors with HTTP status codes."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class Request:
    """Parsed and validated request context."""

    __slots__ = (
        "request_id", "source_ip", "api_key", "team", "prompt",
        "model_id", "max_tokens", "guardrail_id", "guardrail_version",
    )

    def __init__(
        self,
        request_id: str,
        source_ip: str,
        api_key: str,
        team: str,
        prompt: str,
        model_id: str,
        max_tokens: int,
        guardrail_id: Optional[str],
        guardrail_version: str,
    ) -> None:
        self.request_id = request_id
        self.source_ip = source_ip
        self.api_key = api_key
        self.team = team
        self.prompt = prompt
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version


class BedrockResponse:
    """Parsed Bedrock invocation result."""

    __slots__ = ("text", "input_tokens", "output_tokens", "latency_seconds")

    def __init__(self, text: str, input_tokens: int, output_tokens: int, latency_seconds: float) -> None:
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_seconds = latency_seconds


def _parse_request(event: dict[str, Any]) -> Request:
    """Extract and validate request fields from API Gateway event."""
    request_context = event.get("requestContext", {})
    body = json.loads(event.get("body", "{}"))

    prompt = body.get("prompt", "")
    if not prompt:
        raise ClientError(400, "prompt is required")

    return Request(
        request_id=request_context.get("requestId", "unknown"),
        source_ip=request_context.get("identity", {}).get("sourceIp", "unknown"),
        api_key=request_context.get("identity", {}).get("apiKey", "unknown"),
        team=body.get("team", "unknown"),
        prompt=prompt,
        model_id=body.get("model_id", MODEL_IDS["haiku"]),
        max_tokens=min(body.get("max_tokens", 200), MAX_TOKENS_LIMIT),
        guardrail_id=os.environ.get("GUARDRAIL_ID") or None,
        guardrail_version=os.environ.get("GUARDRAIL_VERSION", "DRAFT"),
    )


def _validate_team_identity(request: Request) -> None:
    """
    Resolve team from API key and override the client-claimed team.

    API Gateway validates the key exists via usage plans. We resolve which
    team owns the key so the client cannot spoof a different team identity.
    """
    resolved_team = _resolve_team_from_api_key(request.api_key)
    if resolved_team is not None:
        if resolved_team != request.team:
            _log_audit({
                "request_id": request.request_id,
                "status": "team_spoofing_blocked",
                "claimed_team": request.team,
                "actual_team": resolved_team,
            })
        # Always use the server-resolved team, ignoring client claim
        request.team = resolved_team


def _enforce_model_governance(request: Request) -> None:
    """Check if the team has permission to use the requested model."""
    if not is_model_allowed_for_team(request.team, request.model_id):
        allowed = get_team_allowed_models(request.team)
        _log_audit({
            "request_id": request.request_id,
            "team": request.team,
            "model": request.model_id,
            "status": "model_denied",
            "allowed_models": allowed,
        })
        raise ClientError(
            403,
            f"Team {request.team} is not permitted to use model {request.model_id}. "
            f"Allowed models: {', '.join(allowed)}",
        )


def _invoke_bedrock(request: Request) -> BedrockResponse:
    """Call Bedrock with the validated request."""
    bedrock_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": request.max_tokens,
        "messages": [{"role": "user", "content": request.prompt}],
    }

    invoke_params: dict[str, Any] = {
        "modelId": request.model_id,
        "body": json.dumps(bedrock_body),
    }

    if request.guardrail_id:
        invoke_params["guardrailIdentifier"] = request.guardrail_id
        invoke_params["guardrailVersion"] = request.guardrail_version

    start = datetime.now(timezone.utc)
    response = _bedrock.invoke_model(**invoke_params)
    latency = (datetime.now(timezone.utc) - start).total_seconds()

    response_body = json.loads(response["body"].read())
    usage = response_body.get("usage", {})

    return BedrockResponse(
        text=response_body.get("content", [{}])[0].get("text", ""),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        latency_seconds=latency,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Model Governance
# ─────────────────────────────────────────────────────────────────────────────


def is_model_allowed_for_team(team: str, model_id: str) -> bool:
    """Check if a team has permission to use a specific model."""
    return model_id in get_team_allowed_models(team)


def get_team_allowed_models(team: str) -> list[str]:
    """
    Resolve the full Bedrock model IDs a team is allowed to use.

    Reads from environment variables: TEAM_ALPHA_MODELS, TEAM_BETA_MODELS, etc.
    """
    env_var = f"{team.upper().replace('-', '_')}_MODELS"
    models_csv = os.environ.get(env_var, "haiku")
    short_names = [m.strip() for m in models_csv.split(",")]
    return [MODEL_IDS.get(name, name) for name in short_names]


def _resolve_team_from_api_key(api_key: str) -> Optional[str]:
    """
    Resolve team identity from the API Gateway API key.

    Uses environment variables set by CloudFormation:
        TEAM_ALPHA_API_KEY=<api-key-value>
        TEAM_BETA_API_KEY=<api-key-value>

    Falls back to API_KEY_TEAM_MAPPING JSON env var for custom mappings.
    Returns None only if no mapping is configured (allows client self-identification
    for local testing without API Gateway).
    """
    if not api_key or api_key == "unknown":
        return None

    # Check per-team key env vars (set by CloudFormation or deploy script)
    for env_key, env_val in os.environ.items():
        if env_key.endswith("_API_KEY") and env_val == api_key:
            # TEAM_ALPHA_API_KEY → team-alpha
            team_name = env_key.replace("_API_KEY", "").lower().replace("_", "-")
            return team_name

    # Fallback: JSON mapping env var
    mapping_json = os.environ.get("API_KEY_TEAM_MAPPING", "")
    if mapping_json:
        try:
            mapping = json.loads(mapping_json)
            return mapping.get(api_key)
        except (json.JSONDecodeError, TypeError):
            pass

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Response Formatting
# ─────────────────────────────────────────────────────────────────────────────

_CORS_HEADERS: dict[str, str] = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,x-api-key",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}


def _success_response(request: Request, response: BedrockResponse) -> dict[str, Any]:
    """Format a successful invocation as an API Gateway response."""
    return {
        "statusCode": 200,
        "headers": _CORS_HEADERS,
        "body": json.dumps({
            "response": response.text,
            "usage": {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
            },
            "latency": response.latency_seconds,
            "team": request.team,
            "request_id": request.request_id,
        }),
    }


def _error_response(status_code: int, message: str) -> dict[str, Any]:
    """Format a client-facing error as an API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": _CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Audit Logging
# ─────────────────────────────────────────────────────────────────────────────


def _log_success(request: Request, response: BedrockResponse) -> None:
    """Log a structured audit event for successful invocations."""
    _log_audit({
        "request_id": request.request_id,
        "source_ip": request.source_ip,
        "team": request.team,
        "model": request.model_id,
        "status": "success",
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "latency_seconds": response.latency_seconds,
        "guardrail_applied": bool(request.guardrail_id),
    })


def _log_audit(event_data: dict[str, Any]) -> None:
    """
    Emit a structured JSON log line for CloudWatch Insights.

    Query example:
        fields @timestamp, team, model, status
        | filter status = 'model_denied'
        | stats count() by team
    """
    event_data["timestamp"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(event_data))
