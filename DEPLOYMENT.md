# YouTube API Handler - Production Deployment Guide

This guide covers deploying the YouTube API Handler to production environments with proper security, monitoring, and performance optimizations.

## 📋 Prerequisites

- Python 3.9+ or Docker
- YouTube Data API v3 key
- Linux server (Ubuntu 20.04+ recommended)
- Minimum 2GB RAM, 2 CPU cores
- Root or sudo access

## 🚀 Quick Start (Docker - Recommended)

### 1. Clone and Configure
```bash
git clone <your-repo>
cd youtube-api-handler
cp production.env.example production.env
# Edit production.env with your settings
```

### 2. Deploy with Docker Compose
```bash
# Build and start services
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f youtube-api
```

### 3. Verify Deployment
```bash
# Health check
curl http://localhost:8000/health

# API test (replace with your API key)
curl "http://localhost:8000/api/channel/@MrBeast?api_key=YOUR_API_KEY"
```

## 🔧 Manual Deployment (Linux Server)

### 1. System Preparation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-pip python3-venv nginx supervisor

# Create app user
sudo useradd --system --shell /bin/false --home /opt/youtube-api youtube-api
sudo mkdir -p /opt/youtube-api
sudo chown youtube-api:youtube-api /opt/youtube-api
```

### 2. Application Setup
```bash
# Switch to app directory
cd /opt/youtube-api

# Clone repository
sudo -u youtube-api git clone <your-repo> .

# Setup virtual environment
sudo -u youtube-api python3 -m venv venv
sudo -u youtube-api ./venv/bin/pip install -r requirements.txt

# Configure environment
sudo cp production.env.example production.env
sudo nano production.env  # Edit with your settings
sudo chown youtube-api:youtube-api production.env
sudo chmod 600 production.env
```

### 3. Systemd Service Setup
```bash
# Copy service file
sudo cp youtube-api.service /etc/systemd/system/

# Update paths in service file if needed
sudo nano /etc/systemd/system/youtube-api.service

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable youtube-api
sudo systemctl start youtube-api

# Check status
sudo systemctl status youtube-api
```

### 4. Nginx Reverse Proxy (Optional)
```bash
# Create Nginx configuration
sudo tee /etc/nginx/sites-available/youtube-api << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60;
        proxy_send_timeout 60;
        proxy_read_timeout 60;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/youtube-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | `production` | Environment mode |
| `FLASK_DEBUG` | `False` | Debug mode |
| `WORKERS` | `4` | Number of Gunicorn workers |
| `WORKER_CLASS` | `gevent` | Worker class for async processing |
| `TIMEOUT` | `120` | Request timeout in seconds |
| `RATE_LIMIT_DEFAULT` | `1000 per hour` | Default rate limit |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `ENABLE_METRICS` | `True` | Enable Prometheus metrics |

### Security Configuration

```bash
# Generate secure API key
python3 -c "import secrets; print('API_AUTH_KEY=' + secrets.token_urlsafe(32))"

# Generate secret key
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
```

### YouTube API Key Rotation (New Feature)

Configure multiple YouTube API keys to maximize rate limits:

```bash
# Method 1: Numbered keys (recommended)
YOUTUBE_API_KEY_1=your_youtube_api_key_1_here
YOUTUBE_API_KEY_2=your_youtube_api_key_2_here
YOUTUBE_API_KEY_3=your_youtube_api_key_3_here

# Method 2: Comma-separated list
YOUTUBE_API_KEYS=key1,key2,key3,key4,key5

# Rotation configuration
YOUTUBE_API_KEY_ROTATION_STRATEGY=round_robin  # round_robin, least_used, random
YOUTUBE_API_KEY_DAILY_QUOTA=10000
YOUTUBE_API_KEY_HOURLY_QUOTA=1000
```

**Benefits:**
- **5x Rate Limits**: 5 keys = 50,000 requests/day instead of 10,000
- **Automatic Failover**: System switches to available keys when others hit limits
- **Usage Monitoring**: Track quota usage per key via `/api/keys/stats`

See `API_KEY_ROTATION.md` for detailed configuration guide.

### Performance Tuning

#### For 2GB RAM Server:
```bash
WORKERS=2
WORKER_CONNECTIONS=500
MAX_REQUESTS=500
```

#### For 4GB RAM Server:
```bash
WORKERS=4
WORKER_CONNECTIONS=1000
MAX_REQUESTS=1000
```

#### For 8GB+ RAM Server:
```bash
WORKERS=8
WORKER_CONNECTIONS=2000
MAX_REQUESTS=2000
```

## 📊 Monitoring

### Health Checks

| Endpoint | Purpose | Authentication |
|----------|---------|----------------|
| `/health` | Application health | None |
| `/ready` | Kubernetes readiness | None |
| `/live` | Kubernetes liveness | None |
| `/metrics` | Prometheus metrics | None |
| `/api/stats` | Detailed statistics | Required |

### Log Monitoring

```bash
# View application logs
sudo journalctl -u youtube-api -f

# View access logs
docker logs -f youtube-api

# View error logs
docker logs -f --stderr youtube-api
```

### Metrics Collection

The API exposes Prometheus metrics at `/metrics`:
- HTTP request counts and durations
- Cache hit/miss rates
- System resource usage
- Custom business metrics

## 🔒 Security

### Firewall Configuration
```bash
# Allow only necessary ports
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

### SSL/TLS Setup (Let's Encrypt)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### API Key Management
- Use strong, randomly generated API keys
- Rotate keys regularly
- Monitor usage patterns
- Implement IP whitelisting if needed

## 🔄 Maintenance

### Updates
```bash
# Stop service
sudo systemctl stop youtube-api

# Update code
cd /opt/youtube-api
sudo -u youtube-api git pull

# Update dependencies
sudo -u youtube-api ./venv/bin/pip install -r requirements.txt

# Start service
sudo systemctl start youtube-api
```

### Log Rotation
Logs are output to console and stored in SQLite database for API access.

### Database Cleanup (if applicable)
```bash
# Clear cache
curl -X POST "http://localhost:8000/api/cache/clear?api_key=YOUR_API_KEY"
```

## 🐛 Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   sudo lsof -i :8000
   sudo kill -9 <PID>
   ```

2. **Permission errors**
   ```bash
   sudo chown -R youtube-api:youtube-api /opt/youtube-api
   sudo chmod +x /opt/youtube-api/start_production.sh
   ```

3. **Memory issues**
   ```bash
   # Reduce workers in production.env
   WORKERS=2
   sudo systemctl restart youtube-api
   ```

4. **YouTube API quota exceeded**
   - Monitor API usage in logs
   - Implement additional caching
   - Consider multiple API keys

### Performance Issues

1. **High response times**
   - Increase cache TTL values
   - Add more workers
   - Enable Redis caching

2. **High memory usage**
   - Reduce worker count
   - Implement worker recycling
   - Monitor for memory leaks

### Debug Mode (Development Only)
```bash
# Never use in production!
export FLASK_DEBUG=True
python3 api_server.py
```

## 📈 Scaling

### Horizontal Scaling
- Deploy multiple instances behind a load balancer
- Use shared Redis for caching
- Implement sticky sessions if needed

### Vertical Scaling
- Increase server resources
- Adjust worker count and connections
- Optimize cache settings

### Load Balancer Configuration (Nginx)
```nginx
upstream youtube_api {
    server 127.0.0.1:8000 weight=1;
    server 127.0.0.1:8001 weight=1;
    # Add more instances as needed
}

server {
    location / {
        proxy_pass http://youtube_api;
        # ... other config
    }
}
```

## 📞 Support

For issues and questions:
1. Check logs first
2. Review this documentation
3. Check GitHub issues
4. Monitor system resources

Remember: Always test deployments in a staging environment first! 