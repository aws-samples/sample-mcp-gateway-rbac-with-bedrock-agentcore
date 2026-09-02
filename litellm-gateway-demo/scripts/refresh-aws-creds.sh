#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Refresh AWS credentials for the LiteLLM container (Option B)
# ============================================================================
# The LiteLLM container reads ~/.aws (mounted read-only) and uses the
# AWS_PROFILE set in docker-compose (default: bedrock-static).
#
# The container CANNOT run isengardcli / credential_process, so this script
# runs on the HOST, exports fresh credentials from your real profile
# (default: bedrock), and writes them as a STATIC profile the container reads.
#
# Run this whenever Bedrock calls start failing with an expired-token error.
#
# Usage: ./scripts/refresh-aws-creds.sh [SOURCE_PROFILE] [TARGET_PROFILE]
# ============================================================================

SOURCE_PROFILE="${1:-bedrock}"
TARGET_PROFILE="${2:-bedrock-static}"
CRED_FILE="${HOME}/.aws/credentials"

echo "Exporting credentials from profile '${SOURCE_PROFILE}'..."
CREDS_JSON="$(aws configure export-credentials --profile "${SOURCE_PROFILE}")"

AKID="$(echo "${CREDS_JSON}" | python3 -c 'import json,sys;print(json.load(sys.stdin)["AccessKeyId"])')"
SAK="$(echo "${CREDS_JSON}" | python3 -c 'import json,sys;print(json.load(sys.stdin)["SecretAccessKey"])')"
TOKEN="$(echo "${CREDS_JSON}" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("SessionToken",""))')"
EXPIRY="$(echo "${CREDS_JSON}" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("Expiration","(none)"))')"

# Write/replace the target profile in ~/.aws/credentials using the AWS CLI
aws configure set aws_access_key_id     "${AKID}"  --profile "${TARGET_PROFILE}"
aws configure set aws_secret_access_key "${SAK}"   --profile "${TARGET_PROFILE}"
if [ -n "${TOKEN}" ]; then
  aws configure set aws_session_token   "${TOKEN}" --profile "${TARGET_PROFILE}"
fi

echo "✅ Wrote static profile '${TARGET_PROFILE}' to ${CRED_FILE}"
echo "   Expires: ${EXPIRY}"
echo ""
echo "Restarting LiteLLM so it picks up fresh credentials..."
docker compose restart litellm >/dev/null 2>&1 && echo "✅ litellm restarted" || echo "⚠️  Could not restart litellm (is the stack up?)"
