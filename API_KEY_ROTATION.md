# YouTube API Key Rotation Documentation

## Overview

The YouTube API Handler now supports **API key rotation** to maximize your YouTube API rate limits by distributing requests across multiple API keys. This feature allows you to:

- **Increase Effective Rate Limits**: Use multiple API keys to multiply your quota capacity
- **Automatic Rotation**: Intelligent key selection based on configurable strategies
- **Usage Tracking**: Monitor quota usage per key to optimize distribution
- **Failover Protection**: Automatically switch to available keys when others reach limits

## Configuration

### Method 1: Numbered Keys (Recommended)

Set up multiple API keys using numbered environment variables:

```bash
# In your .env or production.env file
YOUTUBE_API_KEY_1=your_first_api_key_here
YOUTUBE_API_KEY_2=your_second_api_key_here
YOUTUBE_API_KEY_3=your_third_api_key_here
YOUTUBE_API_KEY_4=your_fourth_api_key_here
# Add as many as needed...
```

### Method 2: Comma-Separated List

Alternatively, provide a comma-separated list:

```bash
YOUTUBE_API_KEYS=key1,key2,key3,key4,key5
```

### Method 3: Backward Compatibility

Single key configuration still works:

```bash
YOUTUBE_API_KEY=your_single_api_key_here
```

## Rotation Configuration

Configure how keys are rotated and quota limits:

```bash
# Rotation strategy (round_robin, least_used, random)
YOUTUBE_API_KEY_ROTATION_STRATEGY=round_robin

# Quota limits per key per day (adjust based on your actual quotas)
YOUTUBE_API_KEY_DAILY_QUOTA=10000

# Quota limits per key per hour (adjust based on your actual quotas) 
YOUTUBE_API_KEY_HOURLY_QUOTA=1000
```

## Rotation Strategies

### 1. Round Robin (`round_robin`)
- **Default strategy**
- Cycles through keys in sequential order
- Ensures even distribution of requests
- Best for consistent load patterns

### 2. Least Used (`least_used`)
- Selects the key with the lowest daily usage
- Optimizes for maximum quota utilization
- Best for varying load patterns

### 3. Random (`random`)
- Randomly selects from available keys
- Simple and effective for most use cases
- Good for unpredictable traffic patterns

## Usage Statistics

Monitor your API key usage through the dedicated endpoint:

### GET `/api/keys/stats`

```bash
curl -X GET "http://localhost:8000/api/keys/stats?api_key=your_api_key"
```

**Response Example:**
```json
{
  "success": true,
  "data": {
    "rotation_strategy": "round_robin",
    "total_keys": 3,
    "daily_quota_per_key": 10000,
    "hourly_quota_per_key": 1000,
    "key_stats": {
      "key_1": {
        "total_requests": 150,
        "successful_requests": 148,
        "failed_requests": 2,
        "daily_requests": 45,
        "hourly_requests": 12,
        "daily_quota_used_pct": 0.45,
        "hourly_quota_used_pct": 1.2,
        "last_used": "2025-01-01T10:30:00",
        "is_exhausted": false,
        "can_make_request": true
      },
      "key_2": {
        "total_requests": 142,
        "successful_requests": 140,
        "failed_requests": 2,
        "daily_requests": 38,
        "hourly_requests": 8,
        "daily_quota_used_pct": 0.38,
        "hourly_quota_used_pct": 0.8,
        "last_used": "2025-01-01T10:25:00",
        "is_exhausted": false,
        "can_make_request": true
      }
    }
  },
  "meta": {
    "from_cache": false,
    "cache_status": "live",
    "timestamp": "2025-01-01T10:30:00"
  }
}
```

## Key Metrics Explained

- **total_requests**: Total requests made with this key since startup
- **successful_requests**: Number of successful API calls
- **failed_requests**: Number of failed API calls  
- **daily_requests**: Requests made today (resets at midnight)
- **hourly_requests**: Requests made this hour (resets hourly)
- **daily_quota_used_pct**: Percentage of daily quota used
- **hourly_quota_used_pct**: Percentage of hourly quota used
- **last_used**: Timestamp of last usage
- **is_exhausted**: Whether key has reached quota limits
- **can_make_request**: Whether key can make another request

## Quota Management

### Automatic Quota Tracking

The system automatically tracks quota usage per key:

- **Daily Reset**: Quotas reset at midnight UTC
- **Hourly Reset**: Hourly quotas reset at the top of each hour
- **Real-time Monitoring**: Usage is tracked in real-time

### Quota Warnings

The system logs warnings when keys approach quota limits:

```
WARNING: API key key_1 approaching quota limits: Daily: 95.2%, Hourly: 87.3%
```

### Quota Exhaustion Handling

When all keys reach their quotas:

1. System logs error: `"No available API keys - all quota limits reached"`
2. API returns appropriate error responses
3. Quotas automatically reset at next time boundary

## Production Setup

### Example Configuration

For a high-traffic production environment with 5 API keys:

```bash
# Multiple API keys
YOUTUBE_API_KEY_1=AIzaSyC1...
YOUTUBE_API_KEY_2=AIzaSyC2...
YOUTUBE_API_KEY_3=AIzaSyC3...
YOUTUBE_API_KEY_4=AIzaSyC4...
YOUTUBE_API_KEY_5=AIzaSyC5...

# Optimized rotation
YOUTUBE_API_KEY_ROTATION_STRATEGY=least_used

# Production quotas (adjust based on your actual limits)
YOUTUBE_API_KEY_DAILY_QUOTA=10000
YOUTUBE_API_KEY_HOURLY_QUOTA=1000

# Performance settings
MIN_REQUEST_INTERVAL=0.05
MAX_CONCURRENT_WORKERS=10
```

### Monitoring Setup

Monitor your key usage regularly:

1. **Set up alerts** for high quota usage (>90%)
2. **Monitor key distribution** to ensure even usage
3. **Track failure rates** per key
4. **Implement automated scaling** when approaching limits

### Best Practices

1. **Start with 3-5 keys** and scale based on usage
2. **Use `least_used` strategy** for production environments
3. **Set quotas slightly below actual limits** for safety margin
4. **Monitor usage patterns** to optimize key count
5. **Implement backup keys** for critical applications

## Troubleshooting

### Common Issues

**Issue**: "No YouTube API keys configured"
```bash
# Solution: Set at least one API key
YOUTUBE_API_KEY_1=your_api_key_here
```

**Issue**: "All API keys have reached their quota limits"
```bash
# Solutions:
# 1. Add more API keys
# 2. Increase quota limits if you have higher quotas
# 3. Wait for quota reset (daily/hourly)
```

**Issue**: Keys not rotating evenly
```bash
# Solution: Use least_used strategy
YOUTUBE_API_KEY_ROTATION_STRATEGY=least_used
```

### Debug Information

Check the system logs for detailed rotation information:

```bash
# Docker
docker logs youtube-api-container

# Manual deployment
tail -f logs/api.log
```

## API Integration

### Backward Compatibility

Existing code will continue to work without changes. The rotation happens transparently in the background.

### New Features

Access key statistics programmatically:

```python
import requests

response = requests.get('http://localhost:8000/api/keys/stats', 
                       params={'api_key': 'your_api_key'})
stats = response.json()

# Check if any keys are approaching limits
for key_id, key_stats in stats['data']['key_stats'].items():
    if key_stats['daily_quota_used_pct'] > 90:
        print(f"Warning: {key_id} approaching daily limit")
```

## Scaling Calculations

### Effective Rate Limits

With multiple keys, your effective limits multiply:

- **Single Key**: 10,000 requests/day
- **5 Keys**: 50,000 requests/day
- **10 Keys**: 100,000 requests/day

### Planning Your Keys

Calculate required keys based on your traffic:

```
Required Keys = (Daily Requests / Daily Quota per Key) + Safety Margin
```

Example:
- Expected traffic: 75,000 requests/day
- Quota per key: 10,000 requests/day
- Required keys: (75,000 / 10,000) + 2 = 9.5 ≈ 10 keys

## Support

For additional support or feature requests related to API key rotation:

1. Check the system logs for detailed error information
2. Monitor the `/api/keys/stats` endpoint for usage patterns
3. Adjust configuration based on your specific quota limits
4. Consider implementing custom monitoring alerts for production use 