#!/usr/bin/env python3
"""
oauth-proxy.py — Local OAuth metadata proxy for AgentCore Gateway + Entra ID

PROBLEM
-------
The AgentCore Gateway's /.well-known/oauth-protected-resource response contains
a "resource" field (RFC 9728).  VS Code and MSAL-based clients read this field
and include it as a legacy "resource" parameter in every token request to Entra.
The Entra v2.0 token endpoint rejects requests that contain both "scope" and
"resource", returning AADSTS9010010.

SOLUTION
--------
This proxy sits between VS Code and the AgentCore Gateway.  It:
  1. Intercepts the /.well-known/oauth-protected-resource request and strips
     the "resource" field before returning it to VS Code.
  2. Passes all other requests (MCP tool calls) through unchanged.

VS Code never sees the "resource" field, so it never adds the "resource"
parameter to the Entra token request.

USAGE
-----
1. Install dependencies (one-time):
   pip install flask requests

2. Start the proxy (replace with your actual gateway URL and port):
   GATEWAY_URL=https://<id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp \
   python3 oauth-proxy.py

   The proxy listens on http://localhost:8080 by default.
   Override the port: PORT=9090 python3 oauth-proxy.py

3. Point VS Code at the proxy instead of the gateway directly.
   In mcp.json, set "url" to http://localhost:8080  (not the gateway URL).

EXAMPLE mcp.json
----------------
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
"""

import json
import os
import sys

try:
    import requests
    from flask import Flask, request, Response
except ImportError:
    print("Missing dependencies. Run: pip install flask requests", file=sys.stderr)
    sys.exit(1)

GATEWAY_URL = os.environ.get("GATEWAY_URL", "").rstrip("/")
PORT = int(os.environ.get("PORT", "8080"))

if not GATEWAY_URL:
    print(
        "ERROR: GATEWAY_URL environment variable is required.\n"
        "Example:\n"
        "  GATEWAY_URL=https://<id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp \\\n"
        "  python3 oauth-proxy.py",
        file=sys.stderr,
    )
    sys.exit(1)

# Derive the base URL (everything before /mcp) for well-known endpoint lookups
GATEWAY_BASE = GATEWAY_URL.rstrip("/mcp").rstrip("/")

app = Flask(__name__)


@app.route("/.well-known/oauth-protected-resource", methods=["GET"])
def strip_resource_field():
    """
    Fetch the gateway's OAuth Protected Resource metadata, remove the
    "resource" field that causes AADSTS9010010, and return the cleaned
    response to VS Code.
    """
    upstream_url = f"{GATEWAY_BASE}/.well-known/oauth-protected-resource"
    try:
        resp = requests.get(upstream_url, timeout=10)
        metadata = resp.json()
    except Exception as exc:
        return Response(
            json.dumps({"error": f"Could not reach gateway: {exc}"}),
            status=502,
            mimetype="application/json",
        )

    # Remove the "resource" field — this is what triggers AADSTS9010010
    metadata.pop("resource", None)

    return Response(
        json.dumps(metadata),
        status=200,
        mimetype="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-store",
        },
    )


@app.route("/.well-known/<path:subpath>", methods=["GET"])
def forward_well_known(subpath):
    """Forward any other well-known requests unchanged."""
    upstream_url = f"{GATEWAY_BASE}/.well-known/{subpath}"
    try:
        resp = requests.get(upstream_url, timeout=10)
        return Response(resp.content, status=resp.status_code, mimetype=resp.headers.get("Content-Type", "application/json"))
    except Exception as exc:
        return Response(json.dumps({"error": str(exc)}), status=502, mimetype="application/json")


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def forward_all(path):
    """
    Forward all other requests (MCP tool calls, etc.) to the gateway unchanged.
    The Authorization header from VS Code is forwarded as-is so the gateway
    can validate the Entra JWT normally.
    """
    target = f"{GATEWAY_URL}/{path}".rstrip("/") if path else GATEWAY_URL

    headers = {
        k: v
        for k, v in request.headers
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }

    try:
        resp = requests.request(
            method=request.method,
            url=target,
            headers=headers,
            data=request.get_data(),
            params=request.args,
            timeout=120,
            allow_redirects=False,
        )
        return Response(
            resp.content,
            status=resp.status_code,
            headers={
                k: v
                for k, v in resp.headers.items()
                if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")
            },
        )
    except Exception as exc:
        return Response(
            json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(exc)}}),
            status=502,
            mimetype="application/json",
        )


if __name__ == "__main__":
    print(f"OAuth proxy starting on http://localhost:{PORT}")
    print(f"Forwarding to: {GATEWAY_URL}")
    print(f"Stripping 'resource' field from /.well-known/oauth-protected-resource")
    print()
    print("Point VS Code mcp.json at: http://localhost:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=False)
