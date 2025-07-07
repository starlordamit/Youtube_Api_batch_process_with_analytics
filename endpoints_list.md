# Complete API Endpoints List

## 🌐 BASE URL: http://localhost:8001

## 📋 ALL AVAILABLE ENDPOINTS

### 🔓 PUBLIC ENDPOINTS (No Authentication Required)
1. GET  /health                    - Server health check
2. GET  /api/docs                  - Interactive documentation

### 🔐 AUTHENTICATED ENDPOINTS (API Key Required)

#### 📺 CHANNEL ENDPOINTS
3. GET  /api/channel/{handle}                     - Get channel by handle
4. GET  /api/channel/{handle}/videos              - Channel with analytics & videos
5. POST /api/channels                             - Batch channels by IDs

#### 🎬 VIDEO ENDPOINTS  
6. POST /api/videos                               - Batch videos by IDs

#### 📡 RSS ENDPOINTS
7. GET  /api/channel/{channel_id}/rss             - Single channel RSS feed  
8. POST /api/rss/channels                         - Batch RSS feeds

#### 🔄 BATCH PROCESSING
9. POST /api/batch                                - Universal batch processor

#### 🗂️ CACHE MANAGEMENT
10. GET  /api/cache/stats                         - Cache statistics
11. POST /api/cache/clear                         - Clear all cache

---
TOTAL: 11 Endpoints (2 Public + 9 Authenticated)

