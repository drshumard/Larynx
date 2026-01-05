#!/bin/bash
# Wrapper script to run uvicorn for PM2
cd /var/www/larynx/backend
source venv/bin/activate
exec uvicorn server:app --host 127.0.0.1 --port 8002
