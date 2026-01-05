# Larynx TTS - Production Deployment Guide (PM2)

## Server Requirements

### Minimum Specs
- **CPU:** 1 vCPU
- **RAM:** 1 GB
- **Storage:** 10 GB (audio files auto-cleaned after 48h)
- **OS:** Ubuntu 20.04+ or Debian 11+

### Why So Lightweight?
The heavy lifting (TTS processing) happens on ElevenLabs servers. Your server only:
- Serves the React frontend (static files via Nginx)
- Runs FastAPI backend (managed by PM2)
- Merges audio chunks with ffmpeg (brief CPU spikes)
- Stores temporary audio files

**✅ You can run this alongside your existing site on the same VPS.**

---

## Quick Start

### Prerequisites on Server
```bash
# Install Node.js 20.x, Yarn, PM2
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs python3 python3-pip python3-venv nginx certbot python3-certbot-nginx ffmpeg git
sudo npm install -g yarn pm2
```

### First Time Setup

```bash
# 1. Clone repo to /var/www/larynx
git clone YOUR_REPO_URL /var/www/larynx
cd /var/www/larynx

# 2. Run initial setup script
chmod +x deploy/*.sh
./deploy/initial-setup.sh

# 3. Edit .env with your settings
nano /var/www/larynx/backend/.env

# 4. Run first deployment
./deploy/deploy-script.sh

# 5. Save PM2 config for auto-restart on reboot
pm2 save
```

### Subsequent Deployments

After pushing code to git:
```bash
cd /var/www/larynx
./deploy/deploy-script.sh
```

---

## Configuration

### Environment Variables (`.env`)

```env
# Required
ELEVENLABS_API_KEY=sk_your_key_here
MONGO_URL=mongodb://localhost:27017
DB_NAME=larynx_tts

# Webhook - receives POST on job completion
WEBHOOK_URL=https://your-n8n-or-webhook.com/endpoint

# App domain for webhook URLs
APP_DOMAIN=https://larynx.drshumard.com

# Storage & Cleanup
STORAGE_DIR=/var/www/larynx/backend/storage
AUTO_CLEANUP_HOURS=48
```

### Webhook Payload

When a job completes, a POST request is sent to `WEBHOOK_URL`:

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

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/jobs` | GET | List all jobs |
| `/api/jobs` | POST | Create new job |
| `/api/jobs/{id}` | GET | Get job status |
| `/api/jobs/{id}/download` | GET | Download audio file |
| `/api/jobs/{id}/details` | GET | Full job details |
| `/api/settings` | GET/PUT | TTS settings |

### Create Job via API

```bash
curl -X POST https://larynx.drshumard.com/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Audio",
    "text": "Your long text content here..."
  }'
```

Response:
```json
{
  "id": "abc123",
  "name": "My Audio",
  "status": "queued",
  "message": "Job created and queued for processing"
}
```

---

## PM2 Management

```bash
# View all processes
pm2 status

# View logs
pm2 logs larynx-backend
pm2 logs larynx-cleanup

# Restart backend
pm2 restart larynx-backend

# Stop all
pm2 stop all

# Start from ecosystem file
pm2 start ecosystem.config.js

# Monitor resources
pm2 monit

# Save current config (for reboot survival)
pm2 save
```

---

## Directory Structure

```
/var/www/larynx/
├── backend/
│   ├── server.py           # FastAPI application
│   ├── cleanup.py          # Audio cleanup script
│   ├── requirements.txt
│   ├── .env                # Environment config
│   ├── venv/               # Python virtual environment
│   └── storage/            # Audio files (auto-cleaned)
├── frontend/
│   ├── src/
│   ├── build/              # Production build (served by Nginx)
│   └── package.json
├── deploy/
│   ├── deploy-script.sh    # Main deployment script
│   ├── initial-setup.sh    # First-time setup
│   ├── nginx-larynx.conf   # Nginx config
│   └── ecosystem.config.js # PM2 config
├── logs/                   # PM2 log files
└── ecosystem.config.js     # PM2 config (symlink or copy)
```

---

## Troubleshooting

### Backend won't start
```bash
# Check PM2 logs
pm2 logs larynx-backend --lines 50

# Test manually
cd /var/www/larynx/backend
source venv/bin/activate
python -c "from server import app; print('OK')"
uvicorn server:app --host 127.0.0.1 --port 8001
```

### 502 Bad Gateway
```bash
# Check if PM2 process is running
pm2 status

# Check Nginx error log
sudo tail -f /var/log/nginx/larynx.error.log
```

### Audio files filling disk
```bash
# Check storage size
du -sh /var/www/larynx/backend/storage/

# Manual cleanup
cd /var/www/larynx/backend
source venv/bin/activate
python cleanup.py
```

### Webhook not firing
```bash
# Check WEBHOOK_URL in .env
grep WEBHOOK_URL /var/www/larynx/backend/.env

# Check logs for webhook attempts
pm2 logs larynx-backend | grep -i webhook
```

---

## SSL Certificate Renewal

Certbot auto-renews. To test:
```bash
sudo certbot renew --dry-run
```

---

## Backup & Recovery

### What to backup:
- `/var/www/larynx/backend/.env` (configuration)
- MongoDB database (if local)

### What NOT to backup:
- `/var/www/larynx/backend/storage/` (temporary audio files)
- `node_modules/`, `venv/` (recreated on deploy)
