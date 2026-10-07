# Connecting VS Code to AgentCore Gateway using Entra ID (Azure AD)

This guide replaces the Cognito steps in OAUTH_DEMO.md with an Entra ID App Registration.
The AgentCore Gateway accepts any OIDC-compliant identity provider, so the change is
entirely on the identity side. The Cedar RBAC layer, the gateway itself, and the VS Code
configuration work identically regardless of which IdP you use.

---

## How it works

VS Code triggers a browser-based Authorization Code + PKCE login when a developer first
connects to the gateway. The browser opens, the developer signs in with their corporate
Entra credentials, and VS Code receives a short-lived JWT. Every subsequent MCP tool call
carries that JWT. AgentCore validates the JWT against your Entra issuer URL and Cedar
evaluates the team claim inside the token to allow or deny each tool.

No credentials are stored on the developer laptop. No local proxy is needed.

---

## Prerequisites

You need an AWS account with AgentCore access, the AWS CLI configured with admin
credentials, Python 3.9+, and an Azure tenant where you can create App Registrations.
The base IAM deploy (deploy.sh) should be working before you start this guide.

---

## Step 1: Create the Entra App Registration

Open the Azure portal and go to Microsoft Entra ID > App registrations > New registration.

Set the name to something descriptive such as "AgentCore MCP Gateway".

Under "Supported account types" select the option that matches your organisation
(typically "Accounts in this organizational directory only").

Under "Redirect URI" select "Public client / native (mobile and desktop)" from the
platform dropdown and add these three URIs:

```
http://127.0.0.1:33418
http://localhost:33418
vscode://vscode.github-authentication/did-authenticate
```

These are the exact URIs VS Code uses during its OAuth flow. If even one is missing,
VS Code will receive a redirect mismatch error after the user signs in.

Click Register and note the Application (client) ID and the Directory (tenant) ID.
You will need both values in later steps.

---

## Step 2: Expose a team claim in the token

AgentCore Cedar policies read a claim named "team" from the access token. You need to
inject this into every token.

**Option A: Use an optional claims mapping (recommended for most deployments)**

In the App Registration go to Token configuration > Add optional claim > Access token.
Add the "groups" claim. This includes the user's Entra group IDs in the token.

Then update your Cedar policies to match against the group GUIDs instead of plain team
names. The Cedar syntax stays the same, only the values change:

```cedar
permit(
    principal,
    action == AgentCore::Action::"products-mcp___list_products",
    resource == AgentCore::Gateway::"YOUR_GATEWAY_ARN"
)
when {
    principal.hasTag("groups") &&
    principal.getTag("groups") contains "ENTRA_GROUP_GUID_FOR_ENGINEERING"
};
```

**Option B: Use a custom claims mapping policy (Entra P1 or P2 licence required)**

In the Entra portal go to Enterprise Applications > your app > Single sign-on >
Attributes and Claims. Add a new claim named "team" mapped to a user attribute such as
department or a custom extension attribute. This gives you a clean string value that
matches the existing Cedar policies without modification.

**Option C: Use a Workforce Pool in IAM Identity Center**

If your organisation already federates Entra into AWS IAM Identity Center you can
pass the team attribute through the SAML assertion and then project it into the JWT
via a custom attribute mapping. Contact your identity team for the exact attribute name.

---

## Step 3: Configure the gateway with your Entra issuer

Your Entra OIDC issuer URL follows this pattern:

```
https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0
```

Pass this URL to create-gateway-oauth.py instead of the Cognito issuer:

```bash
python3 scripts/create-gateway-oauth.py \
  --region us-east-1 \
  --cognito-pool-id  NOT_USED_PASS_ANY_VALUE \
  --cognito-client-id YOUR_ENTRA_CLIENT_ID \
  --account-id       YOUR_AWS_ACCOUNT_ID \
  --prefix           mcp-demo
```

The script uses the --cognito-pool-id value only to construct the issuer URL when
creating the gateway. Because you are supplying an external IdP, edit the script and
replace the issuer construction line:

```python
# Original Cognito line (replace this):
cognito_issuer = f"https://cognito-idp.{args.region}.amazonaws.com/{args.cognito_pool_id}"

# Replace with your Entra issuer:
cognito_issuer = f"https://login.microsoftonline.com/{args.cognito_pool_id}/v2.0"
```

Now pass your Entra tenant ID as --cognito-pool-id and your Entra client ID as
--cognito-client-id. The gateway will validate every inbound JWT against the Entra
OIDC discovery document automatically.

---

## Step 4: Configure VS Code

Copy the OAuth config template to your VS Code user settings directory:

```bash
# macOS
cp vscode-config/mcp-oauth.json ~/Library/Application\ Support/Code/User/mcp.json

# Linux
cp vscode-config/mcp-oauth.json ~/.config/Code/User/mcp.json

# Windows (PowerShell)
Copy-Item vscode-config\mcp-oauth.json $env:APPDATA\Code\User\mcp.json
```

Open the copied file and fill in your values:

```json
{
  "servers": {
    "mcp-gateway": {
      "url": "YOUR_AGENTCORE_GATEWAY_URL",
      "description": "Centrally governed MCP gateway with Cedar RBAC",
      "authorization": {
        "type": "oauth",
        "clientId": "YOUR_ENTRA_CLIENT_ID",
        "authorizationEndpoint": "https://login.microsoftonline.com/YOUR_TENANT_ID/oauth2/v2.0/authorize",
        "tokenEndpoint": "https://login.microsoftonline.com/YOUR_TENANT_ID/oauth2/v2.0/token",
        "scopes": ["api://YOUR_ENTRA_CLIENT_ID/.default"],
        "redirectUri": "http://127.0.0.1:33418"
      }
    }
  }
}
```

The scopes list must contain only `api://YOUR_ENTRA_CLIENT_ID/.default`. Do NOT include
`openid`, `email`, or `profile` alongside it. Mixing OpenID scopes with an application
scope on the v2.0 endpoint causes Entra to add a legacy `resource` parameter to the
authorization request, which produces the `AADSTS9010010` error. The `.default` scope
alone requests all permissions defined on the App Registration and causes Entra to
include the necessary `openid` claims automatically in the token.

---

## Step 5: Start the server in VS Code

Open the Command Palette (Ctrl+Shift+P / Cmd+Shift+P) and run "MCP: List Servers".
Find "mcp-gateway" and click Start. A browser window opens and prompts for Entra
credentials. After sign-in VS Code automatically exchanges the authorization code for
tokens and the MCP tools become available in Copilot Chat.

If the browser opens but immediately returns an error, work through the checklist below
before anything else.

---

## Troubleshooting checklist

**"AADSTS9010010: The resource parameter provided in the request doesn't match with the requested scopes"**

This error means VS Code is sending both a `scope` parameter and a `resource` parameter in the same token request to Entra. The Entra v2.0 endpoint rejects this combination.

The root cause is the AgentCore Gateway's `/.well-known/oauth-protected-resource` response. It contains a `resource` field with the gateway URL. VS Code reads this endpoint when it first connects to any MCP server and extracts the `resource` field per RFC 9728. It then sends this value as a `resource` parameter in every token request, regardless of what scopes you have configured in `mcp.json`. There is nothing you can change in `mcp.json` alone to prevent this.

The fix is a small local proxy that intercepts the `/.well-known/oauth-protected-resource` response and removes the `resource` field before VS Code sees it.

**Step 1: Install dependencies**

```bash
pip install flask requests
```

**Step 2: Start the proxy**

```bash
GATEWAY_URL=https://YOUR_GATEWAY_ID.gateway.bedrock-agentcore.YOUR_REGION.amazonaws.com/mcp \
python3 npm-package/customer-gateway-proxy/bin/oauth-proxy.py
```

The proxy starts on `http://localhost:8080` by default. To use a different port set `PORT=9090`.

**Step 3: Point VS Code at the proxy instead of the gateway**

Update `mcp.json` to use the proxy URL:

```json
{
  "servers": {
    "mcp-gateway": {
      "url": "http://localhost:8080",
      "authorization": {
        "type": "oauth",
        "clientId": "YOUR_ENTRA_CLIENT_ID",
        "authorizationEndpoint": "https://login.microsoftonline.com/YOUR_TENANT_ID/oauth2/v2.0/authorize",
        "tokenEndpoint": "https://login.microsoftonline.com/YOUR_TENANT_ID/oauth2/v2.0/token",
        "scopes": ["api://YOUR_ENTRA_CLIENT_ID/.default"],
        "redirectUri": "http://127.0.0.1:33418"
      }
    }
  }
}
```

VS Code connects to the proxy on localhost, gets the cleaned metadata without the `resource` field, completes the Entra auth flow correctly, and the proxy forwards all tool calls to the real gateway with the Authorization header intact.

The proxy source is at `npm-package/customer-gateway-proxy/bin/oauth-proxy.py` and includes inline documentation explaining what it does and why.

If you are using a C# client or the Microsoft Dev Toolkit and are receiving a Graph API v1 token instead of your App Registration token, this means the client is requesting the Microsoft Graph resource (`https://graph.microsoft.com`) rather than your App Registration. Make sure the scope points to your App Registration (`api://YOUR_CLIENT_ID/.default`) and not to any Microsoft Graph endpoint.

**"AADSTS50011: The redirect URI does not match"**

The redirect URI VS Code actually used does not match any URI registered on the App
Registration. Open the App Registration in the portal, go to Authentication, and
confirm all three URIs are present:
  http://127.0.0.1:33418
  http://localhost:33418
  vscode://vscode.github-authentication/did-authenticate

The platform type must be "Public client / native (mobile and desktop)". If it was
added as "Web" the PKCE flow will be rejected.

**"AADSTS70011: The provided value for the input parameter 'scope' is not valid"**

Remove the "api://CLIENT_ID/.default" scope from mcp.json temporarily and test with
only "openid email profile". If that works, the App Registration does not yet have an
exposed API scope defined. Go to Expose an API in the portal, add a scope, then restore
the full scope list.

**Tools load but Cedar denies every call**

The team claim is not reaching AgentCore. To confirm, decode the access token at
jwt.io and check whether the "team" or "groups" claim is present. If it is absent,
revisit Step 2 and ensure the claim mapping is saving correctly. Remember that optional
claims sometimes require an admin consent grant before they appear in tokens.

**"Client is not enabled for OAuth2.0 flows"**

The App Registration is configured for client credentials only. Go to Authentication
in the portal and confirm that "Allow public client flows" is set to Yes and that at
least one redirect URI is registered under the public client platform.

**VS Code caches tokens between users**

When testing with multiple identities, VS Code may serve a cached token for the wrong
user. To force a fresh login, open a new VS Code window with a different profile
(File > New Window with Profile) or clear the Entra session cookie in the browser that
VS Code opened.

**The gateway returns 401 even though the JWT looks correct**

Confirm the issuer URL in create-gateway-oauth.py exactly matches the "iss" claim in
the decoded JWT. Entra tokens issued from a personal tenant use a slightly different
issuer path than multi-tenant apps. Run the following to check the gateway's current
authorizer config:

```bash
aws bedrock-agentcore-control get-gateway \
  --gateway-id YOUR_GATEWAY_ID \
  --region us-east-1 \
  --query 'authorizationConfiguration'
```

---

## Cedar policy example for Entra groups

If you chose the groups claim approach from Step 2 Option A, your Cedar policies look
like this. Run setup-cedar-oauth.py and replace the team string values with the Entra
group GUIDs for your Engineering and Support groups:

```cedar
permit(
    principal,
    action == AgentCore::Action::"products-mcp___list_products",
    resource == AgentCore::Gateway::"YOUR_GATEWAY_ARN"
)
when {
    principal.hasTag("groups") &&
    principal.getTag("groups") contains "00000000-0000-0000-0000-ENGINEERING_GUID"
};
```

If you chose Option B (custom "team" claim as a string), the existing Cedar policies in
setup-cedar-oauth.py work without modification. Only the Entra configuration changes.

---

## Related files in this repository

```
infrastructure/cloudformation/oauth-registry-stack.yaml   Cognito variant of the full OAuth stack
vscode-config/mcp-oauth.json                               VS Code mcp.json template for the OAuth path
scripts/create-gateway-oauth.py                            Creates the AgentCore gateway with CUSTOM_JWT auth
scripts/setup-cedar-oauth.py                               Creates Cedar policies and binds them to the gateway
OAUTH_DEMO.md                                              End-to-end demo walkthrough using Cognito
```
