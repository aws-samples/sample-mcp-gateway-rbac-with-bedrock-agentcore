# LiteLLM — Comprehensive Research for TAM Education

> **Purpose**: Deep reference for Phyu Phyu (TAM) to understand LiteLLM thoroughly enough to advise customers and compare against Bifrost (Tal's focus), serverless approaches, and agentgateway.
>
> **Last Updated**: July 2026

---

## 1. What is LiteLLM?

**LiteLLM** is an open-source Python SDK and self-hosted AI Gateway (proxy server) that provides a single, OpenAI-compatible interface for calling 100+ LLM providers. Instead of learning different APIs for each provider, you use one interface that connects to over 140 LLM services and 2,500+ models.

| Attribute | Detail |
|-----------|--------|
| **Built by** | BerriAI (Y Combinator-backed startup) |
| **Founded** | 2023 |
| **GitHub** | [github.com/BerriAI/litellm](https://github.com/BerriAI/litellm) |
| **Stars** | ~34K+ (as of mid-2026, up from 18K in early 2025) |
| **Monthly PyPI downloads** | 95+ million |
| **Language** | Python |
| **License** | MIT (core) + Enterprise license (advanced features) |

**Problem it solves**: Enterprises using multiple LLM providers (Bedrock, OpenAI, Anthropic, Vertex AI, Azure) face N different SDKs, N auth flows, N billing systems, and no unified cost governance. LiteLLM acts as a "universal translator" — one API format, one cost tracking system, one access control layer.

**Sources**: [YC Company Page](https://www.ycombinator.com/companies/litellm), [GitHub README](https://github.com/BerriAI/litellm), [a2a-mcp.org](https://a2a-mcp.org/blog/what-is-litellm)

---

## 2. Architecture — How It Works

LiteLLM is a **Python proxy server built on FastAPI** that sits between your applications and LLM providers.

### Request Flow (from official docs)

```
Client App → [Virtual Key Check] → [Rate Limiting] → [Router (LB/Fallback)] → [litellm SDK] → Provider API
                  ↓                       ↓                                              ↓
            Redis/In-Memory         Redis counters                              Response returned
                  ↓                       ↓                                              ↓
            PostgreSQL DB          TPM/RPM tracking                        [Post-Processing: Logging, Spend Update]
```

**Detailed flow:**
1. **User sends request** to proxy (`/chat/completions` endpoint)
2. **Virtual Key validation** — checked against Redis cache first, then PostgreSQL if cache miss
3. **Rate limiting** — `MaxParallelRequestsHandler` checks RPM/TPM for: Global → Key → User → Team
4. **Router** — handles load balancing, fallbacks, retries across model deployments
5. **`litellm.completion()`** — translates to provider-specific format (SigV4 for Bedrock, Bearer token for OpenAI, etc.)
6. **Post-request** (async): logging to external services, spend tracking to DB, rate limit counter updates

### Infrastructure Requirements

| Component | Purpose | AWS Service |
|-----------|---------|-------------|
| **Container host** | Run LiteLLM proxy | ECS Fargate or EKS |
| **PostgreSQL** | Virtual keys, spend tracking, team/user config | Amazon RDS |
| **Redis** | Caching, rate limit counters, prompt cache | Amazon ElastiCache |
| **Load Balancer** | Traffic distribution, TLS termination | ALB |
| **Secrets** | API keys for external providers | Secrets Manager |

**Key architecture fact**: DB transactions are NOT tied to request lifecycle. The key validation read hits cache first; all other DB writes are async background tasks. This keeps latency low.

**Source**: [docs.litellm.ai/docs/proxy/architecture](https://docs.litellm.ai/docs/proxy/architecture)

---

## 3. Key Features

| Feature | Description |
|---------|-------------|
| **Unified OpenAI-compatible API** | One format for all providers — apps don't change when you switch models |
| **140+ providers** | OpenAI, Anthropic, Bedrock, Vertex AI, Azure, Mistral, Cohere, Ollama, vLLM, NVIDIA NIM, etc. |
| **Virtual Keys** | Issue internal API keys with per-key budgets, rate limits, model access restrictions |
| **Budget Enforcement** | Per-key, per-user, per-team spend limits with auto-block at threshold |
| **Load Balancing** | Distribute across multiple deployments of same model (e.g., multiple Bedrock regions) |
| **Fallback/Retry** | Auto-failover to backup provider on errors (e.g., Claude → GPT-4 on 429) |
| **Caching** | In-memory, Redis, and semantic caching to reduce costs on repeated queries |
| **Rate Limiting** | RPM/TPM limits at global, key, user, and team levels |
| **Cost Tracking** | Automatic spend calculation per request with model cost map |
| **Guardrails integration** | Bedrock Guardrails, custom content moderation |
| **Logging/Observability** | Integrates with LangFuse, MLflow, Lunary, Datadog, Prometheus |
| **Streaming support** | Full SSE streaming pass-through |

---

## 4. Deployment on AWS — Official Reference Architecture

AWS published an **official reference architecture** using LiteLLM as the core gateway component:

> **"Guidance for Multi-Provider Generative AI Gateway on AWS"**
> [docs.aws.amazon.com/solutions/multi-provider-generative-ai-gateway-on-aws](https://docs.aws.amazon.com/solutions/multi-provider-generative-ai-gateway-on-aws/)

### Architecture Components

```
┌─────────────────────────────────────────────────────────────────────┐
│  Tenants / Client Applications                                       │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
         Route 53 / CloudFront
                  │
              AWS WAF  ←── Protects against web exploits & bots
                  │
     Application Load Balancer (ALB)  ←── TLS via ACM
                  │
    ┌─────────────┴─────────────┐
    │  ECS Fargate / EKS Pods    │  ←── LiteLLM containers + API Middleware
    │  (from ECR images)         │
    └─────────────┬─────────────┘
                  │
    ┌─────────────┼─────────────────────────┐
    │             │                         │
Amazon Bedrock   External Providers    SageMaker AI
(+ Nova, Guardrails,  (OpenAI, Anthropic,
 Prompt Caching)       Vertex AI)
    │
    └── ElastiCache (Redis) ── RDS (PostgreSQL) ── Secrets Manager ── S3 (Logs)
```

### Key Points from the AWS Guidance

1. **WAF in front** — protects the gateway from common exploits
2. **ECS or EKS** — your choice of container orchestration
3. **API/Middleware layer** — custom layer that integrates natively with Bedrock for features not in LiteLLM OSS
4. **ElastiCache** — multi-tenant settings distribution + prompt caching
5. **RDS** — persistence of virtual keys and configuration
6. **S3** — application logs for audit and analysis
7. **Deployable via CDK or Terraform**

### Deployment Steps (High-Level)

1. Clone the [GitHub sample code](https://github.com/aws-samples/bedrock-litellm)
2. Configure `cdk.json` or Terraform variables (VPC, region, model access)
3. Deploy infrastructure (RDS, ElastiCache, ECS/EKS cluster, ALB, WAF)
4. Build and push container images to ECR
5. Deploy LiteLLM + middleware containers
6. Configure model access in Bedrock console
7. Set up external providers via LiteLLM Admin UI
8. Configure Okta/OAuth 2.0 for authentication

**Source**: [AWS Blog — Streamline AI Operations](https://aws.amazon.com/blogs/machine-learning/streamline-ai-operations-with-the-multi-provider-generative-ai-gateway-reference-architecture/), [community.aws](https://community.aws/content/2e0kU51KbOA2ID63FJgfpud07vz/introducing-the-aws-guidance-for-multi-provider-llm-access)

---

## 5. Configuration — Example config.yaml for Bedrock

```yaml
# config.yaml — LiteLLM Proxy with AWS Bedrock
model_list:
  # Claude 4 Sonnet on Bedrock (cross-region inference)
  - model_name: claude-sonnet
    litellm_params:
      model: bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0
      aws_access_key_id: os.environ/AWS_ACCESS_KEY_ID
      aws_secret_access_key: os.environ/AWS_SECRET_ACCESS_KEY
      aws_region_name: us-east-1

  # Claude Haiku (fast, cheap)
  - model_name: claude-haiku
    litellm_params:
      model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
      aws_region_name: us-west-2

  # Amazon Nova
  - model_name: nova-pro
    litellm_params:
      model: bedrock/amazon.nova-pro-v1:0
      aws_region_name: us-east-1

  # Fallback to OpenAI
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY

# Router settings
router_settings:
  routing_strategy: least-busy  # or: simple-shuffle, latency-based-routing
  num_retries: 3
  timeout: 60
  allowed_fails: 2

litellm_settings:
  drop_params: true          # Drop unsupported params silently
  set_verbose: false
  cache: true
  cache_params:
    type: redis
    host: os.environ/REDIS_HOST
    port: 6379

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL   # PostgreSQL connection string
  alerting:
    - slack
```

### Virtual Keys & Team Budgets (via API)

```bash
# Create a team with monthly budget
curl -X POST 'http://localhost:4000/team/new' \
  -H 'Authorization: Bearer sk-master-key' \
  -d '{
    "team_alias": "product-team",
    "max_budget": 500.00,
    "budget_duration": "1mo",
    "models": ["claude-sonnet", "claude-haiku"]
  }'

# Generate a virtual key for that team
curl -X POST 'http://localhost:4000/key/generate' \
  -H 'Authorization: Bearer sk-master-key' \
  -d '{
    "team_id": "team-xyz-123",
    "max_budget": 100.00,
    "budget_duration": "1mo",
    "models": ["claude-sonnet"],
    "rpm_limit": 60,
    "tpm_limit": 100000
  }'
```

---

## 6. Budget Enforcement — How It Works

This is one of LiteLLM's strongest value propositions vs. native cloud billing.

### Mechanism

1. **Every request** passes through virtual key validation
2. **Pre-call check**: Current spend (from Redis cache or DB) is compared against `max_budget`
3. **If over budget**: Immediately returns **HTTP 429** with `BudgetExceededError`
4. **Post-call**: Spend is calculated using token count × model cost map, then written to PostgreSQL asynchronously
5. **Budget resets**: Configurable duration (`1d`, `1mo`, `28d`, etc.) with automatic reset

### Budget Hierarchy

```
Organization Budget ($10,000/mo)
  └── Team Budget ($2,000/mo)
       └── Key Budget ($500/mo)
            └── Tag Budget (project-level tracking)
```

### Why This Matters vs. CloudWatch

| Aspect | LiteLLM Budget | CloudWatch + Billing Alarms |
|--------|---------------|---------------------------|
| **Enforcement latency** | Real-time (pre-call check) | 24+ hour delay |
| **Blocking** | Hard block at threshold (429) | Alert only (no auto-block) |
| **Granularity** | Per-key, per-user, per-team, per-tag | Per-account or per-model |
| **Reset frequency** | Configurable (daily, monthly, custom) | Monthly billing cycle |
| **Cost attribution** | Instant per-request | After billing processing |

### Caveats

- Redis spend counters can inflate over time in multi-pod deployments (known issue [#30460](https://github.com/BerriAI/litellm/issues/30734))
- Cost calculations depend on accurate model cost map — custom/fine-tuned models may need manual pricing
- Streaming requests calculate cost after completion (not truly "pre-call" for the full amount)

**Source**: [docs.litellm.ai/docs/proxy/cost_tracking](https://docs.litellm.ai/docs/proxy/cost_tracking), [docs.litellm.ai/docs/proxy/team_budgets](https://docs.litellm.ai/docs/proxy/team_budgets)

---

## 7. Dashboard / Admin UI

LiteLLM ships with a built-in web UI at `https://your-proxy/ui`:

### Admin Capabilities
- **Usage Tab**: Spend by team, key, user, model, tag — with date range filters
- **Virtual Keys Management**: Create, revoke, set budgets
- **Team Management**: Create teams, assign admins, set model access
- **Model Management**: Add/remove models, configure fallbacks
- **Real-time logs**: Request/response logs with token counts and costs
- **Alerting**: Configure Slack/webhook alerts for budget thresholds

### User Self-Service

Users can query their own spend via API:
```bash
# Get user info (spend, keys, teams)
curl -X GET 'http://localhost:4000/user/info?user_id=jane_smith' \
  -H 'Authorization: Bearer sk-user-key'

# Daily activity breakdown
curl -X GET 'http://localhost:4000/user/daily/activity?start_date=2026-03-20&end_date=2026-03-27' \
  -H 'Authorization: Bearer sk-user-key'
```

### Access Control for Spend Endpoints

| Caller Role | `/spend/keys` | `/spend/users` |
|-------------|--------------|----------------|
| proxy_admin | All keys | All users |
| internal_user | Own keys only | Own row only |
| Non-admin (no user_id) | Empty `[]` | Empty `[]` |

---

## 8. AWS Bedrock Integration — Deep Dive

### How LiteLLM Connects to Bedrock

LiteLLM uses **boto3** under the hood, which means it supports all standard AWS credential methods:
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- IAM instance roles (EC2/ECS task roles — **recommended for AWS deployments**)
- `aws_role_name` for cross-account AssumeRole
- AWS SSO profiles
- Web identity tokens (for EKS IRSA)

**Authentication is SigV4** — boto3 handles the signing automatically. No special configuration needed beyond valid credentials with `bedrock:InvokeModel` permissions.

### Production Config (IAM Role-based)

```yaml
# Best practice: Use ECS Task Role — no keys in config
model_list:
  - model_name: claude-sonnet
    litellm_params:
      model: bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0
      aws_region_name: us-east-1
      # No keys needed — uses ECS Task Role automatically

  - model_name: claude-sonnet-eu
    litellm_params:
      model: bedrock/eu.anthropic.claude-sonnet-4-20250514-v1:0
      aws_region_name: eu-west-1
      aws_role_name: arn:aws:iam::222233334444:role/BedrockCrossRegionRole
```

### Supported Bedrock Features
- All Bedrock models (Anthropic, Meta, Deepseek, Mistral, Amazon Nova)
- Cross-region inference profiles (`us.`, `eu.` prefixes)
- Bedrock Guardrails integration
- Bedrock prompt caching
- Bedrock Realtime API (Nova Sonic)
- Function calling / Tool use
- Request metadata for Bedrock cost attribution

**Source**: [docs.litellm.ai/docs/providers/bedrock](https://docs.litellm.ai/docs/providers/bedrock)

---

## 9. The March 2026 Supply Chain Attack

### What Happened

On **March 24, 2026**, threat group **TeamPCP** published two malicious versions of LiteLLM to PyPI:
- **litellm 1.82.7** — Malicious payload injected into `proxy_server.py`
- **litellm 1.82.8** — More dangerous: used a `.pth` file that executes on Python interpreter startup

### Attack Chain

1. **March 19**: TeamPCP compromised Trivy (Aqua Security's scanner) via stolen credentials
2. **March 20-22**: Worm spread through npm packages, Kubernetes environments
3. **March 23**: Reached Checkmarx GitHub Actions
4. **March 24**: Compromised a BerriAI maintainer's credentials → published malicious LiteLLM versions
5. **March 24 ~14:00 UTC**: PyPI quarantined the entire `litellm` project

### What the Malware Did

1. **Collected**: Environment variables, SSH keys, cloud credentials, Kubernetes tokens, Docker configs, shell history, database credentials, CI/CD secrets
2. **Encrypted**: AES-256 + RSA-4096 hybrid scheme
3. **Exfiltrated** to `models.litellm[.]cloud`
4. **Installed persistence**: `~/.config/sysmon/sysmon.py` + systemd service
5. **Beaconed** for follow-on payloads from `checkmarx[.]zone`
6. **Spread to Kubernetes**: Created privileged pods when service-account tokens were available

### Additional Damage

The attacker also:
- Closed public security disclosures
- Defaced 15 org repositories
- Wiped 182 personal repos
- Made **70 private BerriAI repositories public**

### Impact & Implications for Enterprise Customers

| Concern | Reality |
|---------|---------|
| **Scope** | 95M+ monthly downloads — potentially massive blast radius |
| **Detection window** | ~3.5 hours before PyPI quarantine |
| **Recovery** | Full credential rotation required for affected systems |
| **Trust** | PyPI quarantined the ENTIRE package (all versions) temporarily |

### What This Means for TAM Conversations

- **NOT a vulnerability in LiteLLM's code** — it was a supply chain compromise of the distribution channel
- **Affects any PyPI-based deployment** — containerized deployments with pinned versions were safer
- **Mitigations**: Pin exact versions, use container images from ECR (AWS reference arch does this), run supply-chain firewalls
- **The AWS reference architecture builds images during deployment** → less vulnerable than `pip install litellm`

**Sources**: [Datadog Security Labs](https://securitylabs.datadoghq.com/articles/litellm-compromised-pypi-teampcp-supply-chain-campaign/), [JFrog Research](https://research.jfrog.com/post/litellm-compromised-teampcp/), [Trend Micro](https://www.trendmicro.com/en_us/research/26/c/inside-litellm-supply-chain-compromise.html), [HuggingFace Blog](https://huggingface.co/blog/davidberenstein1957/litellm-supply-chain-attack-2026)

---

## 10. Free (Open-Source) vs Enterprise

### Open-Source (Free)

Everything needed for a functional gateway:
- OpenAI-compatible proxy server
- Virtual keys with budgets
- Spend tracking (PostgreSQL)
- Load balancing, fallbacks, retries
- Caching (Redis)
- Rate limiting (RPM/TPM)
- Request/response logging
- Basic Admin UI
- SSO for up to 5 users

### Enterprise License (Paid)

For teams with 100+ users or 10+ production AI use-cases:

| Feature | Description |
|---------|-------------|
| **SSO/OIDC** | Full SSO beyond 5 users (Okta, Entra, etc.) |
| **Audit Logs** | Detailed audit trail for compliance |
| **Fine-grained RBAC** | Organization → Team → Key hierarchy |
| **IP Address Tracking** | Per-request IP logging |
| **Advanced Rate Limiting** | Model-level, team-level granular limits |
| **Tag-based Budgets** | Track spend by project/department tags |
| **PII Masking** | Mask sensitive data in logs |
| **Custom Branding** | White-label admin UI |
| **Priority Support** | Dedicated support channel |
| **Guardrails (Advanced)** | Content moderation integration |
| **Admin Delegation** | Team admins manage their own keys |

### Pricing

- **Self-hosted OSS**: $0 (you manage infra)
- **Enterprise License**: Contact sales — estimated $1,500–$5,000+/mo depending on scale
- **7-day free trial** available
- SSO free for ≤5 users, then enterprise license required

**Source**: [docs.litellm.ai/docs/enterprise](https://docs.litellm.ai/docs/enterprise)

---

## 11. Comparison: LiteLLM vs Bifrost

| Dimension | LiteLLM | Bifrost (Maxim AI) |
|-----------|---------|-------------------|
| **Language** | Python (FastAPI) | Go (goroutines) |
| **Overhead at 5K RPS** | ~40ms per request | ~11µs per request |
| **Provider count** | 140+ providers, 2500+ models | 20+ providers, 1000+ models |
| **Community** | 34K+ GitHub stars, massive adoption | Newer, smaller community |
| **AWS endorsement** | ✅ Official reference architecture | ❌ None |
| **Virtual keys** | ✅ Full budget system | ✅ More granular governance |
| **MCP Gateway** | ❌ Not native | ✅ Native MCP client + server |
| **SSO/RBAC** | Enterprise only | Built-in |
| **Content guardrails** | Via Bedrock Guardrails integration | Native (Bedrock, Azure, custom) |
| **Secrets detection** | ❌ | ✅ Built-in |
| **Semantic caching** | ✅ (with Redis config) | ✅ (native) |
| **Open source** | ✅ MIT | ✅ |
| **Supply chain incident** | ⚠️ March 2026 PyPI compromise | None known |
| **Maturity** | 3+ years, battle-tested | ~1 year |
| **Python GIL** | ⚠️ Concurrency bottleneck at scale | N/A (Go) |

### When to recommend each

- **LiteLLM**: Widest provider coverage, AWS-endorsed path, massive community, well-understood trade-offs, existing tooling/integrations
- **Bifrost**: Performance-critical workloads (high RPS), MCP-heavy agentic architectures, teams hitting Python GIL limits, organizations that need native governance without enterprise license

**Source**: [getmaxim.ai comparison](https://www.getmaxim.ai/articles/litellm-vs-bifrost-feature-by-feature-comparison/), [Bifrost benchmarks](https://www.getmaxim.ai/bifrost/resources/benchmarks)

---

## 12. Comparison: LiteLLM vs API Gateway + Lambda (Serverless)

| Dimension | LiteLLM (ECS/EKS) | API Gateway + Lambda |
|-----------|-------------------|---------------------|
| **Always-on cost** | ~$200-500/mo minimum (ECS + RDS + Redis) | Pay-per-request ($0 at idle) |
| **Cold starts** | None (always running) | Lambda cold start (100-500ms) |
| **Provider translation** | Built-in for 140+ providers | Must code each provider mapping |
| **Budget enforcement** | Built-in, real-time | Must build custom (DynamoDB + logic) |
| **Load balancing** | Built-in router | Must implement in Lambda code |
| **Operational overhead** | Medium (manage ECS, RDS, Redis) | Low (serverless = less ops) |
| **Scaling** | Horizontal (add ECS tasks) | Automatic (Lambda scales instantly) |
| **Max concurrency** | Limited by ECS task count | Limited by Lambda concurrency (1000 default) |
| **Streaming** | Full SSE support | API Gateway WebSocket or Function URL needed |
| **Vendor lock-in** | Low (portable container) | Higher (AWS-specific) |
| **Time to implement** | Hours (deploy reference arch) | Days/weeks (custom build) |

### When to use Serverless approach

- Low/sporadic traffic (cost-sensitive, bursty workloads)
- Single provider (e.g., Bedrock-only) — no multi-provider routing needed
- Team already has API Gateway expertise
- Need maximum cost optimization at low volumes

### When to use LiteLLM

- Multi-provider routing is a requirement
- Need budget enforcement out-of-the-box
- Steady traffic volume (always-on cost is justified)
- Team wants operational simplicity vs. custom coding
- Need the Admin UI for non-technical stakeholders

---

## 13. Comparison: LiteLLM vs agentgateway

These operate at **different layers** and can be complementary:

| Dimension | LiteLLM | agentgateway |
|-----------|---------|-------------|
| **Layer** | Application proxy (L7, OpenAI API format) | Network proxy / infrastructure gateway |
| **Primary use case** | Unify LLM API calls across providers | Govern agent-to-agent, agent-to-tool, agent-to-model traffic |
| **Language** | Python | Go + Rust |
| **Performance** | ~40ms overhead at scale | ~10× throughput vs LiteLLM at same resources |
| **MCP support** | Limited/not native | Core feature (MCP multiplexing, routing) |
| **A2A protocol** | Not supported | Supported |
| **Governance model** | Virtual keys + budgets | Policy engine (AARM, AGT integration) |
| **Maturity** | 3+ years, 34K stars | 1 year, ~2K stars, Linux Foundation / AAIF hosted |
| **Kill switch** | Budget block (429) | Full traffic kill switch for agents |
| **Best for** | Central LLM cost/access control | Agent networking, MCP tool governance, multi-agent orchestration |

### Key Insight for Customers

- **LiteLLM** = "How do I manage which LLM my teams can call, and how much they spend?"
- **agentgateway** = "How do I govern what my AI agents can reach, with what tools, and cut them off if needed?"
- They can coexist: agentgateway in front routing agent traffic, LiteLLM behind it managing LLM API calls.

**Source**: [agentgateway.dev/blog](https://agentgateway.dev/blog/), [Benchmarking blog posts](https://agentgateway.dev/blog/)

---

## 14. Who's Using LiteLLM?

### AWS Endorsement
- **Official AWS Reference Architecture**: "Guidance for Multi-Provider Generative AI Gateway on AWS"
- Listed in AWS Solutions Library
- Deployed via AWS-maintained CDK/Terraform templates
- Featured in AWS ML blog posts

### Known Enterprise Customers (per YC/job listings)

| Company | Use Case |
|---------|----------|
| **NASA** | LLM gateway |
| **Adobe** | Multi-provider AI |
| **Rocket Money** | Internal AI tools |
| **Samsara** | IoT + AI workloads |
| **Lemonade** | Insurance AI |
| **Twilio** | Communications AI |
| **Siemens** | Industrial AI |
| **Stripe** | (Referenced in security reports) |
| **Netflix** | (Referenced in security reports) |

### Community
- Google ADK uses LiteLLM as default gateway option
- Multiple AWS samples reference it ([aws-samples/bedrock-litellm](https://github.com/aws-samples/bedrock-litellm))
- EKS GenAI Starter Kit uses LiteLLM as default AI gateway

**Source**: [workatastartup.com/jobs/90055](https://www.workatastartup.com/jobs/90055), [phoenix.security](https://phoenix.security/teampcp-litellm-supply-chain-compromise-pypi-credential-stealer-kubernetes/)

---

## 15. Limitations

### Performance
- **Python GIL**: Single-threaded execution limits true parallelism. At high RPS (~500+), overhead grows to ~40ms/request vs. Go-based alternatives at 11µs
- **Horizontal scaling required**: Need multiple ECS tasks/pods to handle production load
- **Head-of-line blocking**: Under surge traffic, synchronous provider retries without circuit breakers can cascade failures

### Security
- **March 2026 supply chain attack**: Demonstrated that LiteLLM (as a high-value target with access to all API keys) is an attractive attack surface
- **Centralized credential store**: By design, LiteLLM holds keys to ALL providers — compromise of the proxy = compromise of everything
- **No built-in secrets detection**: Can't detect if users accidentally send credentials in prompts (Enterprise Bifrost feature)

### Operational
- **Always-on infrastructure**: ECS + RDS + ElastiCache must run 24/7 (~$200-500/mo minimum)
- **Database dependency**: PostgreSQL is a hard requirement for production (not optional)
- **Redis counter drift**: Known issue where spend counters inflate in multi-pod deployments with ElastiCache timeouts
- **No native WAF**: Must add AWS WAF separately (the reference architecture does this)
- **No native Guardrails**: Must configure Bedrock Guardrails integration separately

### Ecosystem
- **Enterprise features gated**: SSO beyond 5 users, advanced RBAC, audit logs require paid license
- **No native MCP gateway**: Can't govern agent tool access natively
- **Python dependency chain**: Large dependency tree = larger attack surface

---

## 16. When to Recommend vs. NOT Recommend

### ✅ RECOMMEND LiteLLM When:

| Signal | Why LiteLLM fits |
|--------|-----------------|
| Customer uses **3+ LLM providers** | Core value prop — unified interface |
| Need **budget enforcement** that actually blocks | Real-time 429 vs. CloudWatch's 24hr delay |
| Want **AWS-endorsed** path | Official reference architecture, CDK templates |
| **Platform team** managing AI for many dev teams | Virtual keys, team budgets, admin UI |
| Need to **switch providers quickly** | Apps don't change — just update config |
| **Quick time-to-value** | Deploy in hours, not weeks |
| Existing **Python/OpenAI SDK** codebase | Drop-in compatible |

### ❌ DO NOT RECOMMEND When:

| Signal | Why not | Alternative |
|--------|---------|-------------|
| **Ultra-low latency** requirements (<5ms gateway overhead) | Python GIL bottleneck | Bifrost (Go) |
| **Single provider** (Bedrock only) | Over-engineered for one provider | Direct Bedrock SDK or API Gateway + Lambda |
| **Cost-sensitive with bursty traffic** | Always-on infra cost not justified | Serverless approach |
| **Agentic workloads** needing MCP governance | No native MCP gateway | agentgateway |
| **Regulated industry** needing SOC2/HIPAA audit logs | Requires Enterprise license ($$) | Bifrost or custom solution |
| **Security-paranoid org** post-supply-chain incident | Trust concerns | Self-build or Bifrost |
| **Very high throughput** (>10K RPS sustained) | Need many replicas, Python ceiling | Bifrost or agentgateway |

### Decision Framework (Quick Reference)

```
Q: How many LLM providers?
  → 1 provider → Skip LiteLLM, use native SDK
  → 2+ providers → Continue ↓

Q: Traffic pattern?
  → Bursty/low volume → Consider serverless
  → Steady/high volume → Continue ↓

Q: Need budget enforcement?
  → Yes, real-time blocking → LiteLLM ✅
  → Alerts only are fine → CloudWatch may suffice

Q: Performance requirements?
  → <5ms gateway overhead → Bifrost
  → <50ms acceptable → LiteLLM ✅

Q: MCP/Agent governance needed?
  → Yes → agentgateway (+ LiteLLM behind it if multi-provider)
  → No → LiteLLM alone is fine
```

---

## Quick Reference Card

| Question a Customer Might Ask | Answer |
|-------------------------------|--------|
| "Is LiteLLM endorsed by AWS?" | Yes — official reference architecture in AWS Solutions Library |
| "Is it secure after the PyPI incident?" | The code itself wasn't compromised; it was the distribution channel. Use container images, pin versions. |
| "What does it cost to run?" | $0 for software (OSS) + ~$200-500/mo AWS infra (ECS + RDS + ElastiCache) |
| "How is it better than just using Bedrock directly?" | Unified API across providers, real-time budget enforcement, virtual keys for teams, load balancing/fallback |
| "Can it replace our API Gateway?" | No — it sits behind your API Gateway/ALB. It's an application-layer proxy, not a network gateway. |
| "LiteLLM vs Bifrost?" | LiteLLM = more providers, AWS-endorsed, bigger community. Bifrost = faster (Go), better governance, MCP-native. |
| "What if we only use Bedrock?" | LiteLLM still adds value for budget enforcement and virtual keys, but consider if the overhead is worth it vs. native SDK + custom logic. |

---

*Document prepared for TAM internal use. Not for customer distribution without review.*
