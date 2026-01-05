#!/bin/bash

# Production Deployment Script for Larynx TTS
# Run as your normal user (ubuntu), NOT as root

set -e

echo "🚀 Starting Larynx TTS production deployment..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
APP_DIR="/var/www/larynx"
FRONTEND_DIR="$APP_DIR/frontend"
BACKEND_DIR="$APP_DIR/backend"
DOMAIN="https://larynx.drshumard.com"
BACKEND_PORT=8002

# Check we're NOT running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}ERROR: Do NOT run this script as root!${NC}"
    echo "Run as: ./deploy/deploy-script.sh"
    exit 1
fi

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

# Ensure required env vars exist
grep -q "BACKEND_PORT" $BACKEND_DIR/.env 2>/dev/null || echo "BACKEND_PORT=$BACKEND_PORT" >> $BACKEND_DIR/.env

echo -e "${GREEN}✅ Backend dependencies updated${NC}"

# Step 3: Frontend build
echo -e "${YELLOW}🏗️  Building frontend for production...${NC}"
cd $FRONTEND_DIR

yarn install
REACT_APP_BACKEND_URL=$DOMAIN yarn build

echo -e "${GREEN}✅ Frontend build complete${NC}"

# Step 4: Run cleanup script
echo -e "${YELLOW}🧹 Running audio cleanup...${NC}"
cd $BACKEND_DIR
source venv/bin/activate
python cleanup.py
deactivate

# Setup hourly cleanup cron
CRON_CMD="0 * * * * cd $BACKEND_DIR && source venv/bin/activate && python cleanup.py >> $APP_DIR/logs/cleanup.log 2>&1"
(crontab -l 2>/dev/null | grep -v "larynx.*cleanup.py" ; echo "$CRON_CMD") | crontab -
echo -e "${GREEN}✅ Cleanup configured${NC}"

# Step 5: Restart PM2 process
echo -e "${YELLOW}🔄 Restarting PM2 process...${NC}"
mkdir -p $APP_DIR/logs

if pm2 describe larynx-backend > /dev/null 2>&1; then
    pm2 restart larynx-backend
else
    echo -e "${YELLOW}Starting new PM2 process...${NC}"
    # Copy and use wrapper script
    cp $APP_DIR/deploy/start-backend.sh $BACKEND_DIR/
    chmod +x $BACKEND_DIR/start-backend.sh
    
    pm2 start $BACKEND_DIR/start-backend.sh \
        --name larynx-backend \
        --output $APP_DIR/logs/backend-out.log \
        --error $APP_DIR/logs/backend-error.log
fi

sleep 2
pm2 status
echo -e "${GREEN}✅ PM2 running${NC}"

# Step 6: Update Nginx
echo -e "${YELLOW}🔄 Updating Nginx...${NC}"
sudo cp $APP_DIR/deploy/nginx-larynx.conf /etc/nginx/sites-available/larynx
sudo ln -sf /etc/nginx/sites-available/larynx /etc/nginx/sites-enabled/larynx
sudo nginx -t && sudo systemctl reload nginx
echo -e "${GREEN}✅ Nginx updated${NC}"

# Step 7: Health check
echo -e "${YELLOW}🏥 Running health check...${NC}"
sleep 2
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:$BACKEND_PORT/api/health)

if [ "$HEALTH_CHECK" = "200" ]; then
    echo -e "${GREEN}✅ Health check passed!${NC}"
    pm2 save
else
    echo -e "${RED}❌ Health check failed (HTTP $HEALTH_CHECK)${NC}"
    echo "Check logs: pm2 logs larynx-backend"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo -e "${GREEN}   App: $DOMAIN${NC}"
echo -e "${GREEN}   API: $DOMAIN/api${NC}"
