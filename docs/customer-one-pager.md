# AI Governance on AWS — Solution Overview

> Leave-behind for customer meetings. Print or export to PDF.

---

## The Challenge

Enterprises adopting AI coding assistants and LLM APIs face two governance gaps:

1. **No tool-level control** — developers using AI assistants can access any connected tool with no role-based restrictions
2. **No model-level governance** — teams consume expensive LLMs with no access control, cost attribution, or audit trail

---

## Two Patterns, One Goal: Governed AI at Scale

### Pattern 1: Tool-Level RBAC for AI Coding Assistants

**Problem:** "Junior developers shouldn't be able to create production orders through Copilot"

**Solution:** AWS Bedrock AgentCore Gateway + Cedar Policies

```
Developer (VS Code) → AgentCore Gateway → Cedar Policy Check → MCP Tool
```

| Capability | How |
|---|---|
| Role-based tool access | Cedar policies evaluate IAM user tags |
| Per-developer audit | Every tool call logged with IAM principal |
| Declarative policies | "ReadOnly group can list, not create" — no code changes needed |
| IDE-native experience | Works with GitHub Copilot, no developer friction |

**Result:** Same developer, same IDE, different permissions — enforced at the gateway, not the tool.

---

### Pattern 2: Team-Based Model Access & Cost Control

**Problem:** "We're spending $50K/month on LLMs and can't tell which team is using what"

**Solution:** API Gateway + Lambda proxy with team-based governance

```
Application → API Gateway (API Key) → Lambda (Team Check) → Bedrock Model
```

| Capability | How |
|---|---|
| Model access per team | Team Alpha: Haiku+Sonnet. Team Beta: Haiku only. |
| Cost attribution | Structured CloudWatch logs with team, model, token counts |
| Rate limiting | Usage plans per team via API Gateway |
| Gradual rollout | Start teams on cheaper models, promote as needed |

**Result:** Finance gets chargeback data. Engineering gets model access. Security gets audit logs.

---

## Deployment

| | Pattern 1 | Pattern 2 |
|---|---|---|
| **Time to deploy** | ~15 minutes | ~10 minutes |
| **Infrastructure** | CloudFormation + AgentCore CLI | CloudFormation only |
| **AWS services** | AgentCore Gateway, Lambda, IAM | API Gateway, Lambda, Bedrock |
| **Monthly cost (demo)** | ~$6.50 | ~$7 (excl. Bedrock inference) |
| **Preview access?** | Yes (AgentCore) | No — GA services only |

---

## Next Steps

1. **See it live** — we can deploy this in your account in 15 minutes
2. **Map to your org** — identify teams/roles that map to ReadOnly vs FullAccess
3. **Pilot** — start with one team, one model, expand from there

---

## Resources

- GitHub: `aws-samples/sample-mcp-gateway-rbac-with-bedrock-agentcore`
- AWS Bedrock AgentCore: https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html
- Cedar Policy Language: https://www.cedarpolicy.com/
- Model Context Protocol: https://modelcontextprotocol.io/

---

*AWS Solutions Architecture — AI Governance Patterns*
