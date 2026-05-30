#!/bin/bash
# MCP Proxy wrapper - calls Python implementation
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/proxy.py"
