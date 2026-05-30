# Demo Script - Team-Based RBAC LLM Gateway

This demo script shows how team-based access control works with the LLM gateway.

## Prerequisites

- Deployment completed (see [DEPLOYMENT.md](DEPLOYMENT.md))
- `chatbox.html` configured with your API Gateway URL and API keys
- Browser open to `chatbox.html`

---

## Demo Flow

### 🎯 Scenario: Two Teams, Different Access Levels

**Setup:**
- **Team Alpha**: Engineering team with access to Haiku + Sonnet (balanced performance + cost)
- **Team Beta**: Support team with access to Haiku only (cost-optimized)

**Goal:** Show that the gateway enforces model access policies without changing application code.

---

## Part 1: Team Alpha - Full Access

### Step 1: Login as Team Alpha

1. Open `chatbox.html` in your browser
2. Click "Team Alpha" in the team selection modal
3. Observe:
   - User avatar shows "A" with AWS orange color
   - Stats bar appears showing "Requests: 0"
   - Model badges update:
     - ✓ Claude 3.5 Haiku (Allowed)
     - ✓ Claude 3.5 Sonnet (Allowed)
     - ✗ Claude Opus 4 (Denied)

### Step 2: Test with Allowed Model (Haiku)

1. Type: "What is the capital of France?"
2. Click Send
3. Observe:
   - Response from Claude Haiku appears quickly
   - Stats bar updates:
     - Requests: 1
     - Input: ~20 tokens
     - Output: ~10 tokens
     - Cost: ~$0.00015
   - Latency shown (~500-800ms)

**✅ Result:** Team Alpha can use Haiku model

### Step 3: Switch to Sonnet Model

1. Click the model selector dropdown
2. Select "Claude 3.5 Sonnet"
3. Observe: System message "✓ Model selected: Claude 3.5 Sonnet (Allowed)"
4. Type: "Write a haiku about cloud computing"
5. Click Send
6. Observe:
   - Response from Sonnet (higher quality than Haiku)
   - Cost is higher (~$0.0012 vs $0.00015)

**✅ Result:** Team Alpha can use Sonnet model

### Step 4: Try Denied Model (Opus)

1. Click the model selector dropdown
2. Select "Claude Opus 4"
3. Observe: Warning message "⚠️ Warning: Team Alpha does not have access to Claude Opus 4. If you send a message, it will be DENIED by the gateway."
4. Type: "Hello"
5. Click Send
6. Observe:
   - **🚫 MODEL ACCESS DENIED** message appears
   - Error explains: "Team Alpha attempted to use Claude Opus 4, but this model is not in your allowed list."
   - Latency: ~200ms (fast failure at gateway)
   - No Bedrock API call was made (saves cost!)

**✅ Result:** Team Alpha CANNOT use Opus - gateway blocks at runtime

---

## Part 2: Team Beta - Limited Access

### Step 5: Switch to Team Beta

1. Click "New chat" button in sidebar
2. Select "Team Beta"
3. Observe:
   - User avatar changes to "B" with different color
   - Model badges update:
     - ✓ Claude 3.5 Haiku (Allowed)
     - ✗ Claude 3.5 Sonnet (Denied)
     - ✗ Claude Opus 4 (Denied)
   - System message: "📋 Your allowed models: Claude 3.5 Haiku"
   - Stats reset to 0

### Step 6: Test with Allowed Model (Haiku)

1. Type: "What is 2+2?"
2. Click Send
3. Observe:
   - Response from Claude Haiku
   - Cost tracking works for Team Beta

**✅ Result:** Team Beta can use Haiku model

### Step 7: Try Denied Model (Sonnet)

1. Click model selector → "Claude 3.5 Sonnet"
2. Observe: Warning message appears
3. Type: "Hello"
4. Click Send
5. Observe:
   - **🚫 MODEL ACCESS DENIED**
   - Error: "Team Beta attempted to use Claude 3.5 Sonnet, but this model is not in your allowed list."
   - Allowed models: Claude 3.5 Haiku only

**✅ Result:** Team Beta CANNOT use Sonnet - cost control enforced

---

## Part 3: Cost Tracking

### Step 8: Compare Costs Between Teams

1. Send 5 messages as Team Alpha (mix of Haiku + Sonnet)
2. Send 5 messages as Team Beta (Haiku only)
3. Observe:
   - Team Alpha's cost is higher (using Sonnet for some requests)
   - Team Beta's cost is lower (Haiku only)
   - Each team has independent cost counters

### Step 9: View Costs in AWS Console

```bash
# In your terminal, check CloudWatch logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/llm-gateway-proxy \
  --filter-pattern "team-alpha" \
  --limit 10

# You should see IAM role assumption logs like:
# "Assuming role for team: team-alpha"
# "Role ARN: arn:aws:iam::123456789012:role/team-alpha-role"
```

**After 24 hours:**
1. Go to AWS Cost Explorer
2. Filter by Service: "Amazon Bedrock"
3. Group by: "User" (IAM principal)
4. See costs split by `team-alpha-role` and `team-beta-role`

**✅ Result:** Costs are tracked per team automatically

---

## Part 4: (Optional) Guardrails Demo

If you deployed guardrails (see DEPLOYMENT.md Step 6):

### Step 10: Test Swedish False Positives

1. Login as Team Alpha
2. Type: "slut på vägen" (Swedish for "end of the road")
3. Click Send
4. Observe:
   - If guardrail is enabled: ❌ "Content blocked by guardrail"
   - This is a **false positive** - "slut" means "end" in Swedish, not offensive!

5. Type: "This is safe content"
6. Click Send
7. Observe: ✅ Allowed

**✅ Result:** Demonstrates multi-lingual content filtering challenges

See [GUARDRAIL_DEMO.md](GUARDRAIL_DEMO.md) for detailed guardrail testing.

---

## Key Takeaways

### 1. **Zero Code Changes**
- No application code knows about Bedrock credentials
- No application code enforces model policies
- Everything happens at the gateway

### 2. **Centralized Governance**
- Add new team → Create IAM role + API key
- Change model access → Update IAM policy
- All enforcement in one place

### 3. **Cost Attribution**
- Every API call tagged with team IAM principal
- AWS Cost Explorer shows costs per team
- Real-time cost tracking in UI

### 4. **Runtime Enforcement**
- Policies checked on every request
- Fast failure for denied models (~200ms)
- No wasted Bedrock API calls

---

## Testing Checklist

Use this checklist to verify everything works:

### Team Alpha Tests
- [ ] Can login as Team Alpha
- [ ] Model badges show: Haiku ✓, Sonnet ✓, Opus ✗
- [ ] Can send message with Haiku model → ✅ Success
- [ ] Can send message with Sonnet model → ✅ Success
- [ ] Can send message with Opus model → ❌ 403 Denied
- [ ] Stats bar shows correct token counts and costs
- [ ] CloudWatch logs show "team-alpha" IAM principal

### Team Beta Tests
- [ ] Can login as Team Beta
- [ ] Model badges show: Haiku ✓, Sonnet ✗, Opus ✗
- [ ] Can send message with Haiku model → ✅ Success
- [ ] Cannot send message with Sonnet → ❌ 403 Denied
- [ ] Cannot send message with Opus → ❌ 403 Denied
- [ ] Stats bar tracks Team Beta costs separately
- [ ] CloudWatch logs show "team-beta" IAM principal

### Cost Tracking Tests
- [ ] Each team has independent cost counters
- [ ] Token counts are accurate
- [ ] Cost calculations match actual Bedrock pricing
- [ ] CloudWatch logs show IAM role assumption
- [ ] (After 24h) Cost Explorer shows per-team costs

---

## Advanced Demos

### Demo 5: Add a New Team

Show how easy it is to add a third team:

```bash
# 1. Create IAM role for Team Gamma
aws iam create-role \
  --role-name team-gamma-role \
  --assume-role-policy-document file://trust-policy.json

# 2. Attach Bedrock policy (Haiku + Sonnet + Opus)
aws iam put-role-policy \
  --role-name team-gamma-role \
  --policy-name bedrock-access \
  --policy-document file://gamma-policy.json

# 3. Create API key in API Gateway
aws apigateway create-api-key \
  --name team-gamma-key \
  --enabled

# 4. Update Lambda environment variables
aws lambda update-function-configuration \
  --function-name llm-gateway-proxy \
  --environment Variables="{...,TEAM_GAMMA_ROLE_ARN=arn:aws:iam::123456789012:role/team-gamma-role}"

# 5. Update chatbox.html
# Add team-gamma to TEAMS and TEAM_MODEL_PERMISSIONS objects
```

**Result:** New team added without changing Lambda code!

### Demo 6: Change Model Access

Show how to promote Team Beta from Haiku-only to Haiku+Sonnet:

```bash
# Update IAM policy to allow Sonnet
aws iam put-role-policy \
  --role-name team-beta-role \
  --policy-name bedrock-access \
  --policy-document file://beta-sonnet-policy.json

# Update Lambda environment variable
aws lambda update-function-configuration \
  --function-name llm-gateway-proxy \
  --environment Variables="{...,TEAM_BETA_MODELS=haiku,sonnet}"
```

Refresh browser → Team Beta can now use Sonnet!

---

## Troubleshooting

### "Network Error" in browser
- Check API Gateway URL is correct in chatbox.html
- Check CORS is enabled on API Gateway
- Check browser console (F12) for detailed error

### "Invalid API key"
- Verify API key is correct (check CloudFormation outputs)
- Verify usage plan is attached to API key
- Check API key is enabled

### Model always shows "Denied"
- Check IAM role has correct bedrock:InvokeModel permissions
- Verify model ID format (e.g., `us.anthropic.claude-3-5-haiku-20241022-v1:0`)
- Check Lambda environment variables match IAM policies

### Costs not tracking
- Check CloudWatch logs for IAM role assumption
- Wait 24 hours for Cost Explorer data
- Verify Cost Allocation Tags are enabled

---

## Demo Tips

### For Live Presentations

1. **Open two browser windows side-by-side**
   - Left: Team Alpha (full access)
   - Right: Team Beta (limited access)
   - Send same message to both → show different model access

2. **Highlight the speed of denied requests**
   - Team Alpha tries Opus → 200ms failure (no Bedrock call)
   - Show in CloudWatch logs that Lambda returned early

3. **Show the IAM role assumption in CloudWatch**
   - Filter logs by "Assuming role"
   - Point out team-alpha-role vs team-beta-role
   - This is what enables cost attribution!

4. **Open AWS Cost Explorer in another tab**
   - Filter by Bedrock
   - Group by User (IAM principal)
   - Show costs split by team

### For Video Demos

1. Record Team Alpha session with voiceover explaining model access
2. Record Team Beta session showing denied access
3. Show CloudWatch logs with highlighted IAM principals
4. Show Cost Explorer dashboard (24h after demo)

---

## What to Highlight

### To Technical Audiences
- IAM role assumption mechanism
- Lambda proxy pattern
- SigV4 signing for Bedrock API
- CloudWatch logging for audit trail

### To Business Audiences
- Cost savings from preventing Opus usage by support team
- Chargeback: can invoice each team based on actual usage
- Governance: centralized control without app changes
- Scalability: add 100 teams without code changes

---

**Demo complete! 🎉**

You've shown how centralized LLM governance enables:
- Team-based access control
- Cost attribution and chargeback
- Runtime policy enforcement
- Zero application code changes
