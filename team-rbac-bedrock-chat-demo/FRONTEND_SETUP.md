# Frontend Setup Instructions

## Option 1: Standalone Guardrail Demo (Recommended)

### Step 1: Configure AWS Credentials

The frontend uses the AWS SDK. For local development, configure credentials via the AWS CLI:

```bash
aws configure
```

Or set environment variables before starting your local server:

```bash
export AWS_ACCESS_KEY_ID=<your-access-key>
export AWS_SECRET_ACCESS_KEY=<your-secret-key>
export AWS_SESSION_TOKEN=<your-session-token>   # if using temporary credentials
```

> **Security note**: Never hardcode AWS credentials in HTML or JavaScript files. Use IAM roles, AWS CLI profiles, or environment variables instead. For browser-based demos, consider using [Amazon Cognito Identity Pools](https://docs.aws.amazon.com/cognito/latest/developerguide/identity-pools.html) to vend temporary credentials safely.

### Step 2: Open in Browser

```bash
# Server is already running on port 8002
open http://localhost:8002/guardrail_demo_frontend.html
```

### Step 3: Test the Demo

Click on the product buttons:
- **USB Cable** - Contains "slut" (sold out)
- **Laptop Stand** - Contains "fart" (speed)  
- **Desk Organizer** - Contains "prick" (dot)
- **List All Products** - Shows all 8 products

**Expected Results:**
- **Left Panel (STRICT)**: ⚠️ Content blocked by guardrail
- **Right Panel (LENIENT)**: ✅ Product details shown with Swedish words highlighted

## Option 2: Integrate Guardrails into Your Own Chatbox

If you want to add guardrail testing to your own chatbox application:

### Add Guardrail Test Buttons

Add this HTML after line 456 (in the suggestions section):

```html
<div class="suggestions">
    <h4>🛡️ Test Guardrails:</h4>
    <div class="suggestion-chips">
        <div class="suggestion-chip" onclick="testGuardrailStrict()">Test STRICT (blocks Swedish)</div>
        <div class="suggestion-chip" onclick="testGuardrailLenient()">Test LENIENT (allows all)</div>
    </div>
</div>
```

### Add JavaScript Functions

Add this JavaScript before the closing `</script>` tag:

```javascript
async function testGuardrailStrict() {
    if (!awsCredentials) {
        alert('⚠️ AWS credentials not configured');
        return;
    }

    addMessage('user', 'Testing STRICT guardrail with product PROD-002 (contains "slut")');
    addTypingIndicator();

    try {
        const lambda = getLambdaClient();
        const params = {
            FunctionName: 'demo-products-mcp-strict',
            Payload: JSON.stringify({
                method: 'tools/call',
                params: {
                    name: 'demo-products-mcp___get_product_by_id',
                    arguments: { product_id: 'PROD-002' }
                }
            })
        };

        const result = await lambda.invoke(params).promise();
        const response = JSON.parse(result.Payload);

        removeTypingIndicator();

        if (response.error) {
            addMessage('assistant', `⚠️ GUARDRAIL BLOCKED!\n\n${response.error.message}\n\nThis demonstrates false positive filtering - "slut" is Swedish for "sold out" but was blocked.`, true);
        } else {
            addMessage('assistant', `❌ Unexpected: Content was not blocked`, false);
        }
    } catch (error) {
        removeTypingIndicator();
        addMessage('assistant', `❌ Error: ${error.message}`, false);
    }
}

async function testGuardrailLenient() {
    if (!awsCredentials) {
        alert('⚠️ AWS credentials not configured');
        return;
    }

    addMessage('user', 'Testing LENIENT mode with product PROD-002 (contains "slut")');
    addTypingIndicator();

    try {
        const lambda = getLambdaClient();
        const params = {
            FunctionName: 'demo-products-mcp-lenient',
            Payload: JSON.stringify({
                method: 'tools/call',
                params: {
                    name: 'demo-products-mcp___get_product_by_id',
                    arguments: { product_id: 'PROD-002' }
                }
            })
        };

        const result = await lambda.invoke(params).promise();
        const response = JSON.parse(result.Payload);

        removeTypingIndicator();

        if (response.result) {
            const product = JSON.parse(response.result.content[0].text);
            addMessage('assistant', `✅ CONTENT ALLOWED!\n\nProduct: ${product.name}\nDescription: ${product.description}\n\nNo guardrail filtering - Swedish words pass through.`, true);
        } else {
            addMessage('assistant', `❌ Unexpected response`, false);
        }
    } catch (error) {
        removeTypingIndicator();
        addMessage('assistant', `❌ Error: ${error.message}`, false);
    }
}
```

## Deployed Lambda Functions

Both guardrail versions are deployed and ready:

```bash
# STRICT version - blocks Swedish words
aws lambda invoke \
  --function-name demo-products-mcp-strict \
  --payload '{"method":"tools/call","params":{"name":"demo-products-mcp___get_product_by_id","arguments":{"product_id":"PROD-002"}}}' \
  /tmp/output.json

# LENIENT version - allows all content
aws lambda invoke \
  --function-name demo-products-mcp-lenient \
  --payload '{"method":"tools/call","params":{"name":"demo-products-mcp___get_product_by_id","arguments":{"product_id":"PROD-002"}}}' \
  /tmp/output.json
```

## Product Catalog with Swedish Words

| Product ID | Swedish Word | Translation | Full Description |
|------------|-------------|-------------|------------------|
| PROD-002 | slut | sold out | "Currently slut (sold out)" |
| PROD-003 | fart | speed | "Quick fart (speed) adjustment" |
| PROD-005 | prick | dot | "Comes with prick (dot) markers" |

## Guardrails

1. **mcp-strict-english-only** (ID: `<YOUR_STRICT_GUARDRAIL_ID>`)
   - Blocks: slut, fart, prick
   - Status: READY
   - Purpose: Demonstrate false positives

2. **support-assistant-guardrail** (ID: `<YOUR_SUPPORT_GUARDRAIL_ID>`)
   - No word filters
   - Blocks: Prompt injection, PII
   - Purpose: General content safety

## Architecture

```
Browser (JavaScript)
    ↓
AWS SDK (Lambda.invoke)
    ↓
┌─────────────────────┬─────────────────────┐
│                     │                     │
│ demo-products-mcp   │ demo-products-mcp  │
│      -strict        │      -lenient       │
│                     │                     │
│ GUARDRAIL_ID=       │ GUARDRAIL_ID=      │
│   <YOUR_GUARDRAIL_ID>│   (empty)           │
│                     │                     │
│ bedrock:            │ (no guardrail)     │
│ ApplyGuardrail      │                     │
│    ↓                │                     │
│ ⚠️ BLOCKED          │ ✅ ALLOWED          │
└─────────────────────┴─────────────────────┘
```

## Troubleshooting

### "AWS credentials not configured"
- Add your AWS access key and secret key to the HTML file
- Make sure you have permissions for `lambda:InvokeFunction`

### "AccessDeniedException: bedrock:ApplyGuardrail"
- Already fixed! IAM role updated with guardrail permissions

### Products not loading
- Check CloudWatch Logs: `/aws/lambda/demo-products-mcp-strict`
- Verify Lambda functions exist: `aws lambda list-functions | grep demo-products-mcp`

### CORS errors
- Frontend uses AWS SDK directly (no CORS issues)
- Make sure AWS credentials are valid

## Demo Script

1. **Login Scenario:**
   "Welcome! I'll show you how Bedrock Guardrails can create false positives with multi-lingual content."

2. **Click USB Cable:**
   - Left: "See? BLOCKED because it contains 'slut'"
   - Right: "Same product, no filtering, shows 'slut (sold out)'"

3. **Key Message:**
   "This is a real challenge for international businesses. The Swedish word 'slut' means 'sold out', but English-only guardrails block it."

4. **Solution:**
   "Options: language detection, context-aware filters, allow-lists, or per-region guardrails."

## Next Steps

- [ ] Add AWS credentials to HTML
- [ ] Test in browser
- [ ] Share demo URL or screenshot
- [ ] Document for aws-samples publication

---

**Files:**
- Frontend: `guardrail_demo_frontend.html` (in repo root)
- Lambda STRICT: `demo-products-mcp-strict`
- Lambda LENIENT: `demo-products-mcp-lenient`
- Documentation: `GUARDRAIL_DEMO.md`
