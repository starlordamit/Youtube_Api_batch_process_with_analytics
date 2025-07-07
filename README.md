# YouTube API Handler

A comprehensive Python library for interacting with YouTube API v3 with built-in caching, batch processing, and rate limiting.

## Features

- **Batch Processing**: Handle multiple API requests efficiently
- **Smart Caching**: Built-in TTL-based caching system for fast responses
- **Rate Limiting**: Automatic rate limiting to prevent API quota exhaustion
- **RSS Feed Support**: Parse YouTube RSS feeds for recent videos
- **Error Handling**: Robust error handling and retry logic
- **Flask API**: Ready-to-use Flask web API endpoints
- **Thread-Safe**: Concurrent request processing with ThreadPoolExecutor

## Installation

### Quick Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run setup script (creates .env file)
python setup.py

# Edit .env file and add your YouTube API key
# Get your API key from: https://console.developers.google.com/
```

### Manual Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file from the sample:
```bash
cp sample.env .env
```

3. Edit `.env` and add your YouTube API key:
```bash
# Required
YOUTUBE_API_KEY=your_youtube_api_key_here

# Optional configurations (with defaults)
CACHE_TTL_CHANNEL=1800
CACHE_TTL_VIDEO=600
FLASK_PORT=5000
LOG_LEVEL=INFO
```

## Quick Start

```python
from youtube_api_handler import YouTubeAPIHandler

# Initialize handler (uses API key from .env file)
yt_handler = YouTubeAPIHandler()

# Get channel by handle
channel = yt_handler.get_channel_by_handle("@BongPosto")
print(f"Channel: {channel['title']}")

# Get multiple videos in batch
video_ids = ["9hMz-55SBcc", "RUwKcUOdffU", "RGFtyK1yf2A"]
videos = yt_handler.get_videos_by_id(video_ids)
print(f"Retrieved {len(videos)} videos")

# Get channel with recent videos
data = yt_handler.get_channel_recent_videos("@BongPosto", max_videos=10)
print(f"Channel: {data['channel']['title']}")
print(f"Recent videos: {len(data['recent_videos'])}")
```

## API Methods

### Channel Methods

#### `get_channel_by_handle(handle, parts=None)`
Get channel information by handle (@username).

**Parameters:**
- `handle` (str): Channel handle (e.g., "@BongPosto")
- `parts` (List[str], optional): API parts to retrieve

**Returns:** Dictionary with formatted channel data

**Example:**
```python
channel = yt_handler.get_channel_by_handle("@BongPosto")
print(f"Subscribers: {channel['subscriber_count']:,}")
```

#### `get_channels_by_id(channel_ids, parts=None)`
Get multiple channels by ID in batch.

**Parameters:**
- `channel_ids` (List[str]): List of channel IDs
- `parts` (List[str], optional): API parts to retrieve

**Returns:** List of formatted channel dictionaries

**Example:**
```python
channel_ids = ['UCX6OQ3DkcsbYNE6H8uQQuVA', 'UC_x5XG1OV2P6uZZ5FSM9Ttw']
channels = yt_handler.get_channels_by_id(channel_ids)
```

### Video Methods

#### `get_videos_by_id(video_ids, parts=None)`
Get multiple videos by ID in batch.

**Parameters:**
- `video_ids` (List[str]): List of video IDs
- `parts` (List[str], optional): API parts to retrieve

**Returns:** List of formatted video dictionaries

**Example:**
```python
video_ids = ["9hMz-55SBcc", "RUwKcUOdffU"]
videos = yt_handler.get_videos_by_id(video_ids)
```

#### `get_channel_videos_rss(channel_id)`
Get recent videos from channel RSS feed.

**Parameters:**
- `channel_id` (str): YouTube channel ID

**Returns:** List of video dictionaries from RSS feed

**Example:**
```python
rss_videos = yt_handler.get_channel_videos_rss("UCMlzi5avz-Bcn_1A_w-M5cg")
```

### Combined Methods

#### `get_channel_recent_videos(channel_handle, max_videos=15)`
Get channel info and recent videos in one call.

**Parameters:**
- `channel_handle` (str): Channel handle
- `max_videos` (int): Maximum number of recent videos to retrieve

**Returns:** Dictionary with channel info and recent videos

**Example:**
```python
data = yt_handler.get_channel_recent_videos("@BongPosto", max_videos=5)
```

### Batch Processing

#### `batch_process_mixed_requests(requests_config)`
Process multiple different types of requests in batch.

**Parameters:**
- `requests_config` (List[Dict]): List of request configurations

**Request Types:**
- `channel_by_handle`
- `channels_by_id`
- `videos_by_id`
- `channel_rss`
- `channel_recent_videos`

**Example:**
```python
requests_config = [
    {
        'type': 'channel_by_handle',
        'params': {'handle': '@BongPosto'}
    },
    {
        'type': 'videos_by_id',
        'params': {'video_ids': ['9hMz-55SBcc', 'RUwKcUOdffU']}
    }
]
results = yt_handler.batch_process_mixed_requests(requests_config)
```

## Flask API Server

The Flask API server uses configuration from your `.env` file.

Start the server:

```bash
python api_server.py
```

The server will start on the configured host and port (default: `http://0.0.0.0:5000`).

Check server health and configuration:
```bash
curl http://localhost:5000/health
```

### API Endpoints

#### Channel Endpoints
- `GET /api/channel/<handle>` - Get channel by handle
- `POST /api/channels` - Get multiple channels by ID
- `GET /api/channel/<handle>/videos` - Get channel with recent videos
- `GET /api/channel/<channel_id>/rss` - Get channel RSS feed

#### Video Endpoints
- `POST /api/videos` - Get multiple videos by ID

#### Batch Processing
- `POST /api/batch` - Process multiple requests in batch

#### Cache Management
- `GET /api/cache/stats` - Get cache statistics
- `POST /api/cache/clear` - Clear cache

#### Examples
- `GET /examples/bongposto` - BongPosto channel example
- `GET /examples/popular-channels` - Popular channels example
- `GET /examples/batch-demo` - Batch processing demo

#### Documentation
- `GET /api/docs` - API documentation
- `GET /health` - Health check with cache stats

### Example API Usage

```bash
# Get channel by handle
curl "http://localhost:5000/api/channel/@BongPosto"

# Get multiple videos
curl -X POST "http://localhost:5000/api/videos" \
  -H "Content-Type: application/json" \
  -d '{"video_ids": ["9hMz-55SBcc", "RUwKcUOdffU"]}'

# Batch processing
curl -X POST "http://localhost:5000/api/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {
        "type": "channel_by_handle",
        "params": {"handle": "@BongPosto"}
      },
      {
        "type": "videos_by_id",
        "params": {"video_ids": ["9hMz-55SBcc"]}
      }
    ]
  }'
```

## Caching

The library includes intelligent caching with configurable TTL values (set via `.env`):

- **Channel data**: `CACHE_TTL_CHANNEL` (default: 30 minutes)
- **Video data**: `CACHE_TTL_VIDEO` (default: 10 minutes)
- **RSS feeds**: `CACHE_TTL_RSS` (default: 5 minutes)

### Cache Methods

```python
# Get cache statistics
stats = yt_handler.get_cache_stats()
print(f"Cache hits: {stats['hits']}")
print(f"Cache misses: {stats['misses']}")

# Clear cache
yt_handler.clear_cache()
```

## Data Format

### Channel Data Format
```python
{
    'id': 'UCMlzi5avz-Bcn_1A_w-M5cg',
    'title': 'Bong Posto',
    'description': 'Channel description...',
    'custom_url': '@bongposto',
    'handle': '@bongposto',
    'published_at': '2016-12-14T09:00:55Z',
    'thumbnails': {...},
    'country': 'IN',
    'view_count': 2542835345,
    'subscriber_count': 5230000,
    'video_count': 344,
    'privacy_status': 'public',
    'topic_categories': [...],
    'uploads_playlist': 'UUMlzi5avz-Bcn_1A_w-M5cg',
    'raw_data': {...}  # Complete API response
}
```

### Video Data Format
```python
{
    'id': '9hMz-55SBcc',
    'title': 'Every parar parlour wali didi...',
    'description': 'Video description...',
    'channel_id': 'UCMlzi5avz-Bcn_1A_w-M5cg',
    'channel_title': 'Bong Posto',
    'published_at': '2025-06-23T07:49:21Z',
    'thumbnails': {...},
    'category_id': '23',
    'duration': 'PT1M47S',
    'view_count': 4631547,
    'like_count': 138538,
    'comment_count': 766,
    'privacy_status': 'public',
    'embeddable': True,
    'made_for_kids': False,
    'topic_categories': [...],
    'embed_html': '<iframe...>',
    'raw_data': {...}  # Complete API response
}
```

## Rate Limiting

The library implements automatic rate limiting:

- **Minimum interval**: 100ms between requests
- **Automatic retry**: On rate limit errors (429)
- **Exponential backoff**: For persistent errors

## Error Handling

Robust error handling for:

- Network timeouts
- API quota exceeded
- Invalid API keys
- Missing channels/videos
- Rate limiting
- JSON parsing errors

## Examples

Run the comprehensive examples:

```bash
python usage_examples.py
```

This will demonstrate:
1. Single channel retrieval
2. Batch channel processing
3. Batch video processing
4. RSS feed parsing
5. Combined channel + videos
6. Batch mixed requests
7. Cache statistics
8. Cache performance testing
9. Advanced data formatting
10. Error handling

## Configuration

All configuration is managed through environment variables in a `.env` file. Copy `sample.env` to `.env` and customize as needed.

### Required Configuration

```bash
YOUTUBE_API_KEY=your_youtube_api_key_here
```

### Optional Configuration

#### Cache Settings
```bash
CACHE_TTL_CHANNEL=1800      # Channel data cache (30 minutes)
CACHE_TTL_VIDEO=600         # Video data cache (10 minutes)
CACHE_TTL_RSS=300           # RSS feed cache (5 minutes)
DEFAULT_CACHE_TTL=3600      # Default cache TTL (1 hour)
```

#### Rate Limiting
```bash
MIN_REQUEST_INTERVAL=0.1    # Minimum time between requests (100ms)
MAX_RETRIES=3               # Maximum retries for failed requests
RETRY_DELAY=1.0             # Delay between retries (1 second)
```

#### Batch Processing
```bash
MAX_VIDEO_BATCH_SIZE=50     # Videos per batch request
MAX_CHANNEL_BATCH_SIZE=50   # Channels per batch request
MAX_CONCURRENT_WORKERS=5    # Concurrent workers for batch processing
```

#### Flask API Server
```bash
FLASK_HOST=0.0.0.0         # Server host
FLASK_PORT=5000            # Server port
FLASK_DEBUG=True           # Debug mode
```

#### Logging
```bash
LOG_LEVEL=INFO             # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

#### API Parts (comma-separated)
```bash
DEFAULT_CHANNEL_PARTS=contentDetails,snippet,statistics,status
DEFAULT_VIDEO_PARTS=contentDetails,snippet,statistics,status
```

### Configuration Validation

The system automatically validates configuration on startup:

```python
from config import Config

# Check if configuration is valid
Config.validate()

# Get configuration summary
summary = Config.get_config_summary()
print(summary)
```

## Requirements

- Python 3.7+
- requests>=2.31.0
- flask>=2.3.0
- python-dotenv>=1.0.0
- aiohttp>=3.8.0
- xmltodict>=0.13.0

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions:
1. Check the examples in `usage_examples.py`
2. Review the API documentation at `/api/docs`
3. Check the health endpoint at `/health`
4. Enable debug logging for detailed error information 