# MCPGatebay 🛸

> **A docking bay for AI tools. They dock, get cleared, and access only what they are authorized for.**

[![AWS](https://img.shields.io/badge/AWS-Bedrock%20AgentCore-FF9900?style=flat&logo=amazon-aws)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
[![Cedar](https://img.shields.io/badge/Policy-Cedar%20RBAC-2ecc71?style=flat)](https://www.cedarpolicy.com/)
[![MCP](https://img.shields.io/badge/Protocol-MCP-6c5ce7?style=flat)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT--0-blue?style=flat)](../LICENSE)

MCPGatebay is a governed gateway that lets developers use AI coding assistants like GitHub Copilot or VS Code against your company's internal APIs — with fine-grained, per-user access control enforced centrally, using your existing corporate identity (Entra ID, Cognito, Okta).

No credentials on developer machines. No bespoke integration per tool. One control point for who can call what.

---

## The analogy

In Star Trek, a **docking bay** is where starships arrive, present their credentials, receive clearance, and are routed to the right section of the station. No ship gets past the bay without authorization. Every approach is logged.

MCPGatebay works the same way. AI tools arrive at the bay, present their identity token, receive clearance from the Cedar policy engine, and are routed to the APIs they are authorized to reach. Engineering crew gets access to the engineering decks. Support crew gets access to the support decks. Nobody crosses without clearance.

---

## What it does

```
Developer (VS Code + Copilot)
        │
        │  OAuth login (corporate identity — Entra ID / Cognito)
        ▼
CloudFront Relay  ──── strips OAuth metadata that breaks Entra
        │
        │  Bearer token + MCP call
        ▼
AgentCore Gateway  ──── validates JWT, reads team claim
        │
        │  Cedar policy check
        ▼
 ✅ Engineering → Products API, Orders API
 ✅ Support     → Customers API, Jira API
 🚫 Cross-team  → denied (default-deny, no exceptions)
        │
        ▼
   Your Internal APIs (Lambda MCP servers)
```

A developer asks Copilot "list the orders for customer X" — Copilot calls the real Orders API through MCPGatebay, gets real data back, and the developer never had direct API access. Every call is logged with the caller's identity.

---

## Two authentication paths

| | Path A: IAM/SigV4 | Path B: OAuth/JWT (Entra ID) |
|---|---|---|
| **How developers authenticate** | AWS credentials + local SigV4 proxy | Native browser login (OAuth popup in IDE) |
| **Identity source for Cedar** | IAM user tags (`group=ReadOnly`) | JWT claims (`team=Engineering`) |
| **Local requirements** | SigV4 proxy process | Nothing — fully remote |
| **One-click deployable** | ✅ `./deploy.sh` | CloudFormation templates provided |
| **Best for** | Internal teams with AWS credentials, quick demos | Enterprise customers with Entra ID, no local install allowed |

Both paths use the same gateway, same Cedar policies, same Lambda MCP tools. Only the authentication layer differs.

---

## Deploy in one command (IAM path)

```bash
git clone https://github.com/aws-samples/sample-mcp-gateway-rbac-with-bedrock-agentcore.git
cd sample-mcp-gateway-rbac-with-bedrock-agentcore/gateway-url-ide-integration-demo
./deploy.sh
```

This creates four Lambda MCP servers (products, orders, customers, jira), an MCP Registry Lambda, an AgentCore Gateway with IAM authorization, Cedar RBAC policies, and two IAM test users. The script outputs the Registry URL, Gateway URL, and IAM credentials.

**Prerequisites:** AWS CLI (configured with admin access), Python 3.9+, jq

---

## Access control matrix

| Tool | Engineering team | Support team |
|------|:---:|:---:|
| Products — list / search / get | ✅ ALLOW | 🚫 DENY |
| Orders — list / get / create | ✅ ALLOW | 🚫 DENY |
| Customers — list / get | 🚫 DENY | ✅ ALLOW |
| Jira — list tickets | 🚫 DENY | ✅ ALLOW |

Cedar uses **default-deny**. Cross-team access is automatically blocked — no explicit forbid rules needed. Policies are declarative, auditable, and version-controlled.

---

## Enterprise IdP (Entra ID / OAuth) path

For customers who need native IDE login without a local proxy — BIS-policy compliance, enterprise Entra ID integration — see the OAuth guides:

- **[OAUTH_DEMO.md](OAUTH_DEMO.md)** — end-to-end OAuth setup with Cognito
- **[ENTRA_ID_OAUTH.md](ENTRA_ID_OAUTH.md)** — complete Entra ID integration guide including the CloudFront relay that fixes the AADSTS9010010 compatibility issue between AgentCore and Entra v2.0

The Entra guide includes:
- App Registration setup and team claim mapping
- CloudFormation template for the cloud-hosted metadata relay (zero per-developer setup)
- AWS support case template for the permanent gateway-level fix
- Troubleshooting checklist for AADSTS9010010, AADSTS50011, AADSTS70011, and AADSTS70003

---

## Why MCPGatebay instead of alternatives

**No credentials on developer machines.** Developers authenticate with their existing corporate identity. No AWS keys, no API secrets, no `.env` files to manage or accidentally commit.

**Per-user, per-team access control.** Permissions follow the person, not the tool. The same gateway enforces different rules for engineering and support automatically based on the identity in the token.

**Works with any MCP-compatible tool.** One gateway serves VS Code, GitHub Copilot CLI, Claude Desktop, and any future MCP client. No bespoke integration per tool.

**Auditable access policies.** Cedar policies are human-readable, version-controlled, and reviewable in a pull request. Security teams can audit exactly who can call what.

**Enterprise identity — no new accounts.** Plugs into your existing Entra ID or Cognito. Developers use the same login they already have.

**Built on AWS managed services.** AgentCore, Lambda, CloudFront, Cedar — fully managed, scales automatically, no infrastructure to operate.

---

## Cost estimate

For 10 developers making 100 tool calls per day:

| Service | Monthly cost |
|---------|-------------|
| AgentCore Gateway (30K requests) | ~$5 |
| Lambda MCP servers (30K invocations) | ~$1 |
| Lambda Registry (minimal) | <$1 |
| CloudFront relay (minimal) | <$1 |
| CloudWatch Logs | ~$1 |
| **Total** | **~$9/month** |

---

## Project structure

```
gateway-url-ide-integration-demo/   ← MCPGatebay
├── deploy.sh                        One-command deploy (IAM path)
├── cleanup.sh                       Tear down all resources
├── OAUTH_DEMO.md                    OAuth/JWT setup with Cognito
├── ENTRA_ID_OAUTH.md                Entra ID integration + relay guide
├── DEMO.md                          Step-by-step demo script
├── VSCODE_SETUP.md                  VS Code configuration details
│
├── infrastructure/cloudformation/
│   ├── oauth-registry-stack.yaml    Cognito User Pool + Registry Lambda
│   └── oauth-metadata-relay-stack.yaml  CloudFront relay for Entra ID
│
├── lambda/mcp-servers/              Lambda functions exposed as MCP tools
│   ├── ecommerce-mcp/               list_customers, get_customer_by_id
│   ├── products-mcp/                list_products, search_products, get_product_by_id
│   ├── orders-mcp/                  list_orders, get_order_by_id, create_order
│   └── jira-mcp/                    list_jira_tickets
│
├── scripts/
│   ├── create-gateway.py            Creates AgentCore Gateway (IAM auth)
│   ├── create-gateway-oauth.py      Creates Gateway (JWT auth)
│   ├── setup-cedar-iam.py           Cedar policies (IAM group tags)
│   └── setup-cedar-oauth.py         Cedar policies (JWT team claims)
│
├── npm-package/customer-gateway-proxy/
│   ├── bin/proxy.py                 Local SigV4 proxy (IAM path)
│   └── bin/oauth-proxy.py           Local OAuth metadata relay (dev/testing)
│
└── vscode-config/
    ├── mcp.json                     VS Code config (IAM path)
    └── mcp-oauth.json               VS Code config (OAuth/Entra path)
```

---

## How Cedar policies work

```cedar
permit(
    principal,
    action == AgentCore::Action::"orders-mcp___list_orders",
    resource == AgentCore::Gateway::"<GATEWAY_ARN>"
)
when {
    principal.hasTag("team") && principal.getTag("team") == "Engineering"
};
```

To change permissions: update a Cedar policy statement. No Lambda redeployment, no code change, no downtime. One permit per action — Cedar evaluates reliably this way on AgentCore.

---

## Security

No credentials or passwords are stored in this repository. IAM access keys are generated at deploy time and printed once. The gateway enforces authentication on every request. Cedar evaluates authorization on every tool call. All decisions are logged to CloudWatch with the caller's identity.

---

## Resources

- [Amazon Bedrock AgentCore Gateway docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
- [Cedar Policy Language](https://www.cedarpolicy.com/)
- [MCP Registry v0.1 specification](https://registry.modelcontextprotocol.io/docs)
- [GitHub Copilot MCP Registry configuration](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-mcp-usage/configure-mcp-registry)
- [AWS Agent Registry (preview)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/registry.html)

---

Licensed under the MIT-0 License. See [LICENSE](../LICENSE).
