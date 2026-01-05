// PM2 Ecosystem Configuration for Larynx TTS
// Place this in /var/www/larynx/ecosystem.config.js

module.exports = {
  apps: [
    {
      name: 'larynx-backend',
      cwd: '/var/www/larynx/backend',
      script: 'venv/bin/uvicorn',
      args: 'server:app --host 127.0.0.1 --port 8001',
      interpreter: 'none',
      env: {
        NODE_ENV: 'production',
      },
      env_file: '/var/www/larynx/backend/.env',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      error_file: '/var/www/larynx/logs/backend-error.log',
      out_file: '/var/www/larynx/logs/backend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
    },
    {
      name: 'larynx-cleanup',
      cwd: '/var/www/larynx/backend',
      script: 'venv/bin/python',
      args: 'cleanup.py',
      interpreter: 'none',
      cron_restart: '0 * * * *',  // Run every hour
      autorestart: false,
      watch: false,
      error_file: '/var/www/larynx/logs/cleanup-error.log',
      out_file: '/var/www/larynx/logs/cleanup-out.log',
    }
  ]
};
