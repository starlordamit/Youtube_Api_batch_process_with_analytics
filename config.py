import os
import secrets
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for YouTube API Handler"""
    
    # YouTube API Configuration
    YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
    YOUTUBE_API_BASE_URL = os.getenv('YOUTUBE_API_BASE_URL', 'https://www.googleapis.com/youtube/v3')
    
    # API Authentication Configuration
    API_AUTH_KEY = os.getenv('API_AUTH_KEY')  # Secret key for API authentication
    REQUIRE_API_AUTH = os.getenv('REQUIRE_API_AUTH', 'True').lower() == 'true'
    
    # Cache Configuration
    CACHE_TTL_CHANNEL = int(os.getenv('CACHE_TTL_CHANNEL', '1800'))  # 30 minutes
    CACHE_TTL_VIDEO = int(os.getenv('CACHE_TTL_VIDEO', '600'))       # 10 minutes
    CACHE_TTL_RSS = int(os.getenv('CACHE_TTL_RSS', '300'))           # 5 minutes
    DEFAULT_CACHE_TTL = int(os.getenv('DEFAULT_CACHE_TTL', '3600'))  # 1 hour
    
    # Rate Limiting Configuration
    MIN_REQUEST_INTERVAL = float(os.getenv('MIN_REQUEST_INTERVAL', '0.1'))  # 100ms
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    RETRY_DELAY = float(os.getenv('RETRY_DELAY', '1.0'))  # 1 second
    
    # Batch Processing Configuration
    MAX_VIDEO_BATCH_SIZE = int(os.getenv('MAX_VIDEO_BATCH_SIZE', '50'))
    MAX_CHANNEL_BATCH_SIZE = int(os.getenv('MAX_CHANNEL_BATCH_SIZE', '50'))
    MAX_CONCURRENT_WORKERS = int(os.getenv('MAX_CONCURRENT_WORKERS', '5'))
    
    # Flask API Configuration
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    
    # Production WSGI Configuration
    WORKERS = int(os.getenv('WORKERS', '4'))
    WORKER_CLASS = os.getenv('WORKER_CLASS', 'gevent')
    WORKER_CONNECTIONS = int(os.getenv('WORKER_CONNECTIONS', '1000'))
    TIMEOUT = int(os.getenv('TIMEOUT', '120'))
    KEEPALIVE = int(os.getenv('KEEPALIVE', '5'))
    MAX_REQUESTS = int(os.getenv('MAX_REQUESTS', '1000'))
    MAX_REQUESTS_JITTER = int(os.getenv('MAX_REQUESTS_JITTER', '100'))
    
    # Security Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
    RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT_DEFAULT', '100 per hour')
    RATE_LIMIT_STORAGE_URL = os.getenv('RATE_LIMIT_STORAGE_URL', 'memory://')
    
    # Monitoring Configuration
    ENABLE_METRICS = os.getenv('ENABLE_METRICS', 'True').lower() == 'true'
    METRICS_PORT = int(os.getenv('METRICS_PORT', '9090'))
    HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', '30'))
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/api.log')
    LOG_MAX_SIZE = int(os.getenv('LOG_MAX_SIZE', '10485760'))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', '5'))
    ACCESS_LOG_FILE = os.getenv('ACCESS_LOG_FILE', 'logs/access.log')
    ERROR_LOG_FILE = os.getenv('ERROR_LOG_FILE', 'logs/error.log')
    
    # Request Timeout Configuration
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))  # 30 seconds
    
    # Default API Parts
    DEFAULT_CHANNEL_PARTS = os.getenv('DEFAULT_CHANNEL_PARTS', 'contentDetails,localizations,snippet,statistics,status,topicDetails').split(',')
    DEFAULT_VIDEO_PARTS = os.getenv('DEFAULT_VIDEO_PARTS', 'contentDetails,id,liveStreamingDetails,localizations,paidProductPlacementDetails,player,recordingDetails,snippet,statistics,status,topicDetails').split(',')
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY is required. Please set it in your .env file or environment variables.")
        
        if len(cls.YOUTUBE_API_KEY) < 30:
            raise ValueError("YOUTUBE_API_KEY appears to be invalid. Please check your API key.")
        
        return True
    
    @classmethod
    def get_config_summary(cls):
        """Get configuration summary for debugging"""
        return {
            'youtube_api_key_set': bool(cls.YOUTUBE_API_KEY),
            'youtube_api_key_length': len(cls.YOUTUBE_API_KEY) if cls.YOUTUBE_API_KEY else 0,
            'cache_ttl_channel': cls.CACHE_TTL_CHANNEL,
            'cache_ttl_video': cls.CACHE_TTL_VIDEO,
            'cache_ttl_rss': cls.CACHE_TTL_RSS,
            'min_request_interval': cls.MIN_REQUEST_INTERVAL,
            'max_batch_sizes': {
                'video': cls.MAX_VIDEO_BATCH_SIZE,
                'channel': cls.MAX_CHANNEL_BATCH_SIZE
            },
            'flask_config': {
                'host': cls.FLASK_HOST,
                'port': cls.FLASK_PORT,
                'debug': cls.FLASK_DEBUG
            },
            'log_level': cls.LOG_LEVEL
        } 