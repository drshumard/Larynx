// PM2 Ecosystem Configuration for Larynx TTS
// Place this in /var/www/larynx/ecosystem.config.js

const path = require('path');
const fs = require('fs');

// Load .env file manually for PM2
function loadEnv(envPath) {
  const env = {};
  if (fs.existsSync(envPath)) {
    const content = fs.readFileSync(envPath, 'utf8');
    content.split('\n').forEach(line => {
      const match = line.match(/^([^#=]+)=(.*)$/);
      if (match) {
        const key = match[1].trim();
        let value = match[2].trim();
        // Remove surrounding quotes if present
        if ((value.startsWith('"') && value.endsWith('"')) || 
            (value.startsWith("'") && value.endsWith("'"))) {
          value = value.slice(1, -1);
        }
        env[key] = value;
      }
    });
  }
  return env;
}

const envVars = loadEnv('/var/www/larynx/backend/.env');

module.exports = {
  apps: [
    {
      name: 'larynx-backend',
      cwd: '/var/www/larynx/backend',
      script: 'venv/bin/uvicorn',
      args: 'server:app --host 127.0.0.1 --port 8001',
      interpreter: 'none',
      env: {
        ...envVars,
        NODE_ENV: 'production',
      },
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      error_file: '/var/www/larynx/logs/backend-error.log',
      out_file: '/var/www/larynx/logs/backend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
    }
  ]
};
