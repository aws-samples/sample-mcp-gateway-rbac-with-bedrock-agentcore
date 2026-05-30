#!/usr/bin/env python3
import sys
import json
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import urllib3
from urllib.parse import urlparse

# Set GATEWAY_URL to your deployed AgentCore Gateway endpoint.
# Format: https://<GATEWAY_ID>.gateway.bedrock-agentcore.<REGION>.amazonaws.com/mcp
# You can also set this via the GATEWAY_URL environment variable.
import os
GATEWAY_URL = os.environ.get(
    "GATEWAY_URL",
    "<YOUR_GATEWAY_URL>"  # Replace with your gateway URL or set the GATEWAY_URL env var
)

def forward_request(url: str, payload: str):
    parsed = urlparse(url)
    hostname = parsed.netloc

    request_headers = {
        'Content-Type': 'application/json',
        'Host': hostname,
    }

    aws_request = AWSRequest(method='POST', url=url, data=payload, headers=request_headers)
    credentials = boto3.Session().get_credentials()
    SigV4Auth(credentials, 'bedrock-agentcore', 'us-east-1').add_auth(aws_request)

    http = urllib3.PoolManager()
    response = http.request('POST', url, body=payload, headers=dict(aws_request.headers), timeout=120.0)
    return response.data.decode('utf-8')

def main():
    for line in sys.stdin:
        try:
            message = line.strip()
            if not message:
                continue

            response = forward_request(GATEWAY_URL, message)
            sys.stdout.write(response + '\n')
            sys.stdout.flush()
        except Exception as e:
            error = json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32000, "message": str(e)}
            })
            sys.stdout.write(error + '\n')
            sys.stdout.flush()

if __name__ == "__main__":
    main()
