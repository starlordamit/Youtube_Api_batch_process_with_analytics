#!/bin/bash

# YouTube API Production Startup Script
# This script starts the YouTube API server in production mode using Gunicorn

set -e

echo "🚀 Starting YouTube API Server in Production Mode"
echo "================================================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Creating one..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate
echo "✅ Virtual environment activated"

# Install/update dependencies
echo "📦 Installing production dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed"

# Create necessary directories
mkdir -p logs
mkdir -p tmp
echo "✅ Directories created"

# Set production environment
export FLASK_ENV=production
export FLASK_DEBUG=False

# Load production environment variables
if [ -f "production.env" ]; then
    echo "📄 Loading production environment variables..."
    set -a
    source production.env
    set +a
    echo "✅ Environment variables loaded"
else
    echo "⚠️  production.env file not found. Using default configuration."
    echo "   Please copy production.env.example to production.env and configure it."
fi

# Validate configuration
echo "🔍 Validating configuration..."
python3 -c "from config import Config; Config.validate(); print('✅ Configuration is valid')"

# Check if port is available
PORT=${FLASK_PORT:-8000}
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null; then
    echo "❌ Port $PORT is already in use. Please stop the existing service or change the port."
    exit 1
fi

# Start the server with Gunicorn
echo "🌟 Starting Gunicorn server..."
echo "   - Environment: production"
echo "   - Host: ${FLASK_HOST:-0.0.0.0}"
echo "   - Port: $PORT"
echo "   - Workers: ${WORKERS:-4}"
echo "   - Worker Class: ${WORKER_CLASS:-gevent}"
echo ""

# Create PID file directory if it doesn't exist
mkdir -p $(dirname ${GUNICORN_PID:-/tmp/youtube_api.pid})

# Start Gunicorn
exec gunicorn \
    --config gunicorn.conf.py \
    --pid ${GUNICORN_PID:-/tmp/youtube_api.pid} \
    api_server:create_app() 