# Bedrock Guardrails Multi-Lingual Demo

## Overview

This demo showcases AWS Bedrock Guardrails for multi-lingual content filtering challenges. It demonstrates how word filters can block innocent content due to language differences.

**Scenario**: Swedish words that are innocent in Swedish but sound offensive in English.

## Swedish Words Used

| Swedish Word | Swedish Meaning | English Interpretation | Example Usage |
|--------------|----------------|------------------------|---------------|
| **slut** | end/finished/sold out | Offensive term | "Currently slut (sold out)" |
| **fart** | speed | Crude/childish | "Quick fart (speed) adjustment" |
| **prick** | dot/period | Offensive term | "Prick (dot) markers for labeling" |

## Demo Architecture

### Two Guardrails

1. **STRICT Guardrail** (`mcp-strict-english-only` - ID: `<YOUR_STRICT_GUARDRAIL_ID>`)
   - Blocks Swedish words: slut, fart, prick
   - Content filters: Sexual, Violence, Hate, Insults
   - Demonstrates false positive blocking

2. **LENIENT Mode** (No guardrail)
   - Allows all content
   - No word filtering
   - Shows unfiltered results

### Two Lambda Functions

1. **demo-products-mcp-strict**
   - Environment: `GUARDRAIL_ID=<YOUR_STRICT_GUARDRAIL_ID>`
   - Uses `bedrock:ApplyGuardrail` API
   - Blocks content containing Swedish words

2. **demo-products-mcp-lenient**
   - Environment: `GUARDRAIL_ID=` (empty)
   - No guardrail applied
   - Returns all content unfiltered

## Sample Products with Swedish Words

```json
{
  "id": "PROD-002",
  "name": "USB-C Cable",
  "description": "Currently slut (sold out)"
}

{
  "id": "PROD-003",
  "name": "Laptop Stand",
  "description": "Quick fart (speed) adjustment"
}

{
  "id": "PROD-005",
  "name": "Desk Organizer",
  "description": "Comes with prick (dot) markers"
}
```

## Test Results

### Test 1: Get Single Product (PROD-002 with "slut")

**STRICT Guardrail:**
```bash
aws lambda invoke \
  --function-name demo-products-mcp-strict \
  --payload '{"method":"tools/call","params":{"name":"demo-products-mcp___get_product_by_id","arguments":{"product_id":"PROD-002"}}}' \
  /tmp/output.json

# Result: ❌ BLOCKED
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32000,
    "message": "Content blocked by guardrail. Product description contains Swedish words."
  }
}
```

**LENIENT Mode:**
```bash
aws lambda invoke \
  --function-name demo-products-mcp-lenient \
  --payload '{"method":"tools/call","params":{"name":"demo-products-mcp___get_product_by_id","arguments":{"product_id":"PROD-002"}}}' \
  /tmp/output.json

# Result: ✅ ALLOWED
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"id\": \"PROD-002\",\n  \"description\": \"Currently slut (sold out)\"\n}"
      }
    ],
    "metadata": {
      "guardrail_action": "NONE"
    }
  }
}
```

### Test 2: List All Products

**STRICT Guardrail:**
- ❌ Blocked - Contains multiple Swedish words across products

**LENIENT Mode:**
- ✅ Allowed - Returns all 8 products including Swedish words

## Key Insights

### Problem Demonstrated
1. **False Positives**: Innocent Swedish words blocked in English context
2. **Multi-Lingual Challenge**: Single language filter affects cross-cultural content
3. **Business Impact**: Product descriptions with legitimate Swedish terms unusable

### Solutions
1. **Language Detection**: Detect input language before applying filters
2. **Context-Aware Filtering**: Different filters per language
3. **Allow-Lists**: Whitelist known false positives
4. **Custom Guardrails**: Per-region or per-market guardrails

## Implementation Details

### Guardrail Integration Code

```python
import boto3

bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')

def apply_guardrail(content, guardrail_id):
    """Apply Bedrock Guardrail to content"""
    response = bedrock_runtime.apply_guardrail(
        guardrailIdentifier=guardrail_id,
        guardrailVersion='DRAFT',
        source='OUTPUT',
        content=[{'text': {'text': content}}]
    )
    
    action = response.get('action', 'NONE')
    
    if action == 'GUARDRAIL_INTERVENED':
        return True, "Content blocked"
    else:
        return False, content
```

### IAM Permissions Required

```yaml
Policies:
  - PolicyName: BedrockGuardrailAccess
    PolicyDocument:
      Statement:
        - Effect: Allow
          Action:
            - 'bedrock:ApplyGuardrail'
          Resource:
            - 'arn:aws:bedrock:*:*:guardrail/*'
```

## Deployment

### 1. Create Guardrail
```bash
aws bedrock create-guardrail \
  --name "mcp-strict-english-only" \
  --word-policy-config '{
    "wordsConfig": [
      {"text": "slut"},
      {"text": "fart"},
      {"text": "prick"}
    ]
  }'
```

### 2. Deploy Lambda Functions
```bash
cd lambda/mcp-servers/products-mcp-with-guardrail

# Deploy STRICT version
./deploy-strict.sh

# Deploy LENIENT version
./deploy-lenient.sh
```

### 3. Update IAM Role (CloudFormation)
```bash
cd /path/to/bedrock-agentcore-mcp-gateway-demo
aws cloudformation update-stack \
  --stack-name mcp-gateway-demo \
  --template-body file://infrastructure/cloudformation/iam-roles.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

## Cost Analysis

### Per Request
- **Guardrail API Call**: ~$0.01 per 1000 characters
- **Lambda Execution**: ~$0.0000002 per request (256MB, 100ms)
- **Total**: ~$0.01 per 1000 characters + Lambda costs

### Monthly Estimate (10,000 requests)
- Guardrail: ~$1-5 (depends on content size)
- Lambda: ~$0.002
- **Total**: ~$1-5/month

## Use Cases

1. **E-commerce**: International product catalogs with multi-language descriptions
2. **Customer Support**: Chat systems handling multiple languages
3. **Content Moderation**: User-generated content in international markets
4. **Documentation**: Technical docs with code/foreign language examples

## Limitations

1. **No Language Auto-Detection**: Guardrail doesn't detect content language
2. **Binary Decision**: Either block or allow - no partial filtering
3. **Performance Impact**: Additional API call adds 50-100ms latency
4. **Cost**: Per-character pricing can add up for large content

## Best Practices

1. **Test Thoroughly**: Test guardrails with real multi-lingual content
2. **Monitor False Positives**: Track blocked content in CloudWatch
3. **Use Versioning**: Create guardrail versions for rollback
4. **Separate Guardrails**: Different guardrails per language/region
5. **Allow-Lists**: Maintain list of known false positives

## Related AWS Services

- **Amazon Comprehend**: Detect language of input
- **Amazon Translate**: Translate to single language before filtering
- **CloudWatch Logs**: Monitor guardrail decisions
- **X-Ray**: Trace guardrail latency impact

## Resources

- [Bedrock Guardrails Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
- [ApplyGuardrail API Reference](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ApplyGuardrail.html)
- [Guardrail Pricing](https://aws.amazon.com/bedrock/pricing/)

---

**Demo Status**: ✅ Fully Functional  
**Last Updated**: May 24, 2026  
**Region**: us-east-1  
**Account**: \<YOUR_ACCOUNT_ID\>
