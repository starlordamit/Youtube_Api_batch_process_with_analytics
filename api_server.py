from flask import Flask, jsonify, request
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from youtube_api_handler import YouTubeAPIHandler
from config import Config
import logging
import logging.handlers
from functools import wraps
import secrets
from datetime import datetime
import os
import psutil
from prometheus_client import Counter, Histogram, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
import time

# Configure production logging
def setup_logging():
    """Setup production-grade logging with file rotation"""
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(Config.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler for development
    if Config.FLASK_DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter(Config.LOG_FORMAT)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # File handler with rotation for production
    file_handler = logging.handlers.RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_SIZE,
        backupCount=Config.LOG_BACKUP_COUNT
    )
    file_handler.setLevel(getattr(logging, Config.LOG_LEVEL))
    file_formatter = logging.Formatter(Config.LOG_FORMAT)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler for errors only
    error_handler = logging.handlers.RotatingFileHandler(
        Config.ERROR_LOG_FILE,
        maxBytes=Config.LOG_MAX_SIZE,
        backupCount=Config.LOG_BACKUP_COUNT
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)

setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Production Flask Configuration
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['ENV'] = Config.FLASK_ENV

# Initialize CORS
cors = CORS(app, origins=Config.CORS_ORIGINS)

# Initialize Rate Limiter
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri=Config.RATE_LIMIT_STORAGE_URL,
    default_limits=[Config.RATE_LIMIT_DEFAULT]
)

# Initialize Prometheus metrics
if Config.ENABLE_METRICS:
    registry = CollectorRegistry()
    
    # Request metrics
    REQUEST_COUNT = Counter(
        'http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status'],
        registry=registry
    )
    
    REQUEST_DURATION = Histogram(
        'http_request_duration_seconds',
        'HTTP request duration in seconds',
        ['method', 'endpoint'],
        registry=registry
    )
    
    # YouTube API metrics
    YOUTUBE_API_CALLS = Counter(
        'youtube_api_calls_total',
        'Total YouTube API calls',
        ['endpoint_type'],
        registry=registry
    )
    
    CACHE_HITS = Counter(
        'cache_hits_total',
        'Total cache hits',
        ['cache_type'],
        registry=registry
    )

# Initialize YouTube API handler (will use config from .env)
try:
    yt_handler = YouTubeAPIHandler()
    logger.info("YouTube API Handler initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize YouTube API Handler: {e}")
    raise

def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not Config.REQUIRE_API_AUTH:
            return f(*args, **kwargs)
        
        # Check for API key in query params or headers
        api_key = request.args.get('api_key') or request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key required',
                'message': 'Please provide api_key parameter or X-API-Key header',
                'meta': {
                    'timestamp': datetime.now().isoformat(),
                    'authentication_required': True
                }
            }), 401
        
        if not Config.API_AUTH_KEY:
            return jsonify({
                'success': False,
                'error': 'Server configuration error',
                'message': 'API authentication not properly configured',
                'meta': {
                    'timestamp': datetime.now().isoformat()
                }
            }), 500
        
        if not secrets.compare_digest(api_key, Config.API_AUTH_KEY):
            return jsonify({
                'success': False,
                'error': 'Invalid API key',
                'message': 'The provided API key is invalid',
                'meta': {
                    'timestamp': datetime.now().isoformat(),
                    'authentication_failed': True
                }
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function

def standardize_response(data, from_cache=False, cache_status='unknown', cache_details=None, count=None):
    """Standardize API response format"""
    response = {
        'success': True,
        'data': data,
        'meta': {
            'from_cache': from_cache,
            'cache_status': cache_status,
            'timestamp': datetime.now().isoformat()
        }
    }
    
    if count is not None:
        response['meta']['count'] = count
    
    if cache_details:
        response['meta']['cache_details'] = cache_details
    
    return response

def handle_errors(f):
    """Decorator for error handling with standardized response"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {e}")
            return jsonify({
                'success': False,
                'error': 'Internal server error',
                'message': str(e),
                'meta': {
                    'timestamp': datetime.now().isoformat(),
                    'endpoint': f.__name__
                }
            }), 500
    return decorated_function

def track_metrics(f):
    """Decorator to track metrics for API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not Config.ENABLE_METRICS:
            return f(*args, **kwargs)
        
        start_time = time.time()
        method = request.method
        endpoint = f.__name__
        
        try:
            response = f(*args, **kwargs)
            status = response[1] if isinstance(response, tuple) else 200
            
            # Track request count and duration
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(time.time() - start_time)
            
            return response
        except Exception as e:
            # Track error metrics
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=500).inc()
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(time.time() - start_time)
            raise
    
    return decorated_function

# Production middleware
@app.before_request
def before_request():
    """Log incoming requests in production"""
    if not Config.FLASK_DEBUG:
        logger.info(f"{request.method} {request.path} from {request.remote_addr}")

@app.after_request
def after_request(response):
    """Add security headers and log responses"""
    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # Log response in production
    if not Config.FLASK_DEBUG:
        logger.info(f"Response {response.status_code} for {request.method} {request.path}")
    
    return response

@app.route('/health', methods=['GET'])
@track_metrics
def health_check():
    """Enhanced health check endpoint for production monitoring"""
    # Get system metrics
    process = psutil.Process()
    memory_info = process.memory_info()
    
    health_data = {
        'status': 'healthy',
        'server_time': datetime.now().isoformat(),
        'uptime_seconds': time.time() - process.create_time(),
        'system': {
            'cpu_percent': psutil.cpu_percent(),
            'memory_usage_mb': memory_info.rss / 1024 / 1024,
            'memory_percent': process.memory_percent(),
            'disk_usage_percent': psutil.disk_usage('/').percent,
            'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
        },
        'application': {
            'environment': Config.FLASK_ENV,
            'debug_mode': Config.FLASK_DEBUG,
            'authentication_enabled': Config.REQUIRE_API_AUTH,
            'metrics_enabled': Config.ENABLE_METRICS,
            'cache_stats': yt_handler.get_cache_stats(),
            'workers': Config.WORKERS if hasattr(Config, 'WORKERS') else 1
        },
        'dependencies': {
            'youtube_api_configured': bool(Config.YOUTUBE_API_KEY),
            'logging_configured': True,
            'rate_limiting_enabled': True
        }
    }
    
    return jsonify(standardize_response(
        data=health_data,
        from_cache=False,
        cache_status='live'
    ))

@app.route('/api/channel/<handle>', methods=['GET'])
@require_api_key
@handle_errors
def get_channel_by_handle(handle):
    """Get channel information by handle"""
    parts = request.args.getlist('parts')
    if not parts:
        parts = None
    
    result = yt_handler.get_channel_by_handle(handle, parts)
    
    if not result or not result.get('data'):
        return jsonify({
            'success': False,
            'error': 'Channel not found',
            'message': f'No channel found with handle: @{handle}',
            'meta': {
                'timestamp': datetime.now().isoformat(),
                'handle': handle
            }
        }), 404
    
    # Format the raw channel data
    formatted_data = yt_handler._format_channel_response(result['data'])
    
    return jsonify(standardize_response(
        data=formatted_data,
        from_cache=result.get('from_cache', False),
        cache_status=result.get('cache_status', 'unknown')
    ))

@app.route('/api/channels', methods=['POST'])
@require_api_key
@handle_errors
def get_channels_by_id():
    """Get multiple channels by ID"""
    data = request.get_json()
    
    if not data or 'channel_ids' not in data:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter',
            'message': 'channel_ids is required in request body',
            'meta': {
                'timestamp': datetime.now().isoformat(),
                'required_fields': ['channel_ids']
            }
        }), 400
    
    channel_ids = data['channel_ids']
    parts = data.get('parts')
    
    result = yt_handler.get_channels_by_id(channel_ids, parts)
    
    # Format the raw channel data
    formatted_data = []
    if result.get('data'):
        for raw_channel in result['data']:
            formatted_data.append(yt_handler._format_channel_response(raw_channel))
    
    return jsonify(standardize_response(
        data=formatted_data,
        from_cache=result.get('from_cache', False),
        cache_status=result.get('cache_status', 'unknown'),
        count=len(formatted_data)
    ))

@app.route('/api/videos', methods=['POST'])
@require_api_key
@handle_errors
def get_videos_by_id():
    """Get multiple videos by ID"""
    data = request.get_json()
    
    if not data or 'video_ids' not in data:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter',
            'message': 'video_ids is required in request body',
            'meta': {
                'timestamp': datetime.now().isoformat(),
                'required_fields': ['video_ids']
            }
        }), 400
    
    video_ids = data['video_ids']
    parts = data.get('parts')
    
    result = yt_handler.get_videos_by_id(video_ids, parts)
    
    return jsonify(standardize_response(
        data=result.get('data', []),
        from_cache=result.get('from_cache', False),
        cache_status=result.get('cache_status', 'unknown'),
        count=len(result.get('data', []))
    ))

@app.route('/api/channel/<handle>/videos', methods=['GET'])
@require_api_key
@handle_errors
def get_channel_recent_videos(handle):
    """Get channel with recent videos and advanced analytics"""
    max_videos = request.args.get('max_videos', 15, type=int)
    include_detailed = request.args.get('include_detailed', 'false').lower() == 'true'
    
    result = yt_handler.get_channel_recent_videos(handle, max_videos, include_detailed)
    
    if not result or not result.get('data'):
        return jsonify({
            'success': False,
            'error': 'Channel not found',
            'message': f'No channel found with handle: @{handle}',
            'meta': {
                'timestamp': datetime.now().isoformat(),
                'handle': handle
            }
        }), 404
    
    return jsonify(standardize_response(
        data=result['data'],
        from_cache=result.get('from_cache', False),
        cache_status=result.get('cache_status', 'unknown'),
        cache_details=result.get('cache_details', {})
    ))

@app.route('/api/channel/<channel_id>/rss', methods=['GET'])
@require_api_key
@handle_errors
def get_channel_rss(channel_id):
    """Get channel RSS feed"""
    result = yt_handler.get_channel_videos_rss(channel_id)
    
    return jsonify(standardize_response(
        data=result.get('data', []),
        from_cache=result.get('from_cache', False),
        cache_status=result.get('cache_status', 'unknown'),
        count=len(result.get('data', []))
    ))

@app.route('/api/rss/channels', methods=['POST'])
@require_api_key
@handle_errors
def get_multiple_channels_rss():
    """Get RSS feeds for multiple channels"""
    data = request.get_json()
    
    if not data or 'channel_ids' not in data:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter',
            'message': 'channel_ids is required in request body',
            'meta': {
                'timestamp': datetime.now().isoformat(),
                'required_fields': ['channel_ids']
            }
        }), 400
    
    channel_ids = data['channel_ids']
    
    if not isinstance(channel_ids, list):
        return jsonify({
            'success': False,
            'error': 'Invalid parameter type',
            'message': 'channel_ids must be an array',
            'meta': {
                'timestamp': datetime.now().isoformat(),
                'received_type': type(channel_ids).__name__
            }
        }), 400
    
    if len(channel_ids) > 10:
        return jsonify({
            'success': False,
            'error': 'Request limit exceeded',
            'message': 'Maximum 10 channels allowed per request',
            'meta': {
                'timestamp': datetime.now().isoformat(),
                'max_allowed': 10,
                'received_count': len(channel_ids)
            }
        }), 400
    
    # Get RSS feeds for each channel
    results = {}
    cache_statuses = {}
    
    for channel_id in channel_ids:
        result = yt_handler.get_channel_videos_rss(channel_id)
        results[channel_id] = result.get('data', [])
        cache_statuses[channel_id] = {
            'from_cache': result.get('from_cache', False),
            'cache_status': result.get('cache_status', 'unknown')
        }
    
    return jsonify(standardize_response(
        data=results,
        from_cache=any(status['from_cache'] for status in cache_statuses.values()),
        cache_status='mixed' if len(set(status['cache_status'] for status in cache_statuses.values())) > 1 else list(cache_statuses.values())[0]['cache_status'],
        cache_details=cache_statuses
    ))

@app.route('/api/batch', methods=['POST'])
@require_api_key
@handle_errors
def batch_process():
    """Process multiple requests in batch"""
    data = request.get_json()
    
    if not data or 'requests' not in data:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter',
            'message': 'requests array is required in request body',
            'meta': {
                'timestamp': datetime.now().isoformat(),
                'required_fields': ['requests']
            }
        }), 400
    
    requests_config = data['requests']
    
    if not isinstance(requests_config, list):
        return jsonify({
            'success': False,
            'error': 'Invalid parameter type',
            'message': 'requests must be an array',
            'meta': {
                'timestamp': datetime.now().isoformat(),
                'received_type': type(requests_config).__name__
            }
        }), 400
    
    if len(requests_config) > 20:
        return jsonify({
            'success': False,
            'error': 'Request limit exceeded',
            'message': 'Maximum 20 requests per batch',
            'meta': {
                'timestamp': datetime.now().isoformat(),
                'max_allowed': 20,
                'received_count': len(requests_config)
            }
        }), 400
    
    # Process each request and collect cache information
    results = {}
    cache_info = {}
    
    for i, config in enumerate(requests_config):
        request_type = config.get('type')
        params = config.get('params', {})
        request_key = f"{request_type}_{i}"
        
        try:
            if request_type == 'channel_by_handle':
                result = yt_handler.get_channel_by_handle(**params)
                # Format raw channel data
                formatted_data = yt_handler._format_channel_response(result.get('data')) if result.get('data') else None
                results[request_key] = formatted_data
            elif request_type == 'channels_by_id':
                result = yt_handler.get_channels_by_id(**params)
                # Format raw channel data
                formatted_data = []
                if result.get('data'):
                    for raw_channel in result['data']:
                        formatted_data.append(yt_handler._format_channel_response(raw_channel))
                results[request_key] = formatted_data
            elif request_type == 'videos_by_id':
                result = yt_handler.get_videos_by_id(**params)
                results[request_key] = result.get('data')
            elif request_type == 'channel_rss':
                result = yt_handler.get_channel_videos_rss(**params)
                results[request_key] = result.get('data')
            elif request_type == 'channel_recent_videos':
                result = yt_handler.get_channel_recent_videos(**params)
                results[request_key] = result.get('data')
            else:
                result = {'data': None, 'from_cache': False, 'cache_status': 'error'}
                results[request_key] = result.get('data')
            
            cache_info[request_key] = {
                'from_cache': result.get('from_cache', False),
                'cache_status': result.get('cache_status', 'unknown')
            }
        except Exception as e:
            results[request_key] = None
            cache_info[request_key] = {
                'from_cache': False,
                'cache_status': 'error',
                'error': str(e)
            }
    
    return jsonify(standardize_response(
        data=results,
        from_cache=any(info.get('from_cache', False) for info in cache_info.values()),
        cache_status='mixed' if len(set(info.get('cache_status', 'unknown') for info in cache_info.values())) > 1 else list(cache_info.values())[0].get('cache_status', 'unknown'),
        cache_details=cache_info,
        count=len(results)
    ))

@app.route('/api/cache/stats', methods=['GET'])
@require_api_key
@handle_errors
def get_cache_stats():
    """Get cache statistics"""
    return jsonify(standardize_response(
        data=yt_handler.get_cache_stats(),
        from_cache=False,
        cache_status='live'
    ))

@app.route('/api/cache/clear', methods=['POST'])
@require_api_key
@handle_errors
def clear_cache():
    """Clear cache"""
    yt_handler.clear_cache()
    return jsonify(standardize_response(
        data={'message': 'Cache cleared successfully'},
        from_cache=False,
        cache_status='cleared'
    ))

@app.route('/api/keys/stats', methods=['GET'])
@require_api_key
@handle_errors
def get_api_key_stats():
    """Get API key usage statistics and rotation status"""
    stats = yt_handler.get_key_usage_stats()
    
    return jsonify(standardize_response(
        data=stats,
        from_cache=False,
        cache_status='live'
    ))

# Swagger UI Configuration
SWAGGER_URL = '/api/docs'
API_URL = '/api/swagger.json'

# OpenAPI 3.0 Specification
swagger_spec = {
    "openapi": "3.0.0",
    "info": {
        "title": "YouTube API Handler",
        "description": "A comprehensive YouTube API wrapper with advanced analytics, caching, batch processing, and API authentication.",
        "version": "3.0.0",
        "contact": {
            "name": "YouTube API Handler",
            "url": "https://github.com/your-repo/youtube-api-handler"
        }
    },
    "servers": [
        {
            "url": f"http://localhost:{Config.FLASK_PORT}",
            "description": "Development server"
        }
    ],
    "components": {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "query",
                "name": "api_key"
            },
            "ApiKeyHeader": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key"
            }
        },
        "schemas": {
            "StandardResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "data": {"type": "object"},
                    "meta": {
                        "type": "object",
                        "properties": {
                            "from_cache": {"type": "boolean"},
                            "cache_status": {"type": "string", "enum": ["hit", "miss", "partial", "mixed", "live", "cleared"]},
                            "timestamp": {"type": "string", "format": "date-time"},
                            "count": {"type": "integer"}
                        }
                    }
                }
            },
            "ChannelData": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "custom_url": {"type": "string"},
                    "handle": {"type": "string"},
                    "subscriber_count": {"type": "integer"},
                    "video_count": {"type": "integer"},
                    "view_count": {"type": "integer"},
                    "primary_audio_language": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "name": {"type": "string"}
                        }
                    },
                    "language_confidence": {"type": "number"},
                    "thumbnails": {"type": "object"},
                    "verification_status": {"type": "string"},
                    "categories": {"type": "array", "items": {"type": "string"}},
                    "email": {"type": "string"},
                    "country": {"type": "string"}
                }
            },
            "VideoData": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "channel_id": {"type": "string"},
                    "channel_title": {"type": "string"},
                    "published_at": {"type": "string", "format": "date-time"},
                    "duration": {"type": "string"},
                    "view_count": {"type": "integer"},
                    "like_count": {"type": "integer"},
                    "comment_count": {"type": "integer"},
                    "video_type": {"type": "string", "enum": ["short", "long"]},
                    "thumbnails": {"type": "object"},
                    "category_id": {"type": "string"},
                    "default_audio_language": {"type": "string"}
                }
            },
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": False},
                    "error": {"type": "string"},
                    "message": {"type": "string"},
                    "meta": {
                        "type": "object",
                        "properties": {
                            "timestamp": {"type": "string", "format": "date-time"}
                        }
                    }
                }
            }
        }
    },
    "paths": {
        "/health": {
            "get": {
                "summary": "Health Check",
                "description": "Check the API server health status",
                "tags": ["System"],
                "responses": {
                    "200": {
                        "description": "Server is healthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/StandardResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/api/channel/{handle}": {
            "get": {
                "summary": "Get Channel by Handle",
                "description": "Retrieve detailed channel information by handle with analytics and language detection",
                "tags": ["Channels"],
                "security": [{"ApiKeyAuth": []}, {"ApiKeyHeader": []}],
                "parameters": [
                    {
                        "name": "handle",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Channel handle (e.g., @BongPosto)",
                        "example": "@BongPosto"
                    },
                    {
                        "name": "parts",
                        "in": "query",
                        "schema": {"type": "array", "items": {"type": "string"}},
                        "description": "API parts to include"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Channel information retrieved successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {"$ref": "#/components/schemas/StandardResponse"},
                                        {
                                            "properties": {
                                                "data": {"$ref": "#/components/schemas/ChannelData"}
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"}
                }
            }
        },
        "/api/channel/{handle}/videos": {
            "get": {
                "summary": "Get Channel Videos with Analytics",
                "description": "Retrieve channel videos with comprehensive analytics including engagement rates, content classification, and language analysis",
                "tags": ["Channels"],
                "security": [{"ApiKeyAuth": []}, {"ApiKeyHeader": []}],
                "parameters": [
                    {
                        "name": "handle",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Channel handle (e.g., @MrBeast)",
                        "example": "@MrBeast"
                    },
                    {
                        "name": "max_videos",
                        "in": "query",
                        "schema": {"type": "integer", "default": 15, "minimum": 1, "maximum": 50},
                        "description": "Maximum number of videos to retrieve"
                    },
                    {
                        "name": "include_detailed",
                        "in": "query",
                        "schema": {"type": "boolean", "default": False},
                        "description": "Include detailed video breakdown"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Channel videos and analytics retrieved successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/StandardResponse"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "401": {"$ref": "#/components/responses/Unauthorized"}
                }
            }
        },
        "/api/channels": {
            "post": {
                "summary": "Get Multiple Channels by ID",
                "description": "Batch retrieve multiple channels by their IDs",
                "tags": ["Channels"],
                "security": [{"ApiKeyAuth": []}, {"ApiKeyHeader": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["channel_ids"],
                                "properties": {
                                    "channel_ids": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Array of channel IDs",
                                        "example": ["UCX6OQ3DkcsbYNE6H8uQQuVA", "UC_x5XG1OV2P6uZZ5FSM9Ttw"]
                                    },
                                    "parts": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Optional API parts"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Channels retrieved successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/StandardResponse"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "401": {"$ref": "#/components/responses/Unauthorized"}
                }
            }
        },
        "/api/videos": {
            "post": {
                "summary": "Get Multiple Videos by ID",
                "description": "Batch retrieve multiple videos by their IDs",
                "tags": ["Videos"],
                "security": [{"ApiKeyAuth": []}, {"ApiKeyHeader": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["video_ids"],
                                "properties": {
                                    "video_ids": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Array of video IDs",
                                        "example": ["9hMz-55SBcc", "RUwKcUOdffU"]
                                    },
                                    "parts": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Optional API parts"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Videos retrieved successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/StandardResponse"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"}
                }
            }
        },
        "/api/channel/{channel_id}/rss": {
            "get": {
                "summary": "Get Channel RSS Feed",
                "description": "Retrieve and parse channel RSS feed data",
                "tags": ["RSS"],
                "security": [{"ApiKeyAuth": []}, {"ApiKeyHeader": []}],
                "parameters": [
                    {
                        "name": "channel_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Channel ID",
                        "example": "UCMlzi5avz-Bcn_1A_w-M5cg"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "RSS feed retrieved successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/StandardResponse"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            }
        },
        "/api/rss/channels": {
            "post": {
                "summary": "Get Multiple Channel RSS Feeds",
                "description": "Batch retrieve RSS feeds for multiple channels",
                "tags": ["RSS"],
                "security": [{"ApiKeyAuth": []}, {"ApiKeyHeader": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["channel_ids"],
                                "properties": {
                                    "channel_ids": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Array of channel IDs"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "RSS feeds retrieved successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/StandardResponse"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"}
                }
            }
        },
        "/api/batch": {
            "post": {
                "summary": "Batch Process Multiple Operations",
                "description": "Execute multiple API operations in a single request",
                "tags": ["Batch"],
                "security": [{"ApiKeyAuth": []}, {"ApiKeyHeader": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["operations"],
                                "properties": {
                                    "operations": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "type": {"type": "string", "enum": ["channel", "videos", "rss"]},
                                                "data": {"type": "object"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Batch operations completed successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/StandardResponse"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"}
                }
            }
        },
        "/api/cache/stats": {
            "get": {
                "summary": "Get Cache Statistics",
                "description": "Retrieve detailed cache performance statistics",
                "tags": ["Cache"],
                "security": [{"ApiKeyAuth": []}, {"ApiKeyHeader": []}],
                "responses": {
                    "200": {
                        "description": "Cache statistics retrieved successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/StandardResponse"}
                            }
                        }
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"}
                }
            }
        },
        "/api/cache/clear": {
            "post": {
                "summary": "Clear Cache",
                "description": "Clear all cached data or specific cache keys",
                "tags": ["Cache"],
                "security": [{"ApiKeyAuth": []}, {"ApiKeyHeader": []}],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "keys": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Specific cache keys to clear (optional)"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Cache cleared successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/StandardResponse"}
                            }
                        }
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"}
                }
            }
        },
        "/api/keys/stats": {
            "get": {
                "summary": "Get API Key Usage Statistics",
                "description": "Retrieve detailed API key usage statistics, rotation status, and quota information",
                "tags": ["API Keys"],
                "security": [{"ApiKeyAuth": []}, {"ApiKeyHeader": []}],
                "responses": {
                    "200": {
                        "description": "API key statistics retrieved successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {"$ref": "#/components/schemas/StandardResponse"},
                                        {
                                            "properties": {
                                                "data": {
                                                    "type": "object",
                                                    "properties": {
                                                        "rotation_strategy": {"type": "string", "enum": ["round_robin", "least_used", "random"]},
                                                        "total_keys": {"type": "integer"},
                                                        "daily_quota_per_key": {"type": "integer"},
                                                        "hourly_quota_per_key": {"type": "integer"},
                                                        "key_stats": {
                                                            "type": "object",
                                                            "additionalProperties": {
                                                                "type": "object",
                                                                "properties": {
                                                                    "total_requests": {"type": "integer"},
                                                                    "successful_requests": {"type": "integer"},
                                                                    "failed_requests": {"type": "integer"},
                                                                    "daily_requests": {"type": "integer"},
                                                                    "hourly_requests": {"type": "integer"},
                                                                    "daily_quota_used_pct": {"type": "number"},
                                                                    "hourly_quota_used_pct": {"type": "number"},
                                                                    "last_used": {"type": "string", "format": "date-time"},
                                                                    "is_exhausted": {"type": "boolean"},
                                                                    "can_make_request": {"type": "boolean"}
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"}
                }
            }
        }
    },
    "components": {
        "responses": {
            "BadRequest": {
                "description": "Bad request",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                }
            },
            "Unauthorized": {
                "description": "Authentication required",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                }
            },
            "Forbidden": {
                "description": "Invalid API key",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                }
            },
            "NotFound": {
                "description": "Resource not found",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                }
            }
        }
    },
    "tags": [
        {"name": "System", "description": "System and health endpoints"},
        {"name": "Channels", "description": "Channel management and analytics"},
        {"name": "Videos", "description": "Video data retrieval"},
        {"name": "RSS", "description": "RSS feed processing"},
        {"name": "Batch", "description": "Batch operations"},
        {"name": "Cache", "description": "Cache management"},
        {"name": "API Keys", "description": "API key usage and rotation management"}
    ]
}

# Create Swagger UI blueprint
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "YouTube API Handler v3.0",
        'supportedSubmitMethods': ['get', 'post'],
        'tryItOutEnabled': True,
        'displayRequestDuration': True,
        'docExpansion': 'list',
        'defaultModelsExpandDepth': 2,
        'displayOperationId': False,
        'defaultModelExpandDepth': 2
    }
)

# Register Swagger UI blueprint
app.register_blueprint(swaggerui_blueprint)

# Production Monitoring Endpoints
@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint (public for monitoring)"""
    if not Config.ENABLE_METRICS:
        return jsonify({'error': 'Metrics disabled'}), 404
    
    return generate_latest(registry), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/ready', methods=['GET'])
def readiness_check():
    """Kubernetes readiness check"""
    try:
        # Check YouTube API connectivity
        test_result = yt_handler.get_cache_stats()
        
        return jsonify({
            'status': 'ready',
            'timestamp': datetime.now().isoformat(),
            'checks': {
                'youtube_api': 'ok',
                'cache': 'ok',
                'database': 'ok'  # Add database check if applicable
            }
        }), 200
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return jsonify({
            'status': 'not_ready',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 503

@app.route('/live', methods=['GET'])
def liveness_check():
    """Kubernetes liveness check"""
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/api/stats', methods=['GET'])
@require_api_key
@track_metrics
def get_api_stats():
    """Get comprehensive API statistics"""
    process = psutil.Process()
    
    stats = {
        'server': {
            'environment': Config.FLASK_ENV,
            'debug_mode': Config.FLASK_DEBUG,
            'uptime_seconds': time.time() - process.create_time(),
            'memory_usage_mb': process.memory_info().rss / 1024 / 1024,
            'cpu_percent': process.cpu_percent(),
            'thread_count': process.num_threads(),
            'open_files': len(process.open_files())
        },
        'cache': yt_handler.get_cache_stats(),
        'configuration': {
            'workers': Config.WORKERS,
            'worker_class': Config.WORKER_CLASS,
            'rate_limit': Config.RATE_LIMIT_DEFAULT,
            'timeout': Config.TIMEOUT,
            'max_requests': Config.MAX_REQUESTS
        }
    }
    
    return jsonify(standardize_response(
        data=stats,
        from_cache=False,
        cache_status='live'
    ))

@app.route('/api/swagger.json')
def swagger():
    """Return the OpenAPI specification"""
    return jsonify(swagger_spec)

def create_app():
    """Application factory for production deployment"""
    return app

if __name__ == '__main__':
    logger.info(f"Starting Flask API server on {Config.FLASK_HOST}:{Config.FLASK_PORT}")
    logger.info(f"Environment: {Config.FLASK_ENV}")
    logger.info(f"Debug mode: {Config.FLASK_DEBUG}")
    logger.info(f"Workers: {Config.WORKERS}")
    logger.info(f"Authentication enabled: {Config.REQUIRE_API_AUTH}")
    logger.info(f"Metrics enabled: {Config.ENABLE_METRICS}")
    logger.info("Configuration loaded from .env file")
    
    if Config.FLASK_ENV == 'production':
        logger.warning("Running in production mode with Flask dev server!")
        logger.warning("Use Gunicorn or another WSGI server for production deployment")
    
    app.run(
        debug=Config.FLASK_DEBUG, 
        host=Config.FLASK_HOST, 
        port=Config.FLASK_PORT,
        threaded=True
    ) 