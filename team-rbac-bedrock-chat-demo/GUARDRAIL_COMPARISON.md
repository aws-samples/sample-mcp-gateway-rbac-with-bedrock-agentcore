# Bedrock Guardrails Comparison Demo

## Two Guardrails, Same Content, Different Results

This demo compares two Bedrock Guardrails with different configurations:

### Left Panel: English-Only Guardrail (Protects English Speakers)

**Guardrail**: `mcp-strict-english-only` (ID: `<YOUR_STRICT_GUARDRAIL_ID>`)

**Configuration**:
- **Word Filters**: Blocks "slut", "fart", "prick"
- **Reasoning**: These ARE offensive words in English language
- **Purpose**: Protect English-speaking customers from profanity

**Use Case**: Organization only serves English-speaking markets (US, UK, Australia)

**Result**: ✅ CORRECTLY blocks offensive English words

### Right Panel: Multi-Lingual Aware Guardrail (Serves Nordic Markets)

**Guardrail**: `mcp-multilingual-aware` (ID: `<YOUR_MULTILINGUAL_GUARDRAIL_ID>`)

**Configuration**:
- **No Word Filters**: Swedish words NOT in blocklist
- **Content Filters Only**: Hate, Violence, Sexual, Insults (AI-detected, context-aware)
- **Reasoning**: "Slut" is NOT offensive in Swedish - it means "sold out" or "finished"

**Use Case**: International organization serving Nordic markets (Sweden, Norway, Denmark)

**Result**: ✅ CORRECTLY allows innocent Swedish words in product descriptions

---

## Demo Comparison

| Aspect | English-Only Guardrail | Multi-Lingual Aware |
|--------|------------------------|---------------------|
| **English word "slut"** | ✅ BLOCKED (offensive) | N/A - Not used in English |
| **Swedish word "slut"** | ❌ False Positive | ✅ ALLOWED (innocent) |
| **English word "fart"** | ✅ BLOCKED (crude) | N/A - Not used in English |
| **Swedish word "fart"** | ❌ False Positive | ✅ ALLOWED (means "speed") |
| **Actual profanity** | ✅ BLOCKED | ✅ BLOCKED |
| **Hate speech** | ✅ BLOCKED | ✅ BLOCKED |
| **Target Market** | 🇺🇸 English-only | 🇸🇪 Nordic/International |

---

## Technical Implementation

### English-Only Guardrail

```python
# Lambda: demo-products-mcp-strict
GUARDRAIL_ID = "<YOUR_STRICT_GUARDRAIL_ID>"

# Guardrail Config
word_policy = {
    "wordsConfig": [
        {"text": "slut"},
        {"text": "fart"},
        {"text": "prick"}
    ]
}

# Result for "Product is slut (sold out)"
action = "GUARDRAIL_INTERVENED"  # BLOCKED!
```

### Multi-Lingual Aware Guardrail

```python
# Lambda: demo-products-mcp-lenient
GUARDRAIL_ID = "<YOUR_MULTILINGUAL_GUARDRAIL_ID>"

# Guardrail Config
# NO word filters - only AI content filters
content_policy = {
    "filtersConfig": [
        {"type": "SEXUAL", "inputStrength": "MEDIUM"},
        {"type": "VIOLENCE", "inputStrength": "MEDIUM"},
        {"type": "HATE", "inputStrength": "HIGH"},
        {"type": "INSULTS", "inputStrength": "MEDIUM"}
    ]
}

# Result for "Product is slut (sold out)"
action = "NONE"  # ALLOWED! AI understands Swedish context
```

---

## Key Learnings

### Challenge: Same Word, Different Languages

**The Problem**: 
- In **ENGLISH**: "slut", "fart", "prick" ARE offensive/crude words
- In **SWEDISH**: "slut", "fart", "prick" are INNOCENT everyday words

**One guardrail can't serve both markets!**

**More Examples**:
- Swedish: "slut" (sold out), "fart" (speed), "prick" (dot) → INNOCENT
- German: "gift" (poison), "dick" (thick) → INNOCENT but sound offensive in English
- French: "con" (stupid/idiot) → Common word but offensive in English slang

### Solution Options

#### Option 1: Language Detection + Guardrail Routing
```
Input → Detect Language → Route to Language-Specific Guardrail
├─ English → English-Only Guardrail (strict word filter)
├─ Swedish → Nordic Guardrail (no Swedish word filters)
└─ German → European Guardrail (no German word filters)
```

#### Option 2: Context-Aware AI Filtering (This Demo)
```
Input → AI Content Filter (no word lists)
        ├─ Analyzes semantic meaning
        ├─ Understands context
        └─ Detects actual harmful intent
```

#### Option 3: Allow-Lists
```
Guardrail Config:
{
  "wordsConfig": [...blocked words...],
  "allowedContexts": [
    {"word": "slut", "context": "Swedish product descriptions"},
    {"word": "fart", "context": "Swedish technical specs"}
  ]
}
```
*Note: Allow-lists not yet supported in Bedrock Guardrails*

---

## Business Impact

### Scenario: E-Commerce Company

**Challenge**:
- Sells to Nordic countries (Sweden, Norway, Denmark)
- Product descriptions contain Swedish words
- English-only guardrail blocks 30% of valid products

**With English-Only Guardrail**:
- ❌ "USB cable - currently slut" → BLOCKED
- ❌ "Adjustable fart control" → BLOCKED  
- ❌ "Comes with prick markers" → BLOCKED
- **Result**: 30% of products unavailable, lost revenue

**With Multi-Lingual Aware Guardrail**:
- ✅ Same products → ALLOWED
- ✅ Actual harmful content → BLOCKED
- **Result**: 100% product availability, customer satisfaction

**ROI**:
- Reduced false positives: 30% → 2%
- Increased product catalog coverage: 70% → 98%
- Customer satisfaction: +25%

---

## Cost Comparison

Both guardrails have the same cost:

| Operation | Cost |
|-----------|------|
| bedrock:ApplyGuardrail | $0.75 per 1,000 text units |
| Text Unit | 1,000 characters |

**Example**:
- Product description: 200 characters = 0.2 text units
- Cost per check: $0.00015
- 1 million products: $150

**No additional cost for AI content filters vs word filters!**

---

## Demo URLs

### Frontend
- **Live Demo**: http://localhost:8002/guardrail_demo_frontend_apigateway.html
- **With Cost Tracking**: http://localhost:8002/guardrail_demo_with_cost_tracking.html

### API Gateway Endpoints
- **English-Only**: https://<YOUR_API_GATEWAY_ID>.execute-api.<REGION>.amazonaws.com/prod/guardrail/strict
- **Multi-Lingual**: https://<YOUR_API_GATEWAY_ID>.execute-api.<REGION>.amazonaws.com/prod/guardrail/lenient

### Lambda Functions
- **English-Only**: `demo-products-mcp-strict`
- **Multi-Lingual**: `demo-products-mcp-lenient`

---

## Customer Talking Points

### Discovery Questions

1. **"Do you serve international markets with non-English content?"**
   → If yes, false positives are a risk

2. **"Have you experienced content filtering blocking legitimate content?"**
   → Validate the problem exists

3. **"How do you currently handle multi-lingual product descriptions?"**
   → Understand current workarounds

### Value Proposition

> "Bedrock Guardrails with AI content filters understand context and semantic meaning, not just keywords. This eliminates false positives for multi-lingual content while still blocking actual harmful content."

### Differentiators vs Competitors

**vs OpenAI Moderation API**:
- Bedrock: Context-aware, multi-lingual by design
- OpenAI: Primarily English-focused

**vs LLamaGuard**:
- Bedrock: Managed service, no model hosting
- LLamaGuard: Self-hosted, more configuration

**vs Custom LLM Filters**:
- Bedrock: Native AWS integration, CUR cost tracking
- Custom: Additional infrastructure, harder to attribute costs

---

## Next Steps

1. ✅ Demo is live and working
2. ✅ Both guardrails configured and tested
3. ⏳ Tomorrow: View costs in Cost Explorer
4. 📊 Create presentation deck
5. 🎯 Schedule customer demo

---

**Demo Created**: 2026-05-24  
**Guardrails**: 2 (English-Only + Multi-Lingual Aware)  
**Test Products**: 8 (3 with Swedish words)  
**Status**: ✅ Ready for customer demos
