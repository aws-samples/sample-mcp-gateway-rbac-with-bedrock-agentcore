# LiteLLM Gateway — Test Cases

These test cases validate the LiteLLM gateway sitting in front of Amazon Bedrock.
Each case states **what to do**, the **expected result**, and — most importantly —
**what LiteLLM is doing for you** (the capability being proven).

## Environment

- Gateway: `http://localhost:4000` (Docker Compose: LiteLLM + PostgreSQL + Redis)
- Auth to Bedrock: host AWS creds via the `bedrock-static` profile (Option B mount)
- Master key: `sk-demo-master-key`
- Two teams provisioned by `scripts/setup-teams.sh`:

| Team | Virtual key | Allowed models | Team budget | Key budget |
|---|---|---|---|---|
| Alpha | `YOUR_TEAM_ALPHA_VIRTUAL_KEY` | claude-haiku, claude-sonnet | $200/mo | $100/mo |
| Beta  | `YOUR_TEAM_BETA_VIRTUAL_KEY` | claude-haiku only | $50/mo | $25/mo |

Two test surfaces:
- **Chatbox UI** — `chatbox.html` (open in browser; log in as a team, pick a model, chat)
- **API** — `curl` against the endpoints below (good for CI / scripted checks)

> Note: live model responses require valid Bedrock creds. If calls fail with an
> expired-token error, run `./scripts/refresh-aws-creds.sh` and retry.

---

## TC-1 — Health check

**What LiteLLM helps with:** a single operational endpoint to confirm the gateway
and its state store are up, so clients don't need to know about Bedrock at all.

- **Steps (API):**
  ```bash
  curl -s http://localhost:4000/health/readiness
  ```
- **Expected:** `{"status":"healthy","db":"connected"}`, HTTP 200.
- **Pass criteria:** status `healthy` and db `connected`.

---

## TC-2 — Authenticated model call (happy path)

**What LiteLLM helps with:** **unified OpenAI-compatible API** in front of Bedrock.
Clients speak the standard `/chat/completions` shape; LiteLLM translates to Bedrock,
signs the request with AWS credentials, and returns a normalized response with usage.

- **Chatbox:** log in as **Team Alpha** → keep model **Claude Haiku** → send "Hello".
- **Steps (API):**
  ```bash
  curl -s http://localhost:4000/chat/completions \
    -H 'Authorization: Bearer YOUR_TEAM_ALPHA_VIRTUAL_KEY' \
    -H 'Content-Type: application/json' \
    -d '{"model":"claude-haiku","messages":[{"role":"user","content":"Hello"}]}'
  ```
- **Expected:** HTTP 200 with `choices[0].message.content` (a real reply) and a
  `usage` block (`prompt_tokens`, `completion_tokens`, `total_tokens`).
- **Pass criteria:** non-empty assistant reply + usage present.

---

## TC-3 — Model-level access control: ALLOWED

**What LiteLLM helps with:** **authorization (RBAC) per virtual key.** The key itself
carries the allowlist; no client-side enforcement needed.

- **Chatbox:** log in as **Team Beta** → model **Claude Haiku** (badged "✓ Allowed") → send a message.
- **Steps (API):**
  ```bash
  curl -s http://localhost:4000/chat/completions \
    -H 'Authorization: Bearer YOUR_TEAM_BETA_VIRTUAL_KEY' \
    -H 'Content-Type: application/json' \
    -d '{"model":"claude-haiku","messages":[{"role":"user","content":"hi"}]}'
  ```
- **Expected:** HTTP 200, normal reply.
- **Pass criteria:** Beta can use its permitted model.

---

## TC-4 — Model-level access control: DENIED

**What LiteLLM helps with:** **authorization enforced at the gateway, before Bedrock.**
An out-of-scope model is rejected — the request never reaches Bedrock, so no cost is
incurred and no client code decides access.

- **Chatbox:** as **Team Beta**, open the model dropdown, select **Claude Sonnet**
  (badged "✗ Denied"), send a message.
- **Steps (API):**
  ```bash
  curl -s http://localhost:4000/chat/completions \
    -H 'Authorization: Bearer YOUR_TEAM_BETA_VIRTUAL_KEY' \
    -H 'Content-Type: application/json' \
    -d '{"model":"claude-sonnet","messages":[{"role":"user","content":"hi"}]}'
  ```
- **Expected:** HTTP 401 with a message like
  *"key not allowed to access model. This key can only access models=['claude-haiku']. Tried to access claude-sonnet"*.
- **Pass criteria:** request blocked with a clear authorization error; no model output returned.

---

## TC-5 — Budget enforcement (pre-call block)

**What LiteLLM helps with:** **pre-call budget enforcement.** When a key/team hits its
spend cap, LiteLLM blocks the request *before* calling Bedrock (HTTP 429) — real dollars
saved, not just logged after the fact. This is the key differentiator vs. a log-only proxy.

- **Setup:** use a key with a very small budget (create a throwaway key with
  `max_budget` near 0), or exhaust an existing key.
  ```bash
  curl -s -X POST http://localhost:4000/key/generate \
    -H 'Authorization: Bearer sk-demo-master-key' \
    -H 'Content-Type: application/json' \
    -d '{"key_alias":"tc5-tiny-budget","models":["claude-haiku"],"max_budget":0.0000001,"budget_duration":"1mo"}'
  ```
- **Steps:** send one or two `chat/completions` calls with that key until the budget trips.
- **Expected:** once the cap is exceeded, HTTP 429 / budget-exceeded error; the call does
  not reach Bedrock.
- **Pass criteria:** request rejected on budget, not model error.

---

## TC-6 — Cost attribution (per-key spend)

**What LiteLLM helps with:** **real-time cost attribution.** Spend is tracked per key/team
in PostgreSQL and queryable via API — finance/ops get per-tenant numbers without parsing logs.

- **Chatbox:** the header shows running request count and estimated cost as you chat.
- **Steps (API):**
  ```bash
  curl -s http://localhost:4000/key/info \
    -H 'Authorization: Bearer sk-demo-master-key' \
    -G --data-urlencode 'key=YOUR_TEAM_BETA_VIRTUAL_KEY'
  ```
- **Expected:** JSON including the key's `spend` and `max_budget`.
- **Pass criteria:** `spend` increases after TC-2/TC-3 calls and is attributed to the right key.

---

## TC-7 — Tenant lifecycle: instant provisioning

**What LiteLLM helps with:** **self-service tenant provisioning.** A new team + key is one
API call — no redeploy, no code change.

- **Steps (API):**
  ```bash
  curl -s -X POST http://localhost:4000/team/new \
    -H 'Authorization: Bearer sk-demo-master-key' \
    -H 'Content-Type: application/json' \
    -d '{"team_alias":"team-gamma","models":["claude-haiku"],"max_budget":30,"budget_duration":"1mo"}'
  ```
  Then `/key/generate` against the returned `team_id`.
- **Expected:** team + key created immediately; the new key can call `claude-haiku` right away.
- **Pass criteria:** new tenant usable within seconds, no restart.

---

## TC-8 — Tenant lifecycle: instant revocation

**What LiteLLM helps with:** **instant credential revocation.** Delete a team/key and its
access dies immediately — no waiting for a deploy or token expiry.

- **Steps (API):**
  ```bash
  # delete the key created in TC-7
  curl -s -X POST http://localhost:4000/key/delete \
    -H 'Authorization: Bearer sk-demo-master-key' \
    -H 'Content-Type: application/json' \
    -d '{"keys":["<the-gamma-key>"]}'
  # then try to use it
  curl -s http://localhost:4000/chat/completions \
    -H 'Authorization: Bearer <the-gamma-key>' \
    -H 'Content-Type: application/json' \
    -d '{"model":"claude-haiku","messages":[{"role":"user","content":"hi"}]}'
  ```
- **Expected:** the deleted key is rejected (auth error).
- **Pass criteria:** revoked key can no longer call any model.

---

## TC-9 — Response caching

**What LiteLLM helps with:** **response caching (Redis).** Identical requests can be served
from cache, cutting latency and Bedrock cost.

- **Steps (API):** send the same request twice with the same key:
  ```bash
  for i in 1 2; do
    time curl -s http://localhost:4000/chat/completions \
      -H 'Authorization: Bearer YOUR_TEAM_ALPHA_VIRTUAL_KEY' \
      -H 'Content-Type: application/json' \
      -d '{"model":"claude-haiku","messages":[{"role":"user","content":"cache test 123"}]}' > /dev/null
  done
  ```
- **Expected:** the second call returns faster; cache-related fields appear in usage on a hit.
- **Pass criteria:** repeat request measurably faster / served from cache.

---

## TC-10 — Centralized observability (Admin UI)

**What LiteLLM helps with:** **centralized observability** for the platform team — teams,
keys, spend, and request logs in one dashboard, no engineering ticket to inspect usage.

- **Steps:** open `http://localhost:4000/ui`, log in with the master key.
- **Expected:** Teams, Keys, and Usage/Logs populated; spend from earlier test cases visible.
- **Pass criteria:** admin can see per-team/key usage and logs centrally.

---

## Capability summary — what LiteLLM is helping with

| Capability | Proven by | Without LiteLLM you'd have to… |
|---|---|---|
| Unified OpenAI-compatible API over Bedrock | TC-2 | Hand-write Bedrock SigV4 + payload mapping in every client |
| Authentication via virtual keys | TC-2, TC-3, TC-8 | Build and store your own key system |
| Authorization / model RBAC | TC-3, TC-4 | Enforce per-team model rules in app code (redeploy to change) |
| Pre-call budget enforcement | TC-5 | Only detect overspend after the fact in logs |
| Real-time cost attribution | TC-6 | Parse CloudWatch logs / build cost tooling |
| Self-service tenant provisioning | TC-7 | Redeploy to add a team |
| Instant revocation | TC-8 | Redeploy to remove access |
| Caching | TC-9 | Add your own cache layer |
| Centralized observability | TC-10 | Stitch dashboards from logs yourself |

*(Capability-to-demo mapping mirrors `DEMO-CHEATSHEET.md`.)*

---

# Test Execution Report

**Run date:** 2026-09-02 ~13:46 UTC
**Environment:** local Docker Compose (LiteLLM + PostgreSQL + Redis); Bedrock auth via `bedrock-static` profile (refreshed at start of run)
**Gateway:** `http://localhost:4000` — healthy, `db: connected`

| Test | Capability | Result | Evidence |
|---|---|---|---|
| TC-1 | Health endpoint | ✅ PASS | `/health/readiness` → `{"status":"healthy","db":"connected"}` |
| TC-2 | Unified API over Bedrock | ✅ PASS | master key + `claude-haiku` → real reply + usage block |
| TC-3 | RBAC allow | ✅ PASS | Team Beta → `claude-haiku` → normal reply |
| TC-4 | RBAC deny (pre-Bedrock) | ✅ PASS | Team Beta → `claude-sonnet` → HTTP 401 "can only access models=['claude-haiku']" |
| TC-5 | Pre-call budget block | ✅ PASS | tiny-budget key: call 2 → HTTP 429 `budget_exceeded` (Current cost 6.38e-05 > Max 1e-07) |
| TC-6 | Per-key cost attribution | ✅ PASS | Beta key `spend` 5.39e-05 → 1.155e-04 after a call (async flush ~15s) |
| TC-7 | Instant provisioning | ✅ PASS | new team-gamma-test + key created via API, worked immediately |
| TC-8 | Instant revocation | ✅ PASS | deleted key → HTTP 401 `token_not_found_in_db` on next call |
| TC-9 | Response caching (Redis) | ✅ PASS | identical request: call 1 = 1.18s (Bedrock), call 2 = 0.04s (cache), same content |
| TC-10 | Centralized observability (UI) | ⏳ MANUAL | verify visually at `http://localhost:4000/ui` (master key) |

**Summary:** 9/9 automated cases PASS. TC-10 is a manual UI check.

**Notes / observations:**
- **Cost attribution is asynchronous.** Spend is batched to PostgreSQL, so `/key/info`
  can lag a call by ~10–15s. Not a bug; account for it in any automated assertion.
- **Budget enforcement is pre-call.** The 429 is returned before the request reaches
  Bedrock, so an over-budget call incurs no model cost.
- **Caching returns identical content and usage** on a hit; the ~30x latency drop
  (1.18s → 0.04s) confirms Redis is serving repeats.
- **Test artifacts cleaned up:** the TC-5 tiny-budget key, the TC-7/TC-8 gamma test
  team and key, and temp response files were all deleted after the run.
- **Cred expiry:** the run used creds valid until 14:05 UTC. For a later re-run,
  execute `./scripts/refresh-aws-creds.sh` first.
