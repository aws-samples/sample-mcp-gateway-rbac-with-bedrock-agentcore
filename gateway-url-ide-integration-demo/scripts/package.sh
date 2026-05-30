#!/bin/bash
# Package Lambda functions for deployment
# Usage: ./scripts/package.sh [S3_BUCKET]
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${PROJECT_DIR}/build"
S3_BUCKET="${1:-}"

echo "📦 Packaging Lambda functions..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Gateway Proxy
echo "  → gateway-proxy"
cd "$PROJECT_DIR/lambda/gateway-proxy"
rm -rf package
pip install -r requirements.txt -t ./package --quiet
cp lambda_function.py feature_flags.py ./package/
cd package && zip -qr "$BUILD_DIR/gateway-proxy.zip" . && cd ..
rm -rf package

# MCP Servers
for mcp in ecommerce-mcp products-mcp orders-mcp; do
  echo "  → $mcp"
  cd "$PROJECT_DIR/lambda/mcp-servers/$mcp"
  zip -qr "$BUILD_DIR/$mcp.zip" lambda_function.py
done

cd "$PROJECT_DIR"
echo ""
echo "✅ Packages created in build/:"
ls -lh "$BUILD_DIR"/*.zip

# Upload to S3 if bucket provided
if [ -n "$S3_BUCKET" ]; then
  echo ""
  echo "☁️ Uploading to s3://$S3_BUCKET/lambda/..."
  aws s3 cp "$BUILD_DIR/gateway-proxy.zip" "s3://$S3_BUCKET/lambda/gateway-proxy.zip"
  aws s3 cp "$BUILD_DIR/ecommerce-mcp.zip" "s3://$S3_BUCKET/lambda/ecommerce-mcp.zip"
  aws s3 cp "$BUILD_DIR/products-mcp.zip" "s3://$S3_BUCKET/lambda/products-mcp.zip"
  aws s3 cp "$BUILD_DIR/orders-mcp.zip" "s3://$S3_BUCKET/lambda/orders-mcp.zip"
  echo "✅ Upload complete"
fi
