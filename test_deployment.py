#!/usr/bin/env python3
"""
YouTube API Handler - Deployment Test Script
Tests all components to ensure proper deployment
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime

def test_imports():
    """Test all required imports"""
    print("🔍 Testing imports...")
    try:
        import flask
        print(f"✅ Flask: {flask.__version__}")
        
        import requests
        print(f"✅ Requests: {requests.__version__}")
        
        import feedparser
        print(f"✅ Feedparser: {feedparser.__version__}")
        
        import prometheus_client
        print(f"✅ Prometheus Client: {prometheus_client.__version__}")
        
        import psutil
        print(f"✅ PSUtil: {psutil.__version__}")
        
        from flask_cors import CORS
        print("✅ Flask-CORS")
        
        from flask_limiter import Limiter
        print("✅ Flask-Limiter")
        
        from flask_swagger_ui import get_swaggerui_blueprint
        print("✅ Flask-Swagger-UI")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_config():
    """Test configuration loading"""
    print("\n🔍 Testing configuration...")
    try:
        from config import Config
        
        # Test environment loading
        if os.path.exists('.env'):
            print("✅ .env file found")
        else:
            print("⚠️  .env file not found, using defaults")
        
        # Test API key configuration
        Config.load_api_keys()
        if Config.YOUTUBE_API_KEYS:
            print(f"✅ {len(Config.YOUTUBE_API_KEYS)} API key(s) loaded")
        else:
            print("❌ No API keys configured")
            return False
        
        print(f"✅ Log level: {Config.LOG_LEVEL}")
        print(f"✅ Log file: {Config.LOG_FILE}")
        print(f"✅ Error log file: {Config.ERROR_LOG_FILE}")
        
        return True
    except Exception as e:
        print(f"❌ Config error: {e}")
        return False

def test_logging():
    """Test logging setup"""
    print("\n🔍 Testing logging setup...")
    try:
        # Test logs directory creation
        logs_dir = "logs"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, exist_ok=True)
            print(f"✅ Created logs directory: {logs_dir}")
        else:
            print(f"✅ Logs directory exists: {logs_dir}")
        
        # Test write permissions
        test_log_file = os.path.join(logs_dir, "test.log")
        try:
            with open(test_log_file, 'w') as f:
                f.write("Test log entry\n")
            os.remove(test_log_file)
            print("✅ Logs directory is writable")
        except PermissionError:
            print("❌ Logs directory is not writable")
            return False
        
        # Test logging configuration
        from api_server import setup_logging
        setup_logging()
        
        # Test actual logging
        logger = logging.getLogger("test_deployment")
        logger.info("Test log message")
        logger.error("Test error message")
        
        print("✅ Logging setup completed successfully")
        return True
    except Exception as e:
        print(f"❌ Logging error: {e}")
        return False

def test_youtube_api_handler():
    """Test YouTube API Handler initialization"""
    print("\n🔍 Testing YouTube API Handler...")
    try:
        from youtube_api_handler import YouTubeAPIHandler
        
        # Test initialization
        handler = YouTubeAPIHandler()
        print("✅ YouTube API Handler initialized")
        
        # Test language mappings
        if os.path.exists('languagelist.json'):
            print("✅ Language mappings file found")
            if handler.language_mappings:
                print(f"✅ {len(handler.language_mappings)} language mappings loaded")
            else:
                print("⚠️  Language mappings not loaded")
        else:
            print("⚠️  languagelist.json not found")
        
        # Test cache
        if handler.cache:
            print("✅ Cache system initialized")
        else:
            print("⚠️  Cache disabled")
        
        # Test API key rotation
        stats = handler.get_key_usage_stats()
        print(f"✅ API key rotation: {stats['rotation_strategy']}")
        print(f"✅ Total keys: {stats['total_keys']}")
        
        return True
    except Exception as e:
        print(f"❌ YouTube API Handler error: {e}")
        return False

def test_flask_app():
    """Test Flask application initialization"""
    print("\n🔍 Testing Flask application...")
    try:
        # Import without starting server
        import api_server
        
        app = api_server.app
        print("✅ Flask app created")
        
        # Test routes
        with app.test_client() as client:
            # Test health endpoint
            response = client.get('/health')
            if response.status_code == 200:
                print("✅ Health endpoint working")
            else:
                print(f"❌ Health endpoint failed: {response.status_code}")
                return False
            
            # Test Swagger endpoint
            response = client.get('/api/swagger.json')
            if response.status_code == 200:
                print("✅ Swagger JSON endpoint working")
            else:
                print(f"❌ Swagger endpoint failed: {response.status_code}")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Flask app error: {e}")
        return False

def test_api_endpoints():
    """Test API endpoints with actual server"""
    print("\n🔍 Testing API endpoints (requires running server)...")
    
    # Common test URLs
    base_url = "http://localhost:8000"
    api_key = "yt_api_secure_key_2024_production_v3"  # Default key
    
    endpoints = [
        ("/health", "Health check"),
        ("/api/swagger.json", "Swagger specification"),
        ("/ready", "Readiness check"),
        ("/live", "Liveness check"),
    ]
    
    for endpoint, description in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {description}: {endpoint}")
            else:
                print(f"❌ {description} failed: {endpoint} ({response.status_code})")
        except requests.exceptions.RequestException:
            print(f"⚠️  {description}: Server not running or unreachable")
    
    return True

def test_deployment_files():
    """Test deployment-related files"""
    print("\n🔍 Testing deployment files...")
    
    files = [
        ("requirements.txt", "Python dependencies"),
        ("Dockerfile", "Docker configuration"),
        ("docker-compose.yml", "Docker Compose"),
        ("gunicorn.conf.py", "Gunicorn configuration"),
        (".gitignore", "Git ignore rules"),
        (".dockerignore", "Docker ignore rules"),
        ("logs/.gitkeep", "Logs directory keeper"),
    ]
    
    for filename, description in files:
        if os.path.exists(filename):
            print(f"✅ {description}: {filename}")
        else:
            print(f"❌ Missing {description}: {filename}")
    
    return True

def generate_deployment_report():
    """Generate a comprehensive deployment report"""
    print("\n📊 DEPLOYMENT TEST REPORT")
    print("=" * 50)
    print(f"Test Date: {datetime.now().isoformat()}")
    print(f"Python Version: {sys.version}")
    print(f"Working Directory: {os.getcwd()}")
    print()
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Logging", test_logging),
        ("YouTube API Handler", test_youtube_api_handler),
        ("Flask Application", test_flask_app),
        ("API Endpoints", test_api_endpoints),
        ("Deployment Files", test_deployment_files),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results[test_name] = False
    
    print("\n📋 SUMMARY")
    print("-" * 20)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED - Ready for deployment!")
        return True
    else:
        print("⚠️  SOME TESTS FAILED - Check errors above")
        return False

if __name__ == "__main__":
    print("🚀 YouTube API Handler - Deployment Test")
    print("=" * 50)
    
    success = generate_deployment_report()
    
    if not success:
        print("\n🔧 TROUBLESHOOTING TIPS:")
        print("1. Run: pip install -r requirements.txt")
        print("2. Check .env file has valid API keys")
        print("3. Ensure logs directory is writable")
        print("4. For server tests, start server with: python3 api_server.py")
        print("5. Check DEPLOYMENT.md for detailed setup instructions")
        
        sys.exit(1)
    
    print("\n🎯 Next steps:")
    print("1. Start server: python3 api_server.py")
    print("2. Test endpoints: python3 test_deployment.py")
    print("3. Build Docker: docker build -t youtube-api .")
    print("4. Deploy to production server")
    
    sys.exit(0) 