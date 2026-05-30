# IAM Principal Cost Tracking Setup for Cost Explorer

## What We've Done

✅ **Tagged IAM Roles** with principal tags:

| IAM Role | Team | CostCenter | Department | Project |
|----------|------|------------|------------|---------|
| `team-alpha-access` | Engineering | CC-1001 | Product | GuardrailDemo |
| `team-beta-access` | Marketing | CC-2002 | Growth | GuardrailDemo |
| `mcp-server-execution-role` | - | - | - | GuardrailDemo |

✅ **Made Bedrock API calls** through tagged IAM principals

⏳ **Waiting for data** - Costs appear in Cost Explorer within 24 hours

---

## Step 1: Activate Cost Allocation Tags

Cost allocation tags must be activated before they appear in Cost Explorer.

### Option A: Via AWS Console (Easiest)

1. Go to **AWS Billing and Cost Management Console**
   - https://console.aws.amazon.com/billing/

2. Navigate to **Cost allocation tags** (left sidebar)
   - Or direct link: https://console.aws.amazon.com/billing/home#/tags

3. Find these **User-defined tags** (they'll show as "Inactive"):
   - `Team`
   - `CostCenter`
   - `Department`
   - `Project`

4. Select all four tags and click **Activate**

5. Wait 24 hours for tags to appear in Cost Explorer

### Option B: Via AWS CLI

```bash
aws ce update-cost-allocation-tags-status \
  --cost-allocation-tags-status \
    TagKey=Team,Status=Active \
    TagKey=CostCenter,Status=Active \
    TagKey=Department,Status=Active \
    TagKey=Project,Status=Active \
  --region us-east-1
```

---

## Step 2: View Costs in Cost Explorer

After 24 hours, view Bedrock costs by team/department.

### Access Cost Explorer

1. Go to **AWS Cost Management Console**
   - https://console.aws.amazon.com/cost-management/home

2. Click **Cost Explorer** in left sidebar
   - Or direct: https://console.aws.amazon.com/cost-management/home?#/cost-explorer

### Filter by Bedrock

1. **Date Range**: Last 7 days (or custom)
2. **Service**: Select "Amazon Bedrock"
3. **Granularity**: Daily or Monthly

### Group by IAM Principal Tags

**Example 1: Cost by Team**
- Click "Group by" → "Tag" → Select "Team"
- You'll see separate bars/lines for:
  - Engineering (team-alpha-access)
  - Marketing (team-beta-access)

**Example 2: Cost by Department**
- Click "Group by" → "Tag" → Select "Department"
- Shows: Product, Growth

**Example 3: Cost by Project**
- Click "Group by" → "Tag" → Select "Project"
- Filter to "GuardrailDemo" to see only this demo's costs

### Advanced: Multiple Dimensions

1. Click "Add filter" → "Tag:Project" → "GuardrailDemo"
2. Click "Group by" → "Tag" → "Team"
3. Now see only GuardrailDemo costs, broken down by team

---

## Step 3: View in Cost and Usage Report (CUR 2.0)

For detailed line-item analysis.

### Enable CUR 2.0 (if not already)

```bash
aws cur put-report-definition \
  --report-definition '{
    "ReportName": "bedrock-principal-costs",
    "TimeUnit": "DAILY",
    "Format": "Parquet",
    "Compression": "Parquet",
    "S3Bucket": "YOUR-CUR-BUCKET",
    "S3Prefix": "bedrock-cur/",
    "S3Region": "us-east-1",
    "ReportVersioning": "OVERWRITE_REPORT",
    "RefreshClosedReports": true,
    "ReportStatus": {
      "lastDelivery": null,
      "lastStatus": "SUCCESS"
    }
  }'
```

### Query CUR with Athena

Once CUR data is available, query it:

```sql
SELECT
    line_item_usage_start_date,
    line_item_iam_principal,
    resource_tags_user_team AS team,
    resource_tags_user_cost_center AS cost_center,
    resource_tags_user_department AS department,
    SUM(line_item_usage_amount) AS total_tokens,
    SUM(line_item_unblended_cost) AS total_cost
FROM
    bedrock_cur_table
WHERE
    line_item_product_code = 'AmazonBedrock'
    AND line_item_usage_start_date >= DATE('2026-05-24')
    AND resource_tags_user_project = 'GuardrailDemo'
GROUP BY
    line_item_usage_start_date,
    line_item_iam_principal,
    resource_tags_user_team,
    resource_tags_user_cost_center,
    resource_tags_user_department
ORDER BY
    line_item_usage_start_date DESC,
    total_cost DESC;
```

**Columns to look for:**
- `line_item_iam_principal`: IAM role ARN (e.g., `arn:aws:iam::<ACCOUNT_ID>:role/mcp-server-execution-role`)
- `resource_tags_user_team`: "Engineering" or "Marketing"
- `resource_tags_user_cost_center`: "CC-1001" or "CC-2002"
- `line_item_usage_amount`: Number of tokens
- `line_item_unblended_cost`: Cost in USD

---

## Step 4: Generate More Test Data

To see meaningful cost data, make more API calls:

```bash
# Run 100 test calls across both guardrails
for i in {1..50}; do
  echo "Call $i - STRICT"
  aws lambda invoke \
    --function-name demo-products-mcp-strict \
    --cli-binary-format raw-in-base64-out \
    --payload '{"method":"tools/call","params":{"name":"demo-products-mcp___list_products","arguments":{}}}' \
    /tmp/test-$i.json > /dev/null 2>&1
  
  echo "Call $i - LENIENT"
  aws lambda invoke \
    --function-name demo-products-mcp-lenient \
    --cli-binary-format raw-in-base64-out \
    --payload '{"method":"tools/call","params":{"name":"demo-products-mcp___list_products","arguments":{}}}' \
    /tmp/test-$i-lenient.json > /dev/null 2>&1
  
  sleep 0.5
done

echo "✅ Generated 100 Bedrock API calls with IAM principal tags"
```

---

## Expected Cost Explorer View

After 24 hours, you should see:

```
Amazon Bedrock Costs (Last 7 Days)
Group by: Tag:Team

┌────────────────────────────────────────┐
│ Engineering: $0.0234                   │  ████████████░░░░░
│ Marketing:   $0.0189                   │  ██████████░░░░░░░
│ (untagged):  $0.0012                   │  █░░░░░░░░░░░░░░░░
└────────────────────────────────────────┘

Group by: Tag:Department

┌────────────────────────────────────────┐
│ Product:     $0.0234                   │  ████████████░░░░░
│ Growth:      $0.0189                   │  ██████████░░░░░░░
└────────────────────────────────────────┘
```

---

## Demo Script for Customers

**Slide 1: The Problem**
> "Before IAM principal tagging, tracking Bedrock costs per team required creating separate Application Inference Profiles for every model-team-region combination. At scale, this means hundreds of profiles to manage."

**Slide 2: The Solution**
> "With IAM principal cost tracking, costs are automatically attributed based on the IAM identity making the call. Tags like Team, CostCenter, and Department flow to Cost Explorer and CUR."

**Slide 3: Live Demo**
1. Show Cost Explorer filtered to Amazon Bedrock
2. Group by "Team" tag → show Engineering vs Marketing costs
3. Group by "CostCenter" tag → show CC-1001 vs CC-2002
4. Filter by "Project: GuardrailDemo" → show only demo costs

**Slide 4: The Value**
> "No additional infrastructure. No profile proliferation. Native AWS billing integration. Attribution to individuals, teams, and departments without managing hundreds of inference profiles."

---

## Key Messages

1. **Zero Infrastructure** - Uses IAM principal tags (50 tags max per role)
2. **Automatic Attribution** - Costs flow to Cost Explorer/CUR within 24 hours
3. **Multi-Dimensional** - Track by Team, CostCenter, Department, Project, User
4. **No Additional Cost** - Feature is free, pay only for Bedrock usage
5. **Works with Federated Identity** - Session tags from Okta/Entra/Ping

---

## Troubleshooting

### Tags not appearing in Cost Explorer?

1. **Check activation**: Tags must be activated in Billing console
2. **Wait 24 hours**: Cost data lags by up to 24 hours
3. **Verify tags on role**: `aws iam get-role --role-name team-alpha-access --query 'Role.Tags'`
4. **Check Bedrock was called**: Look for Lambda invocations in CloudWatch

### Costs showing as "(untagged)"?

- IAM role doesn't have tags: Add tags with `aws iam tag-role`
- Cost allocation tags not activated: Activate in Billing console
- Using API keys instead of IAM: API keys don't support principal tagging

### Want to track individual users?

- **Option 1**: Federated identity with session tags (Okta → AWS STS)
- **Option 2**: Create IAM user per person (not recommended at scale)
- **Option 3**: Application-level tracking in your LLM Gateway

---

## IAM Roles Tagged

```bash
# View all tagged roles
aws iam list-roles --query 'Roles[?Tags[?Key==`Project` && Value==`GuardrailDemo`]].{RoleName:RoleName,Tags:Tags}'
```

**Output:**
```json
[
  {
    "RoleName": "team-alpha-access",
    "Tags": [
      {"Key": "Team", "Value": "Engineering"},
      {"Key": "CostCenter", "Value": "CC-1001"},
      {"Key": "Department", "Value": "Product"},
      {"Key": "Project", "Value": "GuardrailDemo"}
    ]
  },
  {
    "RoleName": "team-beta-access",
    "Tags": [
      {"Key": "Team", "Value": "Marketing"},
      {"Key": "CostCenter", "Value": "CC-2002"},
      {"Key": "Department", "Value": "Growth"},
      {"Key": "Project", "Value": "GuardrailDemo"}
    ]
  }
]
```

---

## Next Steps

1. ✅ IAM roles are tagged
2. ⏳ Activate cost allocation tags (do this now!)
3. ⏳ Wait 24 hours for data
4. ✅ Generate test data (optional - run 100 calls script above)
5. ⏳ View in Cost Explorer tomorrow

---

**Documentation References:**
- [IAM Principal Cost Tracking Launch Blog](https://aws.amazon.com/blogs/aws/new-track-and-attribute-amazon-bedrock-costs-by-iam-user-role-and-tags/)
- [Cost Allocation Tags User Guide](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)
- [Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
