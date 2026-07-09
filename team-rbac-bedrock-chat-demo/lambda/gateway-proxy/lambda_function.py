"""
LLM Gateway Lambda — Team-Based Model Governance Proxy

Routes chat requests to AWS Bedrock with per-team model access control,
token budget enforcement (DynamoDB), structured audit logging, and optional
guardrail integration.

Architecture:
    Browser → API Gateway (REST + API Keys) → This Lambda → AWS Bedrock

Environment Variables:
    TEAM_ALPHA_MODELS       Comma-separated allowed model short names (e.g., "haiku,sonnet")
    TEAM_BETA_MODELS        Comma-separated allowed model short names (e.g., "haiku")
    GUARDRAIL_ID            (Optional) Bedrock Guardrail ID
    GUARDRAIL_VERSION       (Optional) Guardrail version (default: "DRAFT")
    API_KEY_TEAM_MAPPING    (Optional) JSON mapping of API keys to team names
    TOKEN_BUDGET_TABLE      DynamoDB table name for per-team token budgets
    DAILY_TOKEN_LIMIT       Default daily token limit per team (default: 100000)
    MONTHLY_TOKEN_LIMIT     Default monthly token limit per team (default: 2000000)
    THROTTLE_THRESHOLD      Fraction of daily limit at which soft throttle kicks in (default: 0.8)
    THROTTLE_MAX_TOKENS     Max output tokens when throttled (default: 500)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError as BotoClientError

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

MODEL_IDS: dict[str, str] = {
    "haiku": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "sonnet": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "opus": "us.anthropic.claude-opus-4-20250514-v1:0",
}

MAX_TOKENS_LIMIT = 4096
DEFAULT_DAILY_LIMIT = int(os.environ.get("DAILY_TOKEN_LIMIT", "100000"))
DEFAULT_MONTHLY_LIMIT = int(os.environ.get("MONTHLY_TOKEN_LIMIT", "2000000"))
THROTTLE_THRESHOLD = float(os.environ.get("THROTTLE_THRESHOLD", "0.8"))
THROTTLE_MAX_TOKENS = int(os.environ.get("THROTTLE_MAX_TOKENS", "500"))
TOKEN_BUDGET_TABLE = os.environ.get("TOKEN_BUDGET_TABLE", "")

_bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))


# ─────────────────────────────────────────────────────────────────────────────
# Domain Objects
# ─────────────────────────────────────────────────────────────────────────────

class ClientError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class Request:
    __slots__ = (
        "request_id", "source_ip", "api_key", "team", "prompt",
        "model_id", "max_tokens", "guardrail_id", "guardrail_version",
    )

    def __init__(self, request_id, source_ip, api_key, team, prompt,
                 model_id, max_tokens, guardrail_id, guardrail_version):
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
    __slots__ = ("text", "input_tokens", "output_tokens", "latency_seconds")

    def __init__(self, text, input_tokens, output_tokens, latency_seconds):
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_seconds = latency_seconds


# ─────────────────────────────────────────────────────────────────────────────
# Lambda Handler
# ─────────────────────────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_id = event.get("requestContext", {}).get("requestId", "unknown")
    try:
        request = _parse_request(event)
        _validate_team_identity(request)
        _enforce_model_governance(request)
        _enforce_token_budget(request)          # pre-call DynamoDB check
        response = _invoke_bedrock(request)
        _update_token_counters(request, response)  # post-call DynamoDB update
        _log_success(request, response)
        return _success_response(request, response)

    except ClientError as e:
        return _error_response(e.status_code, e.message)
    except json.JSONDecodeError:
        return _error_response(400, "Invalid JSON in request body")
    except Exception as e:
        _log_audit({"request_id": request_id, "status": "error", "error": str(e)})
        return _error_response(500, "An internal error occurred. Check CloudWatch logs.")


# ─────────────────────────────────────────────────────────────────────────────
# Request Parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_request(event: dict[str, Any]) -> Request:
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


# ─────────────────────────────────────────────────────────────────────────────
# Governance
# ─────────────────────────────────────────────────────────────────────────────

def _validate_team_identity(request: Request) -> None:
    actual_team = _map_api_key_to_team(request.api_key)
    if actual_team is not None and actual_team != request.team:
        raise ClientError(403, f"API key does not match team {request.team}")


def _enforce_model_governance(request: Request) -> None:
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


def _enforce_token_budget(request: Request) -> None:
    """
    Pre-call budget check. Raises ClientError(429) if daily or monthly limit exceeded.
    Applies soft throttle (reduces max_tokens) when 80% of daily budget is consumed.
    """
    if not TOKEN_BUDGET_TABLE:
        return  # budget enforcement disabled

    table = _dynamodb.Table(TOKEN_BUDGET_TABLE)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month = datetime.now(timezone.utc).strftime("%Y-%m")

    try:
        daily_item = table.get_item(Key={"teamId": request.team, "periodKey": today}).get("Item", {})
        monthly_item = table.get_item(Key={"teamId": request.team, "periodKey": month}).get("Item", {})
    except BotoClientError as e:
        # If DynamoDB is unreachable, log and allow the request (fail open)
        _log_audit({"request_id": request.request_id, "team": request.team,
                    "status": "budget_check_failed", "error": str(e)})
        return

    daily_used = int(daily_item.get("tokensUsed", 0))
    daily_limit = int(daily_item.get("dailyLimit", DEFAULT_DAILY_LIMIT))
    monthly_used = int(monthly_item.get("tokensUsed", 0))
    monthly_limit = int(monthly_item.get("monthlyLimit", DEFAULT_MONTHLY_LIMIT))

    if daily_used >= daily_limit:
        _log_audit({
            "request_id": request.request_id,
            "team": request.team,
            "status": "daily_limit_exceeded",
            "daily_used": daily_used,
            "daily_limit": daily_limit,
        })
        raise ClientError(
            429,
            f"Daily token budget exhausted ({daily_used:,}/{daily_limit:,} tokens). "
            "Budget resets at midnight UTC."
        )

    if monthly_used >= monthly_limit:
        _log_audit({
            "request_id": request.request_id,
            "team": request.team,
            "status": "monthly_limit_exceeded",
            "monthly_used": monthly_used,
            "monthly_limit": monthly_limit,
        })
        raise ClientError(
            429,
            f"Monthly token budget exhausted ({monthly_used:,}/{monthly_limit:,} tokens)."
        )

    # Soft throttle at THROTTLE_THRESHOLD of daily limit
    if daily_used >= daily_limit * THROTTLE_THRESHOLD:
        request.max_tokens = min(request.max_tokens, THROTTLE_MAX_TOKENS)
        _log_audit({
            "request_id": request.request_id,
            "team": request.team,
            "status": "throttled",
            "daily_used": daily_used,
            "daily_limit": daily_limit,
            "max_tokens_capped": request.max_tokens,
        })


def _update_token_counters(request: Request, response: BedrockResponse) -> None:
    """Atomically increment daily and monthly token counters in DynamoDB."""
    if not TOKEN_BUDGET_TABLE:
        return

    table = _dynamodb.Table(TOKEN_BUDGET_TABLE)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    total = response.input_tokens + response.output_tokens

    for period_key, limit_attr, limit_val in [
        (today, "dailyLimit", DEFAULT_DAILY_LIMIT),
        (month, "monthlyLimit", DEFAULT_MONTHLY_LIMIT),
    ]:
        try:
            table.update_item(
                Key={"teamId": request.team, "periodKey": period_key},
                UpdateExpression=(
                    "ADD tokensUsed :t "
                    "SET #team = if_not_exists(#team, :team_name), "
                    f"    {limit_attr} = if_not_exists({limit_attr}, :lim)"
                ),
                ExpressionAttributeNames={"#team": "team"},
                ExpressionAttributeValues={
                    ":t": total,
                    ":team_name": request.team,
                    ":lim": limit_val,
                },
            )
        except BotoClientError as e:
            _log_audit({"request_id": request.request_id, "team": request.team,
                        "status": "counter_update_failed", "error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# Bedrock Invocation
# ─────────────────────────────────────────────────────────────────────────────

def _invoke_bedrock(request: Request) -> BedrockResponse:
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
# Model Governance Helpers
# ─────────────────────────────────────────────────────────────────────────────

def is_model_allowed_for_team(team: str, model_id: str) -> bool:
    return model_id in get_team_allowed_models(team)


def get_team_allowed_models(team: str) -> list[str]:
    env_var = f"{team.upper().replace('-', '_')}_MODELS"
    models_csv = os.environ.get(env_var, "haiku")
    short_names = [m.strip() for m in models_csv.split(",")]
    return [MODEL_IDS.get(name, name) for name in short_names]


def _map_api_key_to_team(api_key: str) -> Optional[str]:
    mapping_json = os.environ.get("API_KEY_TEAM_MAPPING", "")
    if mapping_json:
        try:
            return json.loads(mapping_json).get(api_key, "unknown")
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
    return {
        "statusCode": status_code,
        "headers": _CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Audit Logging (structured JSON → CloudWatch Insights)
# ─────────────────────────────────────────────────────────────────────────────

def _log_success(request: Request, response: BedrockResponse) -> None:
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
    event_data["timestamp"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(event_data))
