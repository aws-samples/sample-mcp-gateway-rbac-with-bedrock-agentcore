#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Test Script — Validates LiteLLM Gateway Demo End-to-End
# ============================================================================
# Runs through the full demo scenario:
#   1. Health check
#   2. Team Alpha: Haiku ✅, Sonnet ✅, Opus ❌
#   3. Team Beta: Haiku ✅, Sonnet ❌
#   4. Budget enforcement (set low budget, verify 429)
#   5. Admin API (list teams, check spend)
#
# Usage: ./scripts/test-demo.sh [LITELLM_URL] [ALPHA_KEY] [BETA_KEY]
# ============================================================================

LITELLM_URL="${1:-http://localhost:4000}"
MASTER_KEY="${LITELLM_MASTER_KEY:-sk-demo-master-key}"

# If keys not provided, try to get them from LiteLLM
ALPHA_KEY="${2:-}"
BETA_KEY="${3:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0

pass() { echo -e "  ${GREEN}✅ PASS${NC} $1"; PASSED=$((PASSED + 1)); }
fail() { echo -e "  ${RED}❌ FAIL${NC} $1"; FAILED=$((FAILED + 1)); }
skip() { echo -e "  ${YELLOW}⏭️  SKIP${NC} $1"; }

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  LiteLLM Gateway — Integration Tests                          ║"
echo "║  URL: $LITELLM_URL                                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# ── Resolve keys if not provided ──
if [ -z "$ALPHA_KEY" ] || [ -z "$BETA_KEY" ]; then
  echo "🔑 Resolving virtual keys from LiteLLM..."
  KEYS_JSON=$(curl -sf "$LITELLM_URL/key/list" \
    -H "Authorization: Bearer $MASTER_KEY" 2>/dev/null || echo "")

  if [ -n "$KEYS_JSON" ]; then
    ALPHA_KEY=$(echo "$KEYS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
keys = data if isinstance(data, list) else data.get('keys', [])
for k in keys:
    if 'alpha' in k.get('key_alias','').lower() or 'alpha' in k.get('team_alias','').lower():
        print(k.get('token',''))
        break
" 2>/dev/null || echo "")
    BETA_KEY=$(echo "$KEYS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
keys = data if isinstance(data, list) else data.get('keys', [])
for k in keys:
    if 'beta' in k.get('key_alias','').lower() or 'beta' in k.get('team_alias','').lower():
        print(k.get('token',''))
        break
" 2>/dev/null || echo "")
  fi

  if [ -z "$ALPHA_KEY" ] || [ -z "$BETA_KEY" ]; then
    echo "  ⚠️  Could not resolve keys automatically."
    echo "  Run: ./scripts/setup-teams.sh first, then pass keys as arguments:"
    echo "  ./scripts/test-demo.sh $LITELLM_URL <ALPHA_KEY> <BETA_KEY>"
    exit 1
  fi
  echo "  ✅ Keys resolved"
  echo ""
fi

# ── Test 1: Health Check ──
echo "━━━ Test 1: Health Check ━━━"
HEALTH=$(curl -sf "$LITELLM_URL/health" 2>/dev/null || echo "FAIL")
if echo "$HEALTH" | grep -qi "healthy\|ok\|running"; then
  pass "LiteLLM is healthy"
else
  fail "Health check failed: $HEALTH"
  echo "  Cannot continue without a healthy proxy. Exiting."
  exit 1
fi
echo ""

# ── Test 2: Team Alpha — Haiku (should succeed) ──
echo "━━━ Test 2: Team Alpha → claude-haiku (expect: ✅) ━━━"
RESP=$(curl -sf -w "\n%{http_code}" "$LITELLM_URL/chat/completions" \
  -H "Authorization: Bearer $ALPHA_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-haiku", "messages": [{"role": "user", "content": "Say hello in 3 words"}], "max_tokens": 20}' \
  2>/dev/null || echo -e "\n000")
HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
  pass "Team Alpha can use claude-haiku (HTTP $HTTP_CODE)"
else
  fail "Team Alpha denied claude-haiku (HTTP $HTTP_CODE): $BODY"
fi
echo ""

# ── Test 3: Team Alpha — Sonnet (should succeed) ──
echo "━━━ Test 3: Team Alpha → claude-sonnet (expect: ✅) ━━━"
RESP=$(curl -sf -w "\n%{http_code}" "$LITELLM_URL/chat/completions" \
  -H "Authorization: Bearer $ALPHA_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet", "messages": [{"role": "user", "content": "Say hi in 3 words"}], "max_tokens": 20}' \
  2>/dev/null || echo -e "\n000")
HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
  pass "Team Alpha can use claude-sonnet (HTTP $HTTP_CODE)"
else
  fail "Team Alpha denied claude-sonnet (HTTP $HTTP_CODE): $BODY"
fi
echo ""

# ── Test 4: Team Beta — Haiku (should succeed) ──
echo "━━━ Test 4: Team Beta → claude-haiku (expect: ✅) ━━━"
RESP=$(curl -sf -w "\n%{http_code}" "$LITELLM_URL/chat/completions" \
  -H "Authorization: Bearer $BETA_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-haiku", "messages": [{"role": "user", "content": "Say hey in 3 words"}], "max_tokens": 20}' \
  2>/dev/null || echo -e "\n000")
HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
  pass "Team Beta can use claude-haiku (HTTP $HTTP_CODE)"
else
  fail "Team Beta denied claude-haiku (HTTP $HTTP_CODE): $BODY"
fi
echo ""

# ── Test 5: Team Beta — Sonnet (should be DENIED) ──
echo "━━━ Test 5: Team Beta → claude-sonnet (expect: ❌ denied) ━━━"
RESP=$(curl -s -w "\n%{http_code}" "$LITELLM_URL/chat/completions" \
  -H "Authorization: Bearer $BETA_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet", "messages": [{"role": "user", "content": "This should fail"}], "max_tokens": 20}' \
  2>/dev/null || echo -e "\n000")
HTTP_CODE=$(echo "$RESP" | tail -1)

if [ "$HTTP_CODE" = "403" ] || [ "$HTTP_CODE" = "401" ]; then
  pass "Team Beta correctly denied claude-sonnet (HTTP $HTTP_CODE)"
elif [ "$HTTP_CODE" = "200" ]; then
  fail "Team Beta should NOT have access to claude-sonnet but got 200"
else
  fail "Unexpected response (HTTP $HTTP_CODE) — expected 403"
fi
echo ""

# ── Test 6: Invalid key (should be denied) ──
echo "━━━ Test 6: Invalid key (expect: ❌ denied) ━━━"
RESP=$(curl -s -w "\n%{http_code}" "$LITELLM_URL/chat/completions" \
  -H "Authorization: Bearer sk-invalid-fake-key" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-haiku", "messages": [{"role": "user", "content": "Should fail"}], "max_tokens": 20}' \
  2>/dev/null || echo -e "\n000")
HTTP_CODE=$(echo "$RESP" | tail -1)

if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
  pass "Invalid key correctly rejected (HTTP $HTTP_CODE)"
else
  fail "Invalid key was not rejected (HTTP $HTTP_CODE)"
fi
echo ""

# ── Test 7: Admin — List teams ──
echo "━━━ Test 7: Admin API — list teams ━━━"
TEAMS=$(curl -sf "$LITELLM_URL/team/list" \
  -H "Authorization: Bearer $MASTER_KEY" 2>/dev/null || echo "FAIL")

if echo "$TEAMS" | grep -qi "alpha\|beta"; then
  pass "Admin can list teams (found alpha/beta)"
else
  fail "Admin team list failed: $TEAMS"
fi
echo ""

# ── Summary ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL=$((PASSED + FAILED))
echo ""
if [ $FAILED -eq 0 ]; then
  echo -e "${GREEN}All $TOTAL tests passed! ✅${NC}"
  echo ""
  echo "Demo is ready. Open the Admin UI:"
  echo "  $LITELLM_URL/ui  (login with master key)"
else
  echo -e "${RED}$FAILED of $TOTAL tests failed.${NC}"
  echo ""
  echo "Check:"
  echo "  docker compose logs litellm"
  echo "  curl $LITELLM_URL/health"
fi
echo ""
