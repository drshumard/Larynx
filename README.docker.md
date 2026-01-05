# Larynx TTS - Docker Deployment Guide

## Prerequisites

- Docker Engine 20.10+
- Docker Compose v2.0+
- ElevenLabs API Key

## Quick Start

### 1. Clone and Configure

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your ElevenLabs API key
nano .env
```

### 2. Start Services

```bash
# Development mode (frontend + backend + mongodb)
docker compose up -d

# Production mode with Nginx reverse proxy
docker compose --profile production up -d
```

### 3. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **With Nginx**: http://localhost (port 80)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Docker Network                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Nginx   │───▶│ Frontend │    │ MongoDB  │              │
│  │  (opt)   │    │  :3000   │    │  :27017  │              │
│  │   :80    │    └──────────┘    └────┬─────┘              │
│  └────┬─────┘                         │                     │
│       │         ┌──────────┐          │                     │
│       └────────▶│ Backend  │◀─────────┘                     │
│                 │  :8001   │                                │
│                 └──────────┘                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Services

| Service   | Port | Description                          |
|-----------|------|--------------------------------------|
| frontend  | 3000 | React application                    |
| backend   | 8001 | FastAPI server                       |
| mongodb   | 27017| MongoDB database (internal only)     |
| nginx     | 80   | Reverse proxy (production profile)   |

## Configuration

### Environment Variables

| Variable              | Required | Default                    | Description                    |
|-----------------------|----------|----------------------------|--------------------------------|
| ELEVENLABS_API_KEY    | Yes      | -                          | Your ElevenLabs API key        |
| ELEVENLABS_VOICE_ID   | No       | LNHBM9NjjOl44Efsdmtl       | Default voice ID               |
| ELEVENLABS_MODEL      | No       | eleven_multilingual_v2     | TTS model to use               |
| REACT_APP_BACKEND_URL | No       | http://localhost:8001      | Backend URL for frontend       |
| WEBHOOK_URL           | No       | -                          | Webhook for job notifications  |

## Commands

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# View specific service logs
docker compose logs -f backend

# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes data)
docker compose down -v

# Rebuild after code changes
docker compose build --no-cache
docker compose up -d

# Check service health
docker compose ps

# Execute command in container
docker compose exec backend bash
docker compose exec mongodb mongosh
```

## Volumes

| Volume         | Purpose                              |
|----------------|--------------------------------------|
| mongodb_data   | MongoDB database persistence         |
| audio_storage  | Generated audio files                |

## Production Deployment

### With SSL/TLS

1. Create SSL directory and add certificates:
```bash
mkdir -p nginx/ssl
cp /path/to/fullchain.pem nginx/ssl/
cp /path/to/privkey.pem nginx/ssl/
```

2. Uncomment HTTPS configuration in `nginx/nginx.conf`

3. Start with production profile:
```bash
docker compose --profile production up -d
```

### Using Let's Encrypt

Consider using [nginx-proxy](https://github.com/nginx-proxy/nginx-proxy) with [acme-companion](https://github.com/nginx-proxy/acme-companion) for automatic SSL.

## Troubleshooting

### Backend won't start
```bash
# Check logs
docker compose logs backend

# Verify MongoDB is healthy
docker compose ps mongodb

# Test MongoDB connection
docker compose exec mongodb mongosh --eval "db.adminCommand('ping')"
```

### Frontend can't connect to backend
```bash
# Verify REACT_APP_BACKEND_URL in .env
cat .env | grep REACT_APP_BACKEND_URL

# Rebuild frontend with correct URL
docker compose build frontend
docker compose up -d frontend
```

### Audio files not persisting
```bash
# Check volume
docker volume ls | grep audio_storage

# Inspect volume
docker volume inspect larynx_audio_storage
```

## Health Checks

```bash
# Backend health
curl http://localhost:8001/api/health

# Frontend (check if serving)
curl -I http://localhost:3000

# MongoDB (via backend)
curl http://localhost:8001/api/settings
```

## Scaling

For high availability, consider:

1. **MongoDB Replica Set** - For database redundancy
2. **Multiple Backend Instances** - With load balancer
3. **Redis** - For job queue management
4. **S3/Object Storage** - For audio file storage

## License

MIT License
