#!/usr/bin/env python3
"""
Setup script for YouTube API Handler
"""

import os
import sys
import subprocess
import secrets
import string
from pathlib import Path

def generate_secure_api_key(length=32):
    """Generate a secure API key"""
    alphabet = string.ascii_letters + string.digits + '_-'
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_env_file():
    """Create .env file from sample if it doesn't exist"""
    env_file = Path('.env')
    sample_env = Path('sample.env')
    
    if env_file.exists():
        print("✓ .env file already exists")
        return
    
    if not sample_env.exists():
        print("✗ sample.env file not found")
        return
    
    # Read sample.env and replace placeholder values
    with open(sample_env, 'r') as f:
        content = f.read()
    
    # Generate secure API key
    secure_api_key = generate_secure_api_key()
    
    # Replace placeholder with secure key
    content = content.replace('your_secret_api_auth_key_here', secure_api_key)
    
    # Write to .env
    with open(env_file, 'w') as f:
        f.write(content)
    
    print("✓ Created .env file with secure API authentication key")
    print(f"✓ Generated API key: {secure_api_key}")
    print("✓ You can change this key in the .env file if needed")

def install_requirements():
    """Install required packages"""
    try:
        print("Installing required packages...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                      check=True, capture_output=True)
        print("✓ Requirements installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"✗ Error installing requirements: {e}")
        return False
    return True

def validate_youtube_api_key():
    """Validate YouTube API key"""
    from config import Config
    
    try:
        Config.validate()
        print("✓ YouTube API key is valid")
        return True
    except ValueError as e:
        print(f"✗ YouTube API key validation failed: {e}")
        print("Please set your YouTube API key in the .env file")
        return False

def test_api_connection():
    """Test API connection"""
    try:
        from youtube_api_handler import YouTubeAPIHandler
        handler = YouTubeAPIHandler()
        print("✓ YouTube API Handler initialized successfully")
        return True
    except Exception as e:
        print(f"✗ Error initializing API handler: {e}")
        return False

def main():
    """Main setup function"""
    print("=" * 60)
    print("YouTube API Handler Setup")
    print("=" * 60)
    
    # Step 1: Create .env file
    print("\n1. Setting up environment configuration...")
    create_env_file()
    
    # Step 2: Install requirements
    print("\n2. Installing dependencies...")
    if not install_requirements():
        return
    
    # Step 3: Validate configuration
    print("\n3. Validating configuration...")
    if not validate_youtube_api_key():
        print("\n⚠️  Setup incomplete - please configure your YouTube API key in .env")
        return
    
    # Step 4: Test connection
    print("\n4. Testing API connection...")
    if not test_api_connection():
        print("\n⚠️  Setup incomplete - API connection test failed")
        return
    
    print("\n" + "=" * 60)
    print("✓ Setup completed successfully!")
    print("=" * 60)
    print("\nAPI Configuration:")
    print(f"• Authentication: {'Enabled' if os.getenv('REQUIRE_API_AUTH', 'True').lower() == 'true' else 'Disabled'}")
    print(f"• API Key: {os.getenv('API_AUTH_KEY', 'Not set')}")
    print(f"• YouTube API Key: {'Configured' if os.getenv('YOUTUBE_API_KEY') else 'Not configured'}")
    
    print("\nTo start the server:")
    print("python3 api_server.py")
    
    print("\nTo use the API with authentication:")
    print("• Query parameter: ?api_key=your_api_key")
    print("• Header: X-API-Key: your_api_key")
    
    print("\nAPI Documentation:")
    print("http://localhost:8000/api/docs")

if __name__ == '__main__':
    main() 