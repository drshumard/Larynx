#!/bin/bash
# Larynx TTS - Simple Deploy Script
# Run as ubuntu user (not root)

set -e

APP_DIR="/var/www/larynx"
BACKEND_PORT=8002
DOMAIN="larynx.drshumard.com"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Do not run as root. Run as ubuntu user.${NC}"
    exit 1
fi

echo "🚀 Deploying Larynx TTS..."

# Pull code
cd $APP_DIR
git pull origin main

# Backend setup
echo -e "${YELLOW}Setting up backend...${NC}"
cd $APP_DIR/backend
[ ! -d "venv" ] && python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
deactivate

# Add env vars if missing
grep -q "BACKEND_PORT" .env 2>/dev/null || echo "BACKEND_PORT=$BACKEND_PORT" >> .env
grep -q "APP_DOMAIN" .env 2>/dev/null || echo "APP_DOMAIN=https://$DOMAIN" >> .env
grep -q "STORAGE_DIR" .env 2>/dev/null || echo "STORAGE_DIR=$APP_DIR/backend/storage" >> .env

# Create start script
cat > $APP_DIR/backend/start.sh << 'EOF'
#!/bin/bash
cd /var/www/larynx/backend
source venv/bin/activate
exec uvicorn server:app --host 127.0.0.1 --port 8002
EOF
chmod +x $APP_DIR/backend/start.sh

# Frontend build
echo -e "${YELLOW}Building frontend...${NC}"
cd $APP_DIR/frontend
yarn install --silent
REACT_APP_BACKEND_URL=https://$DOMAIN yarn build

# PM2
echo -e "${YELLOW}Starting PM2...${NC}"
mkdir -p $APP_DIR/logs
pm2 delete larynx-backend 2>/dev/null || true
pm2 start $APP_DIR/backend/start.sh --name larynx-backend
pm2 save

# Nginx
echo -e "${YELLOW}Configuring nginx...${NC}"
sudo cp $APP_DIR/deploy/nginx-larynx.conf /etc/nginx/sites-available/larynx
sudo ln -sf /etc/nginx/sites-available/larynx /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Health check
sleep 3
if curl -s http://127.0.0.1:$BACKEND_PORT/api/health | grep -q "healthy"; then
    echo -e "${GREEN}✅ Deployed successfully!${NC}"
    echo "App: https://$DOMAIN"
else
    echo -e "${RED}❌ Health check failed${NC}"
    pm2 logs larynx-backend --lines 20
    exit 1
fi
