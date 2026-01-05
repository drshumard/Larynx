#!/bin/bash
# Larynx TTS Production Installation Script
# Run as root or with sudo on Ubuntu/Debian

set -e

echo "========================================"
echo "Larynx TTS Production Installation"
echo "========================================"

# Configuration
INSTALL_DIR="/var/www/larynx"
DOMAIN="larynx.drshumard.com"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./install.sh)"
    exit 1
fi

echo ""
echo "[1/8] Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx ffmpeg curl

echo ""
echo "[2/8] Creating directory structure..."
mkdir -p $INSTALL_DIR/backend/storage
mkdir -p $INSTALL_DIR/frontend
chown -R www-data:www-data $INSTALL_DIR

echo ""
echo "[3/8] Setting up Python virtual environment..."
cd $INSTALL_DIR/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

echo ""
echo "[4/8] Copying application files..."
echo "Please copy your application files to:"
echo "  Backend: $INSTALL_DIR/backend/"
echo "  Frontend build: $INSTALL_DIR/frontend/build/"
echo ""
read -p "Press Enter when files are copied..."

echo ""
echo "[5/8] Installing Python dependencies..."
cd $INSTALL_DIR/backend
source venv/bin/activate
pip install -r requirements.txt

echo ""
echo "[6/8] Setting up systemd services..."
cp /app/deploy/larynx-backend.service /etc/systemd/system/
cp /app/deploy/larynx-cleanup.service /etc/systemd/system/
cp /app/deploy/larynx-cleanup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable larynx-backend
systemctl enable larynx-cleanup.timer

echo ""
echo "[7/8] Setting up Nginx..."
cp /app/deploy/nginx-larynx.conf /etc/nginx/sites-available/larynx
ln -sf /etc/nginx/sites-available/larynx /etc/nginx/sites-enabled/
nginx -t

echo ""
echo "[8/8] Setting up SSL certificate..."
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || echo "SSL setup may need manual intervention"

echo ""
echo "========================================"
echo "Installation complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit /var/www/larynx/backend/.env with your settings"
echo "2. Start the backend: systemctl start larynx-backend"
echo "3. Start cleanup timer: systemctl start larynx-cleanup.timer"
echo "4. Reload Nginx: systemctl reload nginx"
echo ""
echo "Check status:"
echo "  systemctl status larynx-backend"
echo "  systemctl status larynx-cleanup.timer"
echo "  journalctl -u larynx-backend -f"
echo ""
