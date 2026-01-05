# Larynx TTS - Production Deployment Guide

## Server Requirements

### Minimum Specs
- **CPU:** 1 vCPU
- **RAM:** 1 GB
- **Storage:** 10 GB (audio files are auto-cleaned after 48h)
- **OS:** Ubuntu 20.04+ or Debian 11+

### Why So Lightweight?
The heavy lifting (TTS processing) happens on ElevenLabs servers. Your server only:
- Serves the React frontend (static files)
- Runs FastAPI backend (lightweight)
- Merges audio chunks with ffmpeg (brief CPU spikes)
- Stores temporary audio files

**You can likely run this alongside your existing site on the same VPS.**

---

## Quick Deployment

### 1. Prepare Your Server

```bash
# SSH into your Lightsail instance
ssh ubuntu@your-server-ip

# Install dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx ffmpeg git
```

### 2. Upload Application Files

```bash
# Create directory
sudo mkdir -p /var/www/larynx
sudo chown $USER:$USER /var/www/larynx

# Option A: Clone from git
cd /var/www/larynx
git clone your-repo-url .

# Option B: Upload via SCP
scp -r ./backend user@server:/var/www/larynx/
scp -r ./frontend/build user@server:/var/www/larynx/frontend/
```

### 3. Build Frontend (if not pre-built)

```bash
# On your local machine
cd frontend
yarn install
REACT_APP_BACKEND_URL=https://larynx.drshumard.com yarn build

# Upload build folder to server
scp -r build/ user@server:/var/www/larynx/frontend/
```

### 4. Setup Backend

```bash
cd /var/www/larynx/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Configure environment
cp /var/www/larynx/deploy/production.env.example .env
nano .env  # Edit with your settings

# Create storage directory
mkdir -p storage
chmod 755 storage
```

### 5. Configure .env

```bash
nano /var/www/larynx/backend/.env
```

**Required settings:**
```env
ELEVENLABS_API_KEY=your_key_here
MONGO_URL=mongodb://localhost:27017  # or MongoDB Atlas URL
DB_NAME=larynx_tts
WEBHOOK_URL=https://your-webhook.com/endpoint
APP_DOMAIN=https://larynx.drshumard.com
STORAGE_DIR=/var/www/larynx/backend/storage
AUTO_CLEANUP_HOURS=48
```

### 6. Setup Systemd Services

```bash
# Copy service files
sudo cp /var/www/larynx/deploy/larynx-backend.service /etc/systemd/system/
sudo cp /var/www/larynx/deploy/larynx-cleanup.service /etc/systemd/system/
sudo cp /var/www/larynx/deploy/larynx-cleanup.timer /etc/systemd/system/

# Reload and enable
sudo systemctl daemon-reload
sudo systemctl enable larynx-backend
sudo systemctl enable larynx-cleanup.timer

# Start services
sudo systemctl start larynx-backend
sudo systemctl start larynx-cleanup.timer
```

### 7. Configure Nginx

```bash
# Copy nginx config
sudo cp /var/www/larynx/deploy/nginx-larynx.conf /etc/nginx/sites-available/larynx

# Enable site
sudo ln -s /etc/nginx/sites-available/larynx /etc/nginx/sites-enabled/

# Test config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 8. Setup SSL with Let's Encrypt

```bash
# Get SSL certificate
sudo certbot --nginx -d larynx.drshumard.com

# Auto-renewal is configured automatically
```

### 9. DNS Configuration

Add an A record in your DNS settings:
```
Type: A
Name: larynx
Value: your-server-ip
TTL: 300
```

---

## API Endpoints

Once deployed, your API is available at:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `https://larynx.drshumard.com/api/health` | GET | Health check |
| `https://larynx.drshumard.com/api/jobs` | GET | List all jobs |
| `https://larynx.drshumard.com/api/jobs` | POST | Create new job |
| `https://larynx.drshumard.com/api/jobs/{id}` | GET | Get job status |
| `https://larynx.drshumard.com/api/jobs/{id}/download` | GET | Download audio |
| `https://larynx.drshumard.com/api/settings` | GET/PUT | TTS settings |

### Example: Create Job via API

```bash
curl -X POST https://larynx.drshumard.com/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Audio Job",
    "text": "Your long text content here..."
  }'
```

### Webhook Payload

When a job completes, a POST request is sent to your WEBHOOK_URL:

```json
{
  "jobId": "abc123",
  "name": "My Audio Job",
  "audioUrl": "https://larynx.drshumard.com/api/jobs/abc123/download",
  "status": "completed",
  "textLength": 5000,
  "chunkCount": 2,
  "completedAt": "2024-01-15T10:30:00Z"
}
```

---

## Management Commands

```bash
# View backend logs
sudo journalctl -u larynx-backend -f

# Restart backend
sudo systemctl restart larynx-backend

# Check cleanup timer
sudo systemctl status larynx-cleanup.timer

# Run cleanup manually
sudo -u www-data /var/www/larynx/backend/venv/bin/python /var/www/larynx/backend/cleanup.py

# Check disk usage
du -sh /var/www/larynx/backend/storage/
```

---

## Troubleshooting

### Backend won't start
```bash
# Check logs
sudo journalctl -u larynx-backend -n 50

# Test manually
cd /var/www/larynx/backend
source venv/bin/activate
python -c "from server import app; print('OK')"
```

### 502 Bad Gateway
```bash
# Check if backend is running
sudo systemctl status larynx-backend

# Check nginx error log
sudo tail -f /var/log/nginx/larynx.error.log
```

### MongoDB connection issues
```bash
# Test connection
cd /var/www/larynx/backend
source venv/bin/activate
python -c "from motor.motor_asyncio import AsyncIOMotorClient; import os; print(os.environ.get('MONGO_URL'))"
```

---

## MongoDB Options

### Option 1: Local MongoDB (Simple)
```bash
sudo apt install -y mongodb
sudo systemctl enable mongodb
sudo systemctl start mongodb
```
Use: `MONGO_URL=mongodb://localhost:27017`

### Option 2: MongoDB Atlas (Recommended)
1. Create free cluster at https://cloud.mongodb.com
2. Get connection string
3. Use: `MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net/`

---

## Running Both Sites on Same VPS

Yes, you can run Larynx alongside your existing site:

1. Each site has its own Nginx server block
2. Larynx backend runs on port 8001 internally
3. Your other site likely uses different ports

**Resource usage estimate:**
- Idle: ~50MB RAM, minimal CPU
- Processing job: ~100-200MB RAM, brief CPU for ffmpeg
- Peak: Depends on concurrent jobs (each job is independent)

**Recommendation:** Start with your current VPS. Monitor with `htop`. Upgrade only if needed.
