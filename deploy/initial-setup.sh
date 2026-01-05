#!/bin/bash

# Initial Setup Script for Larynx TTS
# Run this ONCE on a fresh server before first deployment

set -e

echo "🔧 Larynx TTS Initial Server Setup"
echo "==================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

DOMAIN="larynx.drshumard.com"
APP_DIR="/var/www/larynx"

# Check if running as appropriate user
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}Running as root. Some commands will use sudo for www-data operations.${NC}"
fi

# Step 1: Install system dependencies
echo -e "${YELLOW}[1/8] Installing system dependencies...${NC}"
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx ffmpeg curl git

# Step 2: Install Node.js and Yarn (if not installed)
echo -e "${YELLOW}[2/8] Checking Node.js and Yarn...${NC}"
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
fi

if ! command -v yarn &> /dev/null; then
    sudo npm install -g yarn
fi

if ! command -v pm2 &> /dev/null; then
    sudo npm install -g pm2
fi

echo "Node: $(node --version)"
echo "Yarn: $(yarn --version)"
echo "PM2: $(pm2 --version)"

# Step 3: Create directory structure
echo -e "${YELLOW}[3/8] Creating directory structure...${NC}"
sudo mkdir -p $APP_DIR/backend/storage
sudo mkdir -p $APP_DIR/frontend
sudo mkdir -p $APP_DIR/logs
sudo chown -R $USER:$USER $APP_DIR

# Step 4: Clone repository (or set up for git pull)
echo -e "${YELLOW}[4/8] Setting up repository...${NC}"
if [ ! -d "$APP_DIR/.git" ]; then
    echo "Please clone your repository to $APP_DIR"
    echo "Example: git clone your-repo-url $APP_DIR"
    read -p "Press Enter after cloning, or Ctrl+C to exit and clone manually..."
fi

# Step 5: Setup Python virtual environment
echo -e "${YELLOW}[5/8] Setting up Python environment...${NC}"
cd $APP_DIR/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Step 6: Create .env file
echo -e "${YELLOW}[6/8] Setting up environment file...${NC}"
if [ ! -f "$APP_DIR/backend/.env" ]; then
    cp $APP_DIR/deploy/production.env.example $APP_DIR/backend/.env
    echo -e "${YELLOW}⚠️  Please edit $APP_DIR/backend/.env with your settings!${NC}"
    echo "Required: ELEVENLABS_API_KEY, MONGO_URL, WEBHOOK_URL"
    read -p "Press Enter after editing .env..."
fi

# Step 7: Setup Nginx
echo -e "${YELLOW}[7/8] Setting up Nginx...${NC}"
sudo cp $APP_DIR/deploy/nginx-larynx.conf /etc/nginx/sites-available/larynx
sudo ln -sf /etc/nginx/sites-available/larynx /etc/nginx/sites-enabled/

# Comment out SSL lines initially (certbot will add them)
sudo sed -i 's/listen 443 ssl/#listen 443 ssl/' /etc/nginx/sites-available/larynx
sudo sed -i 's/ssl_certificate/#ssl_certificate/' /etc/nginx/sites-available/larynx
sudo sed -i 's/return 301 https/#return 301 https/' /etc/nginx/sites-available/larynx

sudo nginx -t && sudo systemctl reload nginx

# Step 8: Setup SSL
echo -e "${YELLOW}[8/8] Setting up SSL certificate...${NC}"
echo "Make sure DNS is pointing to this server first!"
read -p "Press Enter to continue with SSL setup (or Ctrl+C to skip)..."
sudo certbot --nginx -d $DOMAIN

# Setup PM2 to start on boot
echo -e "${YELLOW}Setting up PM2 startup...${NC}"
pm2 startup
echo "Run the command above if prompted"

echo ""
echo -e "${GREEN}✅ Initial setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Edit /var/www/larynx/backend/.env with your settings"
echo "2. Run the deploy script: ./deploy/deploy-script.sh"
echo ""
echo "After first deploy, save PM2 config:"
echo "  pm2 save"
