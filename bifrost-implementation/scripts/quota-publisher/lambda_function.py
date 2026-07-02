"""
Bifrost AI Gateway — Quota Utilisation Publisher

Runs every 5 minutes via EventBridge. Reads today's cumulative token
counts from CloudWatch metrics (published by the ADOT collector from
Bifrost's Prometheus endpoint) and computes QuotaUtilisationPct for
each team. Publishes the result back to CloudWatch as a gauge metric.

Metrics written:
  Namespace:  Bifrost/Gateway
  MetricName: QuotaUtilisationPct
  Dimensions: team=<team-alpha|team-beta>
  Value:      0–100+ (percentage of daily token limit consumed)
  Unit:       Percent
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

NAMESPACE   = os.environ.get("NAMESPACE", "Bifrost/Gateway")
REGION      = os.environ.get("REGION", "us-east-1")

TEAMS: dict[str, int] = {
    "team-alpha": int(os.environ.get("TEAM_ALPHA_DAILY_LIMIT", "100000")),
    "team-beta":  int(os.environ.get("TEAM_BETA_DAILY_LIMIT",  "50000")),
}

cw = boto3.client("cloudwatch", region_name=REGION)


def _get_today_token_sum(team: str) -> int:
    """
    Query CloudWatch for the sum of TokensInput + TokensOutput for `team`
    over the last 24 hours (midnight-to-now UTC).
    Returns 0 if no data is available yet.
    """
    now   = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    query_id_input  = f"{team.replace('-','_')}_input"
    query_id_output = f"{team.replace('-','_')}_output"

    result = cw.get_metric_data(
        MetricDataQueries=[
            {
                "Id":    query_id_input,
                "Label": f"{team} input tokens",
                "MetricStat": {
                    "Metric": {
                        "Namespace":  NAMESPACE,
                        "MetricName": "TokensInput",
                        "Dimensions": [{"Name": "team", "Value": team}],
                    },
                    "Period": 86400,  # 24h bucket
                    "Stat":   "Sum",
                },
                "ReturnData": True,
            },
            {
                "Id":    query_id_output,
                "Label": f"{team} output tokens",
                "MetricStat": {
                    "Metric": {
                        "Namespace":  NAMESPACE,
                        "MetricName": "TokensOutput",
                        "Dimensions": [{"Name": "team", "Value": team}],
                    },
                    "Period": 86400,
                    "Stat":   "Sum",
                },
                "ReturnData": True,
            },
        ],
        StartTime=start,
        EndTime=now,
    )

    total = 0
    for r in result.get("MetricDataResults", []):
        vals = r.get("Values", [])
        if vals:
            total += int(vals[-1])  # most recent value in the window

    return total


def _publish_quota_pct(team: str, pct: float) -> None:
    """Push QuotaUtilisationPct to CloudWatch."""
    cw.put_metric_data(
        Namespace=NAMESPACE,
        MetricData=[
            {
                "MetricName": "QuotaUtilisationPct",
                "Dimensions": [{"Name": "team", "Value": team}],
                "Value":      round(pct, 2),
                "Unit":       "Percent",
                "Timestamp":  datetime.now(timezone.utc),
            }
        ],
    )


def _publish_tokens_used(team: str, tokens_used: int, daily_limit: int) -> None:
    """Push absolute token counters as CloudWatch metrics for dashboard bars."""
    cw.put_metric_data(
        Namespace=NAMESPACE,
        MetricData=[
            {
                "MetricName": "DailyTokensUsed",
                "Dimensions": [{"Name": "team", "Value": team}],
                "Value":      float(tokens_used),
                "Unit":       "Count",
                "Timestamp":  datetime.now(timezone.utc),
            },
            {
                "MetricName": "DailyTokenLimit",
                "Dimensions": [{"Name": "team", "Value": team}],
                "Value":      float(daily_limit),
                "Unit":       "Count",
                "Timestamp":  datetime.now(timezone.utc),
            },
            {
                "MetricName": "DailyTokensRemaining",
                "Dimensions": [{"Name": "team", "Value": team}],
                "Value":      float(max(0, daily_limit - tokens_used)),
                "Unit":       "Count",
                "Timestamp":  datetime.now(timezone.utc),
            },
        ],
    )


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    results = {}

    for team, daily_limit in TEAMS.items():
        try:
            tokens_used = _get_today_token_sum(team)
            pct = (tokens_used / daily_limit * 100.0) if daily_limit > 0 else 0.0

            _publish_quota_pct(team, pct)
            _publish_tokens_used(team, tokens_used, daily_limit)

            log.info(json.dumps({
                "team":        team,
                "tokens_used": tokens_used,
                "daily_limit": daily_limit,
                "quota_pct":   round(pct, 2),
                "status":      "published",
            }))
            results[team] = {"tokens_used": tokens_used, "pct": round(pct, 2)}

        except Exception as exc:
            log.error(json.dumps({
                "team":  team,
                "error": str(exc),
            }))
            results[team] = {"error": str(exc)}

    return {
        "statusCode": 200,
        "body": json.dumps(results),
    }
