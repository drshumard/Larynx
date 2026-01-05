#!/bin/bash
# Build frontend for production deployment

set -e

DOMAIN="${1:-https://larynx.drshumard.com}"

echo "Building frontend for domain: $DOMAIN"

cd /app/frontend

# Set backend URL for production
export REACT_APP_BACKEND_URL="$DOMAIN"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    yarn install
fi

# Build
yarn build

echo ""
echo "Build complete! Files are in /app/frontend/build/"
echo "Upload this folder to /var/www/larynx/frontend/build/ on your server"
