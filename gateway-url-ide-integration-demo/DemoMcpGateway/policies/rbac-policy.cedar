// ReadOnly Developers: Can only use list, get, and search operations
// NOTE: After deploying the gateway, replace <YOUR_GATEWAY_ARN> with the actual Gateway ARN from the agentcore deploy output
permit(
    principal,
    action in
        [AgentCore::Action::"customers-mcp___list_customers",
         AgentCore::Action::"customers-mcp___get_customer_by_id",
         AgentCore::Action::"orders-mcp___list_orders",
         AgentCore::Action::"orders-mcp___get_order_by_id",
         AgentCore::Action::"products-mcp___list_products",
         AgentCore::Action::"products-mcp___get_product_by_id",
         AgentCore::Action::"products-mcp___search_products",
         AgentCore::Action::"jira-mcp___list_jira_tickets"],
    resource ==
        AgentCore::Gateway::"<YOUR_GATEWAY_ARN>"
)
when
{ (principal.hasTag("group")) && ((principal.getTag("group")) == "ReadOnly") };

// FullAccess Developers: Can use all tools
permit(
    principal,
    action,
    resource ==
        AgentCore::Gateway::"<YOUR_GATEWAY_ARN>"
)
when
{ (principal.hasTag("group")) && ((principal.getTag("group")) == "FullAccess") };
