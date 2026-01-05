#!/bin/bash

# Complete Cleanup and Fresh Install Script for Larynx TTS
# This removes everything and starts fresh

set -e

echo "🧹 LARYNX TTS - COMPLETE CLEANUP & FRESH INSTALL"
echo "================================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

APP_DIR="/var/www/larynx"
DOMAIN="larynx.drshumard.com"
BACKEND_PORT=8002

echo ""
echo -e "${YELLOW}[1/10] Stopping and removing PM2 processes...${NC}"
pm2 delete larynx-backend 2>/dev/null || true
pm2 delete larynx-cleanup 2>/dev/null || true
pm2 save --force 2>/dev/null || true
echo -e "${GREEN}✅ PM2 cleaned${NC}"

echo ""
echo -e "${YELLOW}[2/10] Removing cron jobs...${NC}"
(crontab -l 2>/dev/null | grep -v "larynx") | crontab - 2>/dev/null || true
echo -e "${GREEN}✅ Cron cleaned${NC}"

echo ""
echo -e "${YELLOW}[3/10] Removing nginx config...${NC}"
sudo rm -f /etc/nginx/sites-enabled/larynx
sudo rm -f /etc/nginx/sites-available/larynx
sudo nginx -t && sudo systemctl reload nginx
echo -e "${GREEN}✅ Nginx cleaned${NC}"

echo ""
echo -e "${YELLOW}[4/10] Cleaning old files...${NC}"
rm -rf $APP_DIR/logs
rm -rf $APP_DIR/backend/venv
rm -rf $APP_DIR/frontend/node_modules
rm -rf $APP_DIR/frontend/build
rm -f $APP_DIR/ecosystem.config.js
echo -e "${GREEN}✅ Old files cleaned${NC}"

echo ""
echo -e "${YELLOW}[5/10] Creating directory structure...${NC}"
mkdir -p $APP_DIR/logs
mkdir -p $APP_DIR/backend/storage
echo -e "${GREEN}✅ Directories created${NC}"

echo ""
echo -e "${YELLOW}[6/10] Setting up Python virtual environment...${NC}"
cd $APP_DIR/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
echo -e "${GREEN}✅ Python venv created${NC}"

echo ""
echo -e "${YELLOW}[7/10] Configuring .env file...${NC}"
# Ensure BACKEND_PORT is in .env
if [ ! -f "$APP_DIR/backend/.env" ]; then
    echo -e "${RED}ERROR: .env file not found!${NC}"
    echo "Please create $APP_DIR/backend/.env with your settings"
    exit 1
fi

# Add BACKEND_PORT if missing
if ! grep -q "BACKEND_PORT" $APP_DIR/backend/.env; then
    echo "" >> $APP_DIR/backend/.env
    echo "BACKEND_PORT=$BACKEND_PORT" >> $APP_DIR/backend/.env
fi

# Add STORAGE_DIR if missing
if ! grep -q "STORAGE_DIR" $APP_DIR/backend/.env; then
    echo "STORAGE_DIR=$APP_DIR/backend/storage" >> $APP_DIR/backend/.env
fi

# Add APP_DOMAIN if missing
if ! grep -q "APP_DOMAIN" $APP_DIR/backend/.env; then
    echo "APP_DOMAIN=https://$DOMAIN" >> $APP_DIR/backend/.env
fi

echo -e "${GREEN}✅ .env configured${NC}"

echo ""
echo -e "${YELLOW}[8/10] Testing backend manually...${NC}"
cd $APP_DIR/backend
source venv/bin/activate

# Test if server can import
echo "Testing server import..."
python -c "from server import app; print('✅ Server imports OK')"

# Test if uvicorn works
echo "Testing uvicorn startup (5 seconds)..."
timeout 5 venv/bin/uvicorn server:app --host 127.0.0.1 --port $BACKEND_PORT &
UVICORN_PID=$!
sleep 3

# Test health endpoint
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:$BACKEND_PORT/api/health 2>/dev/null || echo "000")
kill $UVICORN_PID 2>/dev/null || true
wait $UVICORN_PID 2>/dev/null || true

if [ "$HEALTH" = "200" ]; then
    echo -e "${GREEN}✅ Backend test passed (HTTP $HEALTH)${NC}"
else
    echo -e "${RED}❌ Backend test failed (HTTP $HEALTH)${NC}"
    echo "Checking for errors..."
    cd $APP_DIR/backend
    source venv/bin/activate
    python -c "
import sys
try:
    from server import app
    print('Import OK')
except Exception as e:
    print(f'Import Error: {e}')
    sys.exit(1)
"
    exit 1
fi

deactivate

echo ""
echo -e "${YELLOW}[9/10] Building frontend...${NC}"
cd $APP_DIR/frontend
yarn install
REACT_APP_BACKEND_URL=https://$DOMAIN yarn build
echo -e "${GREEN}✅ Frontend built${NC}"

echo ""
echo -e "${YELLOW}[10/10] Setting up services...${NC}"

# Setup nginx
sudo cp $APP_DIR/deploy/nginx-larynx.conf /etc/nginx/sites-available/larynx
sudo ln -sf /etc/nginx/sites-available/larynx /etc/nginx/sites-enabled/larynx
sudo nginx -t && sudo systemctl reload nginx
echo "✅ Nginx configured"

# Setup PM2 with a simpler approach - direct command instead of ecosystem file
cd $APP_DIR/backend
source venv/bin/activate

# Start with PM2 using direct command
pm2 start venv/bin/uvicorn \
    --name larynx-backend \
    --cwd $APP_DIR/backend \
    -- server:app --host 127.0.0.1 --port $BACKEND_PORT

deactivate

# Wait and verify
sleep 3
pm2 status

# Final health check
echo ""
echo -e "${YELLOW}Final health check...${NC}"
FINAL_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:$BACKEND_PORT/api/health)

if [ "$FINAL_HEALTH" = "200" ]; then
    echo -e "${GREEN}✅ Health check passed!${NC}"
    pm2 save
    
    # Setup cron for cleanup
    CRON_CMD="0 * * * * cd $APP_DIR/backend && source venv/bin/activate && python cleanup.py >> $APP_DIR/logs/cleanup.log 2>&1"
    (crontab -l 2>/dev/null | grep -v "larynx.*cleanup.py" ; echo "$CRON_CMD") | crontab -
    
    echo ""
    echo -e "${GREEN}🎉 INSTALLATION COMPLETE!${NC}"
    echo ""
    echo "Your app is running at: https://$DOMAIN"
    echo "API endpoint: https://$DOMAIN/api"
    echo ""
    echo "Useful commands:"
    echo "  pm2 logs larynx-backend   - View logs"
    echo "  pm2 status                - Check status"  
    echo "  pm2 restart larynx-backend - Restart"
else
    echo -e "${RED}❌ Health check failed (HTTP $FINAL_HEALTH)${NC}"
    echo ""
    echo "Debug info:"
    pm2 logs larynx-backend --lines 20
    exit 1
fi
