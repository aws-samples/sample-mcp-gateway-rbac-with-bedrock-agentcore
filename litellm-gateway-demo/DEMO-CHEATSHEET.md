# Demo 3 Cheatsheet — What to Say and Why LiteLLM

## Demo 2 vs Demo 3 (Quick Reference)

| | Demo 2 (Custom Lambda) | Demo 3 (LiteLLM) |
|---|---|---|
| **What it is** | You wrote a proxy | You deployed a product |
| **Model access control** | ✅ Both do this | ✅ Both do this |
| **Budget enforcement** | ❌ Logs only, request still goes through | ✅ Blocks at gateway, $0 spent |
| **Add a new team** | Redeploy Lambda (edit env vars, wait) | API call, instant |
| **Remove a team** | Redeploy Lambda | API call, keys die immediately |
| **Spend visibility** | Parse CloudWatch Logs Insights | API call or built-in dashboard |
| **Who manages it** | Developer (code change needed) | Platform team (no code) |
| **Multi-provider** | Bedrock only (hardcoded) | 140+ providers via config |
| **Infra cost** | ~$7/mo (serverless) | ~$82/mo (ECS + RDS + Redis) |
| **Lines of code you maintain** | ~250 (Lambda + CloudFormation) | 0 (config only) |

---

## LLM Gateway Properties in Each Demo Step

| Step | Demo Action | Gateway Property | What you say |
|---|---|---|---|
| 1 | Teams created via API | **Self-service tenant provisioning** | "New team joins? 30 seconds. Not a sprint." |
| 2 | Key generated instantly | **Virtual key management** | "One API call — no deploy, no code." |
| 3 | HTTP 429 budget block | **Pre-call budget enforcement** | "Budget hit → request never reaches Bedrock. Zero dollars wasted." |
| 4 | Spend returned as JSON | **Real-time cost attribution** | "Finance wants spend data? One API call. No log parsing." |
| 5 | Haiku ✅, Sonnet ❌ | **Model-level access control** | "Same RBAC story — just config instead of code." |
| 6 | Admin sees all teams | **Centralized observability** | "Open the dashboard, show it to your VP." |
| 7 | Deleted team key rejected | **Instant credential revocation** | "Employee leaves? Delete team, keys die instantly." |
| 8 | Open /ui | **Platform team interface** | "This is what ops uses day-to-day. No engineering tickets." |

---

## When to Show Which Demo

**Show Demo 2 when:**
- Customer has 2-3 teams, simple needs
- Cost is the priority (~$7/mo vs ~$82/mo)
- They're Bedrock-only, no multi-provider plans
- They want to understand the pattern (educational)

**Show Demo 3 (LiteLLM) when:**
- Customer has 10+ teams or growing fast
- They need real budget blocking (not just logging)
- Platform team needs self-service (no engineering tickets for access changes)
- They use multiple providers (Bedrock + OpenAI + Azure)
- They ask "what does AWS recommend?" (official reference architecture)

---

## The Closing Line

"Demo 2 showed you can build governance yourself — it's cheap and simple. Demo 3 shows you don't have to build it — it's config-driven, AWS-endorsed, and your platform team can manage it without writing code. Pick based on your scale."

---

## Gateway Properties We Show vs Skip

| Gateway Property | In Demo? | Why |
|---|---|---|
| ✅ Authentication (virtual keys) | Yes | Core demo |
| ✅ Authorization (model access) | Yes | Core demo |
| ✅ Budget enforcement (pre-call block) | Yes | Key differentiator vs Demo 2 |
| ✅ Cost attribution (per-key spend) | Yes | Key differentiator vs Demo 2 |
| ✅ Observability (dashboard) | Yes | Key differentiator vs Demo 2 |
| ✅ Tenant lifecycle (create/delete) | Yes | Key differentiator vs Demo 2 |
| ⏭️ Unified API (multi-provider) | Mention only | Bedrock-focused demo |
| ⏭️ Load balancing / fallback | Mention only | Single-region demo |
| ⏭️ Caching | Skip | Low visual impact |
| ⏭️ Rate limiting (RPM) | Skip | Budget blocking is more dramatic |

---

*Keep this open during your demo. The table at the top is your anchor.*
