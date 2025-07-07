#!/usr/bin/env python3
"""
Simple test script for YouTube API Handler
Tests core functionality quickly without extensive deployment checks
"""

import os
import sys
import logging
import time
import requests
from threading import Thread

def test_imports():
    """Test that all required modules can be imported"""
    try:
        print("🔍 Testing imports...")
        
        # Core dependencies
        import flask
        import sqlite_logger
        import youtube_api_handler
        import config
        
        print(f"✅ Flask: {flask.__version__}")
        print(f"✅ SQLite Logger: Custom")
        print(f"✅ YouTube API Handler: Custom")
        print(f"✅ Config: Custom")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_config():
    """Test configuration loading"""
    try:
        print("\n🔍 Testing configuration...")
        
        from config import Config
        Config.load_api_keys()
        
        if Config.YOUTUBE_API_KEYS:
            print(f"✅ {len(Config.YOUTUBE_API_KEYS)} API key(s) loaded")
        else:
            print("❌ No API keys configured")
            return False
        
        print(f"✅ Environment: {Config.FLASK_ENV}")
        print(f"✅ Port: {Config.FLASK_PORT}")
        
        return True
    except Exception as e:
        print(f"❌ Config error: {e}")
        return False

def test_sqlite_logging():
    """Test SQLite logging system"""
    try:
        print("\n🔍 Testing SQLite logging...")
        
        from sqlite_logger import SQLiteHandler, SQLiteLogReader
        
        # Test logging
        logger = logging.getLogger('test_logger')
        logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Add SQLite handler
        handler = SQLiteHandler('logs/test_logs.db')
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Test logging
        logger.info("Test message 1")
        logger.warning("Test warning")
        logger.error("Test error")
        
        # Test reading
        reader = SQLiteLogReader('logs/test_logs.db')
        result = reader.get_logs(limit=5)
        
        if result and 'logs' in result:
            print(f"✅ SQLite logging working - {len(result['logs'])} entries")
            return True
        else:
            print(f"❌ SQLite logging failed")
            return False
            
    except Exception as e:
        print(f"❌ SQLite logging error: {e}")
        return False

def test_youtube_handler():
    """Test YouTube API Handler initialization"""
    try:
        print("\n🔍 Testing YouTube API Handler...")
        
        from youtube_api_handler import YouTubeAPIHandler
        
        handler = YouTubeAPIHandler()
        
        print(f"✅ Handler initialized with {len(handler.api_keys)} keys")
        print(f"✅ Cache system: {'enabled' if handler.cache else 'disabled'}")
        print(f"✅ Language mappings: {len(handler.language_mappings)}")
        
        return True
    except Exception as e:
        print(f"❌ YouTube API Handler error: {e}")
        return False

def test_api_server():
    """Test API server startup"""
    try:
        print("\n🔍 Testing API server...")
        
        import subprocess
        import signal
        
        # Start server in background
        proc = subprocess.Popen([
            sys.executable, 'api_server.py'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for startup
        time.sleep(3)
        
        if proc.poll() is None:  # Still running
            print("✅ Server started successfully")
            
            # Test health endpoint
            try:
                response = requests.get('http://localhost:8000/health', timeout=5)
                if response.status_code == 200:
                    print("✅ Health endpoint working")
                else:
                    print(f"⚠️  Health endpoint returned {response.status_code}")
            except Exception as e:
                print(f"⚠️  Health endpoint test failed: {e}")
            
            # Stop server
            proc.terminate()
            proc.wait()
            print("✅ Server stopped")
            
            return True
        else:
            print("❌ Server failed to start")
            return False
            
    except Exception as e:
        print(f"❌ API server test error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 YouTube API Handler - Simple Test")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config), 
        ("SQLite Logging", test_sqlite_logging),
        ("YouTube Handler", test_youtube_handler),
        ("API Server", test_api_server)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} test failed")
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    print("\n📋 SUMMARY")
    print("-" * 20)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("\n🎯 System is ready for use:")
        print("  1. Start server: python3 api_server.py")
        print("  2. View docs: http://localhost:8000/api/docs/")
        print("  3. Check health: http://localhost:8000/health")
    else:
        print(f"❌ {total - passed} tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main() 