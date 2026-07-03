#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Setup Teams & Virtual Keys for LiteLLM Demo
# ============================================================================
# Run this after docker compose up (or after AWS deployment)
# Creates two teams with different model access and budgets.
#
# Usage: ./scripts/setup-teams.sh [LITELLM_URL]
# ============================================================================

LITELLM_URL="${1:-http://localhost:4000}"
MASTER_KEY="${LITELLM_MASTER_KEY:-sk-demo-master-key}"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  LiteLLM Team Setup                                           ║"
echo "║  URL: $LITELLM_URL                                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Wait for LiteLLM to be ready
echo "⏳ Waiting for LiteLLM to be ready..."
for i in $(seq 1 30); do
  if curl -sf "$LITELLM_URL/health" > /dev/null 2>&1; then
    echo "  ✅ LiteLLM is ready"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "  ❌ LiteLLM not ready after 30s. Is it running?"
    exit 1
  fi
  sleep 1
done
echo ""

# ── Create Team Alpha ──
echo "━━━ Creating Team Alpha (Haiku + Sonnet, $200/mo budget) ━━━"
TEAM_ALPHA=$(curl -sf -X POST "$LITELLM_URL/team/new" \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "team_alias": "team-alpha",
    "models": ["claude-haiku", "claude-sonnet"],
    "max_budget": 200.00,
    "budget_duration": "1mo"
  }')

TEAM_ALPHA_ID=$(echo "$TEAM_ALPHA" | python3 -c "import json,sys; print(json.load(sys.stdin)['team_id'])")
echo "  ✅ Team Alpha created: $TEAM_ALPHA_ID"
echo ""

# ── Create Team Beta ──
echo "━━━ Creating Team Beta (Haiku only, $50/mo budget) ━━━"
TEAM_BETA=$(curl -sf -X POST "$LITELLM_URL/team/new" \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "team_alias": "team-beta",
    "models": ["claude-haiku"],
    "max_budget": 50.00,
    "budget_duration": "1mo"
  }')

TEAM_BETA_ID=$(echo "$TEAM_BETA" | python3 -c "import json,sys; print(json.load(sys.stdin)['team_id'])")
echo "  ✅ Team Beta created: $TEAM_BETA_ID"
echo ""

# ── Generate Virtual Keys ──
echo "━━━ Generating Virtual Keys ━━━"

KEY_ALPHA=$(curl -sf -X POST "$LITELLM_URL/key/generate" \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"team_id\": \"$TEAM_ALPHA_ID\",
    \"key_alias\": \"team-alpha-key\",
    \"max_budget\": 100.00,
    \"budget_duration\": \"1mo\",
    \"models\": [\"claude-haiku\", \"claude-sonnet\"]
  }")

SK_ALPHA=$(echo "$KEY_ALPHA" | python3 -c "import json,sys; print(json.load(sys.stdin)['key'])")
echo "  ✅ Team Alpha key: $SK_ALPHA"

KEY_BETA=$(curl -sf -X POST "$LITELLM_URL/key/generate" \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"team_id\": \"$TEAM_BETA_ID\",
    \"key_alias\": \"team-beta-key\",
    \"max_budget\": 25.00,
    \"budget_duration\": \"1mo\",
    \"models\": [\"claude-haiku\"]
  }")

SK_BETA=$(echo "$KEY_BETA" | python3 -c "import json,sys; print(json.load(sys.stdin)['key'])")
echo "  ✅ Team Beta key:  $SK_BETA"
echo ""

# ── Summary ──
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  ✅ SETUP COMPLETE                                            ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║                                                               ║"
echo "║  Team Alpha:                                                  ║"
echo "║    Models: claude-haiku, claude-sonnet                        ║"
echo "║    Budget: \$200/month (team) | \$100/month (key)              ║"
echo "║    Key:    $SK_ALPHA"
echo "║                                                               ║"
echo "║  Team Beta:                                                   ║"
echo "║    Models: claude-haiku only                                  ║"
echo "║    Budget: \$50/month (team) | \$25/month (key)                ║"
echo "║    Key:    $SK_BETA"
echo "║                                                               ║"
echo "║  Admin UI: $LITELLM_URL/ui                                    ║"
echo "║  Master Key: $MASTER_KEY                                      ║"
echo "║                                                               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Test with:"
echo "  curl $LITELLM_URL/chat/completions \\"
echo "    -H 'Authorization: Bearer $SK_ALPHA' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"model\": \"claude-haiku\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]}'"
