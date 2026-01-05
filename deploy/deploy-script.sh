#!/bin/bash

# Production Deployment Script for Larynx TTS
# Run this on your Lightsail server after git push

set -e  # Exit on any error

echo "🚀 Starting Larynx TTS production deployment..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/var/www/larynx"
FRONTEND_DIR="$APP_DIR/frontend"
BACKEND_DIR="$APP_DIR/backend"
DOMAIN="https://larynx.drshumard.com"

# Step 1: Pull latest code
echo -e "${YELLOW}📥 Pulling latest code from repository...${NC}"
cd $APP_DIR
git pull origin main

# Step 2: Backend updates
echo -e "${YELLOW}🔧 Updating backend...${NC}"
cd $BACKEND_DIR

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Ensure BACKEND_PORT is set in .env
if ! grep -q "BACKEND_PORT" $BACKEND_DIR/.env 2>/dev/null; then
    echo "BACKEND_PORT=8002" >> $BACKEND_DIR/.env
    echo -e "${YELLOW}Added BACKEND_PORT=8002 to .env${NC}"
fi

echo -e "${GREEN}✅ Backend dependencies updated${NC}"

# Step 3: Frontend build
echo -e "${YELLOW}🏗️  Building frontend for production...${NC}"
cd $FRONTEND_DIR

# Install dependencies
yarn install

# Build with production backend URL
REACT_APP_BACKEND_URL=$DOMAIN yarn build

echo -e "${GREEN}✅ Frontend build complete${NC}"

# Step 4: Run cleanup script to free disk space
echo -e "${YELLOW}🧹 Running audio cleanup...${NC}"
cd $BACKEND_DIR
source venv/bin/activate
python cleanup.py
deactivate

# Setup hourly cleanup cron job if not exists
CRON_CMD="0 * * * * cd $BACKEND_DIR && source venv/bin/activate && python cleanup.py >> $APP_DIR/logs/cleanup.log 2>&1"
(crontab -l 2>/dev/null | grep -v "larynx.*cleanup.py" ; echo "$CRON_CMD") | crontab -
echo -e "${GREEN}✅ Cleanup cron job configured${NC}"

# Step 5: Restart PM2 processes
echo -e "${YELLOW}🔄 Restarting PM2 processes...${NC}"
cd $APP_DIR

# Ensure logs directory exists
mkdir -p $APP_DIR/logs

# Check if process exists, restart or start fresh
if pm2 describe larynx-backend > /dev/null 2>&1; then
    pm2 restart larynx-backend
else
    echo -e "${YELLOW}Starting PM2 process...${NC}"
    cd $BACKEND_DIR
    source venv/bin/activate
    pm2 start venv/bin/uvicorn \
        --name larynx-backend \
        --cwd $BACKEND_DIR \
        -- server:app --host 127.0.0.1 --port 8002
    deactivate
fi

sleep 2
pm2 status
echo -e "${GREEN}✅ PM2 processes running${NC}"

# Step 6: Update and reload Nginx
echo -e "${YELLOW}🔄 Updating Nginx configuration...${NC}"
sudo cp $APP_DIR/deploy/nginx-larynx.conf /etc/nginx/sites-available/larynx
sudo nginx -t && sudo systemctl reload nginx

echo -e "${GREEN}✅ Nginx updated${NC}"

# Step 7: Health check
echo -e "${YELLOW}🏥 Running health check...${NC}"
sleep 3
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8002/api/health)

if [ "$HEALTH_CHECK" = "200" ]; then
    echo -e "${GREEN}✅ Health check passed!${NC}"
else
    echo -e "${RED}❌ Health check failed (HTTP $HEALTH_CHECK)${NC}"
    echo -e "${YELLOW}Check logs: pm2 logs larynx-backend${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo -e "${GREEN}   App URL: $DOMAIN${NC}"
echo -e "${GREEN}   API URL: $DOMAIN/api${NC}"
echo ""
echo "Useful commands:"
echo "  pm2 logs larynx-backend    - View backend logs"
echo "  pm2 status                 - Check process status"
echo "  pm2 restart larynx-backend - Restart backend"
