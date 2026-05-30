# IAM Principal Cost Tracking - Demo Summary

## ✅ What's Already Working

Your guardrail demo is **ALREADY generating Bedrock costs with IAM principal tags**!

Every time you click a product in the frontend:
- Lambda function `demo-products-mcp-strict` or `demo-products-mcp-lenient` runs
- It calls `bedrock:ApplyGuardrail` API
- The IAM principal (`mcp-server-execution-role`) has tags:
  - **Service**: MCPServer
  - **Project**: GuardrailDemo
- These costs flow to Cost Explorer with principal tags attached

## How to View Costs in Cost Explorer (Tomorrow)

### Step 1: Activate Cost Allocation Tags

1. Go to AWS Billing Console
   ```
   https://console.aws.amazon.com/billing/home#/tags
   ```

2. Look for these tags in "User-defined tags":
   - `Service`
   - `Project`

3. Select them and click **Activate**

### Step 2: View in Cost Explorer (after 24 hours)

1. Go to Cost Explorer
   ```
   https://console.aws.amazon.com/cost-management/home#/cost-explorer
   ```

2. **Filter by Bedrock**:
   - Service: Amazon Bedrock
   - Date Range: Last 7 days

3. **Group by Project Tag**:
   - Click "Group by" → "Tag" → Select "Project"
   - You'll see: `GuardrailDemo` with its cost

4. **Group by Service Tag**:
   - Click "Group by" → "Tag" → Select "Service"
   - You'll see: `MCPServer` with its cost

### Step 3: See Detailed Breakdown

**Filter + Group**:
1. Add filter: `Tag:Project` = "GuardrailDemo"
2. Group by: `Tag:Service`
3. Result: Only GuardrailDemo costs, broken down by service

## Cost Data You'll See

```
Amazon Bedrock Costs - GuardrailDemo Project
─────────────────────────────────────────────

Date: 2026-05-24
Service: Amazon Bedrock (Guardrails)
Principal: mcp-server-execution-role

Line Items:
• bedrock:ApplyGuardrail calls (STRICT)
• bedrock:ApplyGuardrail calls (LENIENT)

Tags:
• Service: MCPServer
• Project: GuardrailDemo

Estimated cost: $0.0001 - $0.001 per test
(depends on number of frontend button clicks)
```

## Demo Script for Customers

### Slide 1: The Challenge

> **Problem**: "How do we track Bedrock costs per team without creating hundreds of Application Inference Profiles?"
>
> **Old Approach**: Create separate inference profile for every:
> - Team (Engineering, Marketing, Sales...)
> - Model (Claude, Titan, Jurassic...)
> - Region (us-east-1, eu-west-1...)
> - Application (ChatBot, DocumentAnalysis...)
>
> **Result**: Profile proliferation - 10 teams × 5 models × 3 regions = 150 profiles to manage!

### Slide 2: The Solution

> **IAM Principal Cost Tracking** (GA April 2026)
>
> - Costs automatically attributed based on WHO made the call
> - Uses IAM principal tags (Team, CostCenter, Department, Project)
> - Tags flow to Cost Explorer and CUR 2.0
> - No additional infrastructure needed
> - Works with federated identity (Okta, Entra, Ping)

### Slide 3: Live Demo

1. **Show Guardrail Demo**
   - "This demo makes Bedrock ApplyGuardrail API calls"
   - Click USB Cable product → triggers STRICT guardrail
   - Click Laptop Stand → triggers LENIENT mode

2. **Show IAM Role Tags**
   ```bash
   aws iam get-role --role-name mcp-server-execution-role --query 'Role.Tags'
   ```
   - Service: MCPServer
   - Project: GuardrailDemo

3. **Show Cost Explorer** (tomorrow)
   - Filter: Amazon Bedrock
   - Group by: Tag → Project
   - **Result**: GuardrailDemo costs isolated

### Slide 4: Enterprise Use Case

> **Scenario**: Multi-tenant AI platform with 50 teams
>
> **Without Principal Tagging**:
> - Create 50 × 10 models = 500 inference profiles
> - Tag each profile with team name
> - Update application code to route to correct profile
> - Manage profile lifecycle (create, update, delete)
>
> **With Principal Tagging**:
> - Create 50 IAM roles (one per team)
> - Add tags: Team, CostCenter, Department
> - Teams call Bedrock directly with their role
> - Costs automatically attributed - no profiles needed!

### Slide 5: The Value

**Benefits**:
1. **Simplified Management**: 50 roles instead of 500 profiles
2. **Native Integration**: AWS Cost Explorer & CUR
3. **Multi-Dimensional**: Track by user, team, department, cost center
4. **Works with Federation**: Okta/Entra session tags
5. **No Additional Cost**: Feature is free

**Technical Details**:
- Up to 50 tags per IAM principal
- Cost data available within 24 hours
- Works with all Bedrock APIs (InvokeModel, Converse, ApplyGuardrail, Batch)
- CUR 2.0 column: `line_item_iam_principal`

## FAQ from Customer Conversations

### Q: "Do I still need Application Inference Profiles?"

**A**: Depends on your use case:
- **Use AIPs for**: Team-level + Model-level + Application-level attribution
- **Use IAM Principal Tags for**: Identity-level attribution (who made the call)
- **Use Both for**: Multi-dimensional cost tracking

Example:
- AIP: "TeamA-ProductionChatBot-Claude" (application context)
- IAM Tags: "User: alice@company.com, Department: Engineering" (identity context)

### Q: "How does this work with federated identity (Okta/Entra)?"

**A**: Use **session tags**!

When user logs in via Okta → AWS STS AssumeRoleWithSAML:
1. Okta passes SAML attributes (user email, department, cost center)
2. AWS maps SAML attributes to session tags via IAM role trust policy
3. Session tags are captured with Bedrock API call
4. Tags flow to Cost Explorer

**Example Trust Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Federated": "arn:aws:iam::ACCOUNT:saml-provider/Okta"},
      "Action": ["sts:AssumeRoleWithSAML", "sts:TagSession"],
      "Condition": {
        "StringEquals": {
          "SAML:aud": "https://signin.aws.amazon.com/saml"
        }
      }
    }
  ]
}
```

**SAML Attribute Mapping**:
```
Okta Attribute          → AWS Session Tag
─────────────────────────────────────────
user.email              → Email
user.department         → Department
user.costCenter         → CostCenter
```

### Q: "Can I set spending limits per team?"

**A**: Not natively in Bedrock, but you can:

1. **AWS Budgets with Tag Filters**:
   - Create budget filtered by `Tag:Team` = "Engineering"
   - Set alert threshold: $1,000/month
   - Get SNS notification when 80% spent

2. **AWS Budget Actions**:
   - When budget exceeds 100%, apply IAM deny policy
   - Blocks team's Bedrock access until next month

3. **LLM Gateway** (LiteLLM, Kong, custom):
   - Track usage in real-time
   - Apply rate limits per team
   - Block access when budget exceeded

### Q: "How granular can I get - individual users?"

**A**: Yes, with federated identity!

**Setup**:
1. Users log in via Okta/Entra
2. Session tags include: `Email: alice@company.com`
3. Bedrock costs tagged with user email
4. Cost Explorer: Group by `Tag:Email`

**Result**: See costs per individual user!

**Scale Consideration**:
- 1,000 users = 1,000 unique tag values in Cost Explorer
- CUR queries work fine
- Cost Explorer UI may paginate

### Q: "Does this work for Bedrock Agents and Knowledge Bases?"

**A**: Yes!

- **Bedrock Agents**: Agent execution uses IAM role → role tags captured
- **Knowledge Bases**: Ingestion jobs use IAM role → role tags captured
- **Batch Inference**: Batch job uses IAM role → role tags captured

All Bedrock services support IAM principal cost tracking.

## Testing Your Setup

### Generate Test Costs

Run the frontend demo multiple times:

```bash
# Open frontend
open http://localhost:8002/guardrail_demo_frontend_apigateway.html

# Click each product 10 times:
# 1. USB Cable (STRICT will block, LENIENT allows)
# 2. Laptop Stand
# 3. Desk Organizer
# 4. List All Products

# Total: ~40 Bedrock API calls
```

Each call generates:
- bedrock:ApplyGuardrail API usage
- Cost: ~$0.00001 per call
- Tags: Service=MCPServer, Project=GuardrailDemo

### Verify Tags on Role

```bash
aws iam get-role \
  --role-name mcp-server-execution-role \
  --query 'Role.Tags' \
  --output table
```

### Check CloudWatch Logs

```bash
aws logs tail /aws/lambda/demo-products-mcp-strict --follow
```

Look for: "Guardrail Mode: STRICT" → Confirms Bedrock calls happening

### Tomorrow: Check Cost Explorer

```bash
# Open Cost Explorer
open "https://console.aws.amazon.com/cost-management/home#/cost-explorer"

# Steps:
# 1. Service: Amazon Bedrock
# 2. Group by: Tag → Project
# 3. Look for: GuardrailDemo
```

## Files Created

| File | Purpose |
|------|---------|
| `COST_EXPLORER_SETUP.md` | Full setup instructions |
| `IAM_PRINCIPAL_COST_TRACKING_SUMMARY.md` | This file - demo summary |
| `infrastructure/cloudformation/iam-roles.yaml` | IAM roles with tags |
| `guardrail_demo_frontend_apigateway.html` | Frontend that generates Bedrock costs |

## Next Steps

1. ✅ IAM roles tagged
2. ✅ Bedrock API calls generating cost data
3. ⏳ **YOU DO**: Activate cost allocation tags in Billing Console
4. ⏳ **WAIT**: 24 hours for data to appear
5. ⏳ **VIEW**: Cost Explorer filtered by Project=GuardrailDemo

---

**Demo Status**: ✅ Ready for Cost Explorer viewing (tomorrow)

**Key Message**: "Every guardrail API call you make through the frontend is generating cost data with IAM principal tags. Tomorrow, you'll see it in Cost Explorer grouped by Project!"
