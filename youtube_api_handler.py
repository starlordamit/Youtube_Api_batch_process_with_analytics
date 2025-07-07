import requests
import json
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import logging
from functools import wraps
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import re
from config import Config

# Configure logging
Config.validate()  # Validate configuration on import
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL), format=Config.LOG_FORMAT)
logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Cache entry with expiration"""
    data: Any
    timestamp: datetime
    ttl: int  # Time to live in seconds
    
    def is_expired(self) -> bool:
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl)

class SimpleCache:
    """Simple in-memory cache with TTL support"""
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = {'hits': 0, 'misses': 0}
    
    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            entry = self._cache[key]
            if not entry.is_expired():
                self._stats['hits'] += 1
                return entry.data
            else:
                del self._cache[key]
        self._stats['misses'] += 1
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        self._cache[key] = CacheEntry(value, datetime.now(), ttl)
    
    def clear(self):
        self._cache.clear()
    
    def stats(self) -> Dict[str, int]:
        return self._stats.copy()

def cache_response(ttl: int = 3600):
    """Decorator to cache function responses"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}_{hashlib.md5(str(args + tuple(kwargs.items())).encode()).hexdigest()}"
            
            # Try to get from cache first
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                logger.info(f"Cache hit for {func.__name__}")
                # Return cached data with cache status
                return {
                    'data': cached_result,
                    'from_cache': True,
                    'cache_status': 'hit'
                }
            
            # Execute function and cache result
            result = func(self, *args, **kwargs)
            if result is not None:
                # Cache only the actual data
                self.cache.set(cache_key, result, ttl)
                logger.info(f"Cached result for {func.__name__}")
                # Return with cache status
                return {
                    'data': result,
                    'from_cache': False,
                    'cache_status': 'miss'
                }
            
            return {
                'data': None,
                'from_cache': False,
                'cache_status': 'miss'
            }
        return wrapper
    return decorator

class YouTubeAPIHandler:
    """Comprehensive YouTube API handler with caching and batch processing"""
    
    def __init__(self, api_key: str = None, cache_ttl: int = None, cache_enabled: bool = True):
        self.api_key = api_key or Config.YOUTUBE_API_KEY
        self.base_url = Config.YOUTUBE_API_BASE_URL
        self.cache = SimpleCache() if cache_enabled else None
        self.cache_ttl = cache_ttl or Config.DEFAULT_CACHE_TTL
        self.session = requests.Session()
        
        # Initialize logger first before using it
        self.logger = logging.getLogger(__name__)
        
        # Set timeout for requests
        self.session.timeout = Config.REQUEST_TIMEOUT
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = Config.MIN_REQUEST_INTERVAL
        self.max_retries = Config.MAX_RETRIES
        self.retry_delay = Config.RETRY_DELAY
        
        # Batch size limits
        self.max_video_batch_size = Config.MAX_VIDEO_BATCH_SIZE
        self.max_channel_batch_size = Config.MAX_CHANNEL_BATCH_SIZE
        self.max_concurrent_workers = Config.MAX_CONCURRENT_WORKERS
        
        # Default API parts
        self.default_channel_parts = Config.DEFAULT_CHANNEL_PARTS
        self.default_video_parts = Config.DEFAULT_VIDEO_PARTS
        
        # Load language mappings on initialization
        self.language_mappings = self._load_language_mappings()
        
        # Validate API key
        if not self.api_key:
            raise ValueError("YouTube API key is required. Please set YOUTUBE_API_KEY in your .env file.")
        
        self.logger.info(f"YouTube API Handler initialized with base URL: {self.base_url}")
        self.logger.info(f"Cache TTL: {self.cache_ttl}s, Rate limit: {self.min_request_interval}s")
    
    def _load_language_mappings(self) -> Dict[str, str]:
        """Load language code to name mappings from languagelist.json"""
        try:
            with open('languagelist.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            mappings = {}
            for item in data.get('items', []):
                language_id = item.get('id')
                language_name = item.get('snippet', {}).get('name')
                if language_id and language_name:
                    mappings[language_id] = language_name
            
            self.logger.info(f"Loaded {len(mappings)} language mappings")
            return mappings
        except Exception as e:
            self.logger.error(f"Failed to load language mappings: {e}")
            return {}

    def _get_full_language_name(self, language_code: str) -> str:
        """Convert language code to full language name"""
        if not language_code:
            return "Unknown"
        
        # Handle common variations
        code = language_code.lower()
        
        # Direct lookup
        if language_code in self.language_mappings:
            return self.language_mappings[language_code]
        
        # Try lowercase lookup
        if code in self.language_mappings:
            return self.language_mappings[code]
        
        # Handle common variations like en-US, es-419, etc.
        base_code = code.split('-')[0]
        if base_code in self.language_mappings:
            return self.language_mappings[base_code]
        
        # Fallback to code if not found
        self.logger.warning(f"Language code '{language_code}' not found in mappings")
        return language_code.upper()
    
    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, params: Dict[str, Any] = None) -> Optional[Dict]:
        """Make HTTP request with error handling"""
        try:
            self._rate_limit()
            
            if params is None:
                params = {}
            params['key'] = self.api_key
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error: {e}")
            if response.status_code == 429:
                self.logger.warning("Rate limit exceeded, waiting...")
                time.sleep(1)
                return self._make_request(url, params)
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
        
        return None
    
    def _make_xml_request(self, url: str) -> Optional[str]:
        """Make XML request for RSS feeds"""
        try:
            self._rate_limit()
            response = self.session.get(url)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            self.logger.error(f"XML request error: {e}")
        
        return None
    
    @cache_response(ttl=Config.CACHE_TTL_CHANNEL)  # Configurable cache
    def get_channel_by_handle(self, handle: str, parts: List[str] = None) -> Optional[Dict]:
        """Get channel information by handle (@username)"""
        if parts is None:
            parts = self.default_channel_parts
        
        # Remove @ if present
        handle = handle.lstrip('@')
        
        params = {
            'part': ','.join(parts),
            'forHandle': f'@{handle}'
        }
        
        url = f"{self.base_url}/channels"
        response = self._make_request(url, params)
        
        if response and 'items' in response and response['items']:
            return response['items'][0]  # Return raw data for later formatting
        
        return None
    
    @cache_response(ttl=Config.CACHE_TTL_CHANNEL)  # Configurable cache
    def get_channels_by_id(self, channel_ids: List[str], parts: List[str] = None) -> List[Dict]:
        """Get multiple channels by ID in batch"""
        if parts is None:
            parts = self.default_channel_parts
        
        all_channels = []
        
        # Process in batches
        for i in range(0, len(channel_ids), self.max_channel_batch_size):
            batch = channel_ids[i:i + self.max_channel_batch_size]
            
            params = {
                'part': ','.join(parts),
                'id': ','.join(batch)
            }
            
            url = f"{self.base_url}/channels"
            response = self._make_request(url, params)
            
            if response and 'items' in response:
                for item in response['items']:
                    all_channels.append(item)  # Return raw data for later formatting
        
        return all_channels
    
    @cache_response(ttl=Config.CACHE_TTL_VIDEO)  # Configurable cache
    def get_videos_by_id(self, video_ids: List[str], parts: List[str] = None) -> List[Dict]:
        """Get multiple videos by ID in batch"""
        if parts is None:
            parts = self.default_video_parts
        
        all_videos = []
        
        # Process in batches
        for i in range(0, len(video_ids), self.max_video_batch_size):
            batch = video_ids[i:i + self.max_video_batch_size]
            
            params = {
                'part': ','.join(parts),
                'id': ','.join(batch)
            }
            
            url = f"{self.base_url}/videos"
            response = self._make_request(url, params)
            
            if response and 'items' in response:
                for item in response['items']:
                    all_videos.append(self._format_video_response(item))
        
        return all_videos
    
    @cache_response(ttl=Config.CACHE_TTL_RSS)  # Configurable cache
    def get_channel_videos_rss(self, channel_id: str) -> List[Dict]:
        """Get recent videos from channel RSS feed"""
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        xml_content = self._make_xml_request(url)
        
        if not xml_content:
            return []
        
        return self._parse_rss_feed(xml_content)
    
    def get_channel_recent_videos(self, channel_handle: str, max_videos: int = 15, include_detailed: bool = False) -> Dict:
        """Get channel info and recent videos with comprehensive analytics"""
        # First get channel info
        channel_result = self.get_channel_by_handle(channel_handle)
        if not channel_result or not channel_result.get('data'):
            return {
                'data': {},
                'from_cache': False,
                'cache_status': 'miss'
            }
        
        # Extract raw channel data and basic info
        raw_channel_data = channel_result['data']
        channel_id = raw_channel_data.get('id')
        subscriber_count = int(raw_channel_data.get('statistics', {}).get('subscriberCount', 0))
        
        # Get recent videos from RSS
        rss_result = self.get_channel_videos_rss(channel_id)
        rss_videos = rss_result.get('data', [])
        
        # Get detailed video info for recent videos
        video_ids = [video['video_id'] for video in rss_videos[:max_videos] if video.get('video_id')]
        
        if not video_ids:
            # Format channel data even when no videos found
            formatted_channel = self._format_channel_response(raw_channel_data)
            return {
                'data': {
                    'channel': formatted_channel,
                    'videos': [],
                    'analytics': {
                        'message': 'No videos found for analytics'
                    }
                },
                'from_cache': False,
                'cache_status': 'miss'
            }
        
        # Get detailed video information
        videos_result = self.get_videos_by_id(video_ids)
        detailed_videos = videos_result.get('data', [])
        
        # Add video type information from RSS to detailed videos
        for detailed_video in detailed_videos:
            video_id = detailed_video.get('id')
            for rss_video in rss_videos:
                if rss_video.get('video_id') == video_id:
                    detailed_video['video_type'] = rss_video.get('video_type', 'unknown')
                    detailed_video['rss_url'] = rss_video.get('url', '')
                    break
        
        # Categorize videos by type
        video_categorization = self._categorize_videos_by_type(detailed_videos)
        
        # Calculate metrics for last 6 videos
        metrics_6 = self._calculate_video_metrics(detailed_videos, 6)
        
        # Calculate metrics for last 15 videos
        metrics_15 = self._calculate_video_metrics(detailed_videos, 15)
        
        # Separate videos by type for ER calculation
        shorts_videos = video_categorization['shorts']['videos']
        long_videos = video_categorization['long']['videos']
        
        # Calculate engagement rates
        shorts_er_6 = self._calculate_engagement_rate(shorts_videos, subscriber_count, 6)
        shorts_er_15 = self._calculate_engagement_rate(shorts_videos, subscriber_count, 15)
        long_er_6 = self._calculate_engagement_rate(long_videos, subscriber_count, 6)
        long_er_15 = self._calculate_engagement_rate(long_videos, subscriber_count, 15)
        
        # Determine channel type
        primary_format = self._analyze_channel_type(video_categorization, shorts_er_6, shorts_er_15, long_er_6, long_er_15)
        
        # Analyze channel language from videos
        language_analysis = self._analyze_channel_language(detailed_videos)
        
        # Calculate separate metrics for shorts and long videos
        shorts_metrics_6 = self._calculate_video_metrics(shorts_videos, 6)
        shorts_metrics_15 = self._calculate_video_metrics(shorts_videos, 15)
        long_metrics_6 = self._calculate_video_metrics(long_videos, 6)
        long_metrics_15 = self._calculate_video_metrics(long_videos, 15)
        
        # Channel analysis
        channel_analysis = {
            'primary_format': primary_format,
            'language_analysis': language_analysis
        }
        
        # Generate final optimized metrics
        final_metrics = self._generate_final_metrics(
            channel_analysis, shorts_metrics_6, shorts_metrics_15,
            long_metrics_6, long_metrics_15, shorts_er_6, shorts_er_15,
            long_er_6, long_er_15, video_categorization
        )
        
        # Compile comprehensive analytics (reduced version)
        analytics = {
            'final_metrics': final_metrics
        }
        
        # Only include detailed breakdown if requested (for debugging)
        if include_detailed:
            analytics['detailed_breakdown'] = {
                'overall_metrics': {
                    'last_6_videos': metrics_6,
                    'last_15_videos': metrics_15,
                },
                'shorts_metrics': {
                    'last_6_videos': shorts_metrics_6,
                    'last_15_videos': shorts_metrics_15,
                    'er_last_6': shorts_er_6,
                    'er_last_15': shorts_er_15
                },
                'long_form_metrics': {
                    'last_6_videos': long_metrics_6,
                    'last_15_videos': long_metrics_15,
                    'er_last_6': long_er_6,
                    'er_last_15': long_er_15
                },
                'video_distribution': video_categorization,
                'language_analysis': language_analysis
            }
        
        # Determine cache status
        cache_details = {
            'channel': {
                'from_cache': channel_result.get('from_cache', False),
                'cache_status': channel_result.get('cache_status', 'unknown')
            },
            'rss': {
                'from_cache': rss_result.get('from_cache', False),
                'cache_status': rss_result.get('cache_status', 'unknown')
            },
            'videos': {
                'from_cache': videos_result.get('from_cache', False),
                'cache_status': videos_result.get('cache_status', 'unknown')
            }
        }
        
        # Overall cache status
        all_cached = all(detail.get('from_cache', False) for detail in cache_details.values())
        none_cached = not any(detail.get('from_cache', False) for detail in cache_details.values())
        
        if all_cached:
            overall_status = 'hit'
            from_cache = True
        elif none_cached:
            overall_status = 'miss'
            from_cache = False
        else:
            overall_status = 'partial'
            from_cache = False
        
        # Format channel info with language analysis
        formatted_channel_info = self._format_channel_response(raw_channel_data, language_analysis)
        
        # Build response data - only include videos if detailed is requested
        response_data = {
            'channel': formatted_channel_info,
            'analytics': analytics
        }
        
        # Only include videos array when detailed breakdown is requested
        if include_detailed:
            response_data['videos'] = detailed_videos
        
        return {
            'data': response_data,
            'from_cache': from_cache,
            'cache_status': overall_status,
            'cache_details': cache_details
        }
    
    def _format_channel_response(self, channel_data: Dict, language_analysis: Dict = None) -> Dict:
        """Format channel response with extracted information"""
        snippet = channel_data.get('snippet', {})
        statistics = channel_data.get('statistics', {})
        status = channel_data.get('status', {})
        topic_details = channel_data.get('topicDetails', {})
        content_details = channel_data.get('contentDetails', {})
        
        # Extract email from description
        description = snippet.get('description', '')
        email = self._extract_email_from_text(description)
        
        # Parse categories
        topic_categories = topic_details.get('topicCategories', [])
        categories = self._parse_categories(topic_categories)
        
        # Get language information
        primary_audio_language_code = language_analysis.get('primary_language') if language_analysis else None
        primary_audio_language_name = language_analysis.get('primary_language_name') if language_analysis else None
        default_language_code = snippet.get('defaultLanguage')
        default_language_name = self._get_full_language_name(default_language_code) if default_language_code else None

        formatted_data = {
            'id': channel_data.get('id'),
            'title': snippet.get('title'),
            'description': description,
            'custom_url': snippet.get('customUrl'),
            'handle': snippet.get('customUrl'),
            'published_at': snippet.get('publishedAt'),
            'thumbnails': snippet.get('thumbnails', {}),
            'country': snippet.get('country'),
            'default_language': {
                'code': default_language_code,
                'name': default_language_name
            } if default_language_code else None,  # Channel's default language
            'primary_audio_language': {
                'code': primary_audio_language_code,
                'name': primary_audio_language_name
            } if primary_audio_language_code else None,  # Most common audio language from videos
            'language_confidence': language_analysis.get('language_confidence', 0) if language_analysis else 0,
            'view_count': int(statistics.get('viewCount', 0)),
            'subscriber_count': int(statistics.get('subscriberCount', 0)),
            'video_count': int(statistics.get('videoCount', 0)),
            'privacy_status': status.get('privacyStatus'),
            'categories': categories,  # Beautified categories array
            'topic_categories': topic_categories,  # Original URLs for reference
            'uploads_playlist': content_details.get('relatedPlaylists', {}).get('uploads'),
            'email': email,  # Extracted email
            'verification_status': {
                'has_email': email is not None,
                'has_custom_url': bool(snippet.get('customUrl')),
                'has_description': len(description) > 0,
                'is_verified': status.get('isLinked', False)
            },
            'engagement_data': {
                'avg_views_per_video': int(statistics.get('viewCount', 0)) // max(int(statistics.get('videoCount', 1)), 1),
                'subscriber_to_video_ratio': int(statistics.get('subscriberCount', 0)) // max(int(statistics.get('videoCount', 1)), 1)
            }
        }
        
        return formatted_data
    
    def _format_video_response(self, video_data: Dict) -> Dict:
        """Format video response for consistency"""
        # Get audio language information
        audio_language_code = video_data.get('snippet', {}).get('defaultAudioLanguage')
        audio_language_name = self._get_full_language_name(audio_language_code) if audio_language_code else None

        return {
            'id': video_data.get('id'),
            'title': video_data.get('snippet', {}).get('title'),
            'description': video_data.get('snippet', {}).get('description'),
            'channel_id': video_data.get('snippet', {}).get('channelId'),
            'channel_title': video_data.get('snippet', {}).get('channelTitle'),
            'published_at': video_data.get('snippet', {}).get('publishedAt'),
            'thumbnails': video_data.get('snippet', {}).get('thumbnails', {}),
            'category_id': video_data.get('snippet', {}).get('categoryId'),
            'default_audio_language': {
                'code': audio_language_code,
                'name': audio_language_name
            } if audio_language_code else None,  # Audio language with full name
            'duration': video_data.get('contentDetails', {}).get('duration'),
            'view_count': int(video_data.get('statistics', {}).get('viewCount', 0)),
            'like_count': int(video_data.get('statistics', {}).get('likeCount', 0)),
            'comment_count': int(video_data.get('statistics', {}).get('commentCount', 0)),
            'privacy_status': video_data.get('status', {}).get('privacyStatus'),
            'embeddable': video_data.get('status', {}).get('embeddable'),
            'made_for_kids': video_data.get('status', {}).get('madeForKids'),
            'topic_categories': video_data.get('topicDetails', {}).get('topicCategories', []),
            'embed_html': video_data.get('player', {}).get('embedHtml'),
            'raw_data': video_data
        }
    
    def _parse_rss_feed(self, xml_content: str) -> List[Dict]:
        """Parse YouTube RSS feed XML"""
        try:
            root = ET.fromstring(xml_content)
            
            # Define namespaces
            namespaces = {
                'atom': 'http://www.w3.org/2005/Atom',
                'yt': 'http://www.youtube.com/xml/schemas/2015',
                'media': 'http://search.yahoo.com/mrss/'
            }
            
            videos = []
            
            for entry in root.findall('atom:entry', namespaces):
                video_data = self._parse_rss_video(entry)
                videos.append(video_data)
            
            return videos
            
        except ET.ParseError as e:
            self.logger.error(f"XML parsing error: {e}")
            return []
    
    def _parse_rss_video(self, entry):
        """Parse individual video from RSS entry"""
        link = entry.find('{http://www.w3.org/2005/Atom}link')
        video_url = link.get('href') if link is not None else ''
        
        # Extract video ID from URL
        video_id = ''
        if '/watch?v=' in video_url:
            video_id = video_url.split('/watch?v=')[-1].split('&')[0]
        elif '/shorts/' in video_url:
            video_id = video_url.split('/shorts/')[-1].split('?')[0]
        
        # Categorize video type
        video_type = self._categorize_video_type(video_url)
        
        # Extract media group information
        media_group = entry.find('{http://search.yahoo.com/mrss/}group')
        views = 0
        if media_group is not None:
            media_community = media_group.find('{http://search.yahoo.com/mrss/}community')
            if media_community is not None:
                media_stats = media_community.find('{http://search.yahoo.com/mrss/}statistics')
                if media_stats is not None:
                    views = int(media_stats.get('views', 0))
        
        return {
            'video_id': video_id,
            'title': entry.find('{http://www.w3.org/2005/Atom}title').text if entry.find('{http://www.w3.org/2005/Atom}title') is not None else '',
            'published_at': entry.find('{http://www.w3.org/2005/Atom}published').text if entry.find('{http://www.w3.org/2005/Atom}published') is not None else '',
            'updated_at': entry.find('{http://www.w3.org/2005/Atom}updated').text if entry.find('{http://www.w3.org/2005/Atom}updated') is not None else '',
            'url': video_url,
            'video_type': video_type,  # 'shorts' or 'long'
            'views_from_rss': views
        }
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return self.cache.stats()
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
    
    def _extract_email_from_text(self, text: str) -> Optional[str]:
        """Extract email address from text using regex"""
        if not text:
            return None
        
        # Comprehensive email regex pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, text)
        
        # Return first valid email found
        if matches:
            return matches[0]
        return None
    
    def _parse_categories(self, topic_categories: List[str]) -> List[str]:
        """Parse topic categories from URLs to readable names"""
        if not topic_categories:
            return []
        
        categories = []
        for category_url in topic_categories:
            # Extract category name from Wikipedia URL
            if '/wiki/' in category_url:
                category_name = category_url.split('/wiki/')[-1]
                # Clean up the category name
                category_name = category_name.replace('_', ' ')
                category_name = category_name.replace('(', '').replace(')', '')
                categories.append(category_name)
        
        return categories
    
    def _categorize_video_type(self, url: str) -> str:
        """Categorize video as 'shorts' or 'long' based on URL"""
        if not url:
            return 'unknown'
        
        if '/shorts/' in url:
            return 'shorts'
        elif '/watch?v=' in url:
            return 'long'
        else:
            return 'unknown'
    
    def batch_process_mixed_requests(self, requests_config: List[Dict]) -> Dict:
        """Process multiple different types of requests in batch"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent_workers) as executor:
            futures = {}
            
            for i, config in enumerate(requests_config):
                request_type = config.get('type')
                params = config.get('params', {})
                
                if request_type == 'channel_by_handle':
                    future = executor.submit(self.get_channel_by_handle, **params)
                elif request_type == 'channels_by_id':
                    future = executor.submit(self.get_channels_by_id, **params)
                elif request_type == 'videos_by_id':
                    future = executor.submit(self.get_videos_by_id, **params)
                elif request_type == 'channel_rss':
                    future = executor.submit(self.get_channel_videos_rss, **params)
                elif request_type == 'channel_recent_videos':
                    future = executor.submit(self.get_channel_recent_videos, **params)
                
                futures[future] = f"{request_type}_{i}"
            
            # Collect results
            for future in futures:
                try:
                    result = future.result(timeout=30)
                    results[futures[future]] = result
                except Exception as e:
                    self.logger.error(f"Error in batch request {futures[future]}: {e}")
                    results[futures[future]] = None
        
        return results
    
    def _calculate_video_metrics(self, videos: List[Dict], video_count: int) -> Dict:
        """Calculate metrics for specified number of recent videos"""
        if not videos or video_count <= 0:
            return {
                'video_count': 0,
                'avg_views': 0,
                'avg_likes': 0,
                'avg_comments': 0,
                'total_views': 0,
                'total_likes': 0,
                'total_comments': 0
            }
        
        # Take the specified number of recent videos
        recent_videos = videos[:video_count]
        actual_count = len(recent_videos)
        
        if actual_count == 0:
            return {
                'video_count': 0,
                'avg_views': 0,
                'avg_likes': 0,
                'avg_comments': 0,
                'total_views': 0,
                'total_likes': 0,
                'total_comments': 0
            }
        
        total_views = sum(int(video.get('view_count', 0)) for video in recent_videos)
        total_likes = sum(int(video.get('like_count', 0)) for video in recent_videos)
        total_comments = sum(int(video.get('comment_count', 0)) for video in recent_videos)
        
        return {
            'video_count': actual_count,
            'avg_views': total_views // actual_count,
            'avg_likes': total_likes // actual_count,
            'avg_comments': total_comments // actual_count,
            'total_views': total_views,
            'total_likes': total_likes,
            'total_comments': total_comments
        }
    
    def _calculate_engagement_rate(self, videos: List[Dict], subscriber_count: int, video_count: int) -> float:
        """Calculate engagement rate for specified number of recent videos"""
        if not videos or subscriber_count <= 0 or video_count <= 0:
            return 0.0
        
        # Take the specified number of recent videos
        recent_videos = videos[:video_count]
        
        if not recent_videos:
            return 0.0
        
        total_engagement = 0
        for video in recent_videos:
            likes = int(video.get('like_count', 0))
            comments = int(video.get('comment_count', 0))
            total_engagement += likes + comments
        
        # Calculate engagement rate: (total engagement / subscriber count) * 100
        engagement_rate = (total_engagement / subscriber_count) * 100
        return round(engagement_rate, 4)
    
    def _categorize_videos_by_type(self, videos: List[Dict]) -> Dict:
        """Categorize videos by type (shorts vs long) and calculate separate metrics"""
        shorts_videos = []
        long_videos = []
        
        for video in videos:
            video_type = video.get('video_type', 'unknown')
            if video_type == 'shorts':
                shorts_videos.append(video)
            elif video_type == 'long':
                long_videos.append(video)
        
        return {
            'shorts': {
                'videos': shorts_videos,
                'count': len(shorts_videos)
            },
            'long': {
                'videos': long_videos,
                'count': len(long_videos)
            },
            'total_shorts': len(shorts_videos),
            'total_long': len(long_videos),
            'shorts_percentage': (len(shorts_videos) / len(videos) * 100) if videos else 0,
            'long_percentage': (len(long_videos) / len(videos) * 100) if videos else 0
        }
    
    def _generate_final_metrics(self, channel_analysis: Dict, shorts_metrics_6: Dict, shorts_metrics_15: Dict, 
                                long_metrics_6: Dict, long_metrics_15: Dict, shorts_er_6: float, shorts_er_15: float, 
                                long_er_6: float, long_er_15: float, video_categorization: Dict) -> Dict:
        """Generate final metrics with both long and short format data"""
        
        # Determine primary format (simplified)
        primary_format = channel_analysis.get('primary_format', 'mixed')
        if primary_format == 'shorts':
            channel_type = 'short'
        elif primary_format == 'long':
            channel_type = 'long'
        else:
            # For balanced, choose based on higher average ER
            shorts_avg_er = (shorts_er_6 + shorts_er_15) / 2
            long_avg_er = (long_er_6 + long_er_15) / 2
            channel_type = 'short' if shorts_avg_er > long_avg_er else 'long'
        
        final_metrics = {
            'channel_type': channel_type,
            'short': {
                'last_6_videos': {
                    'avg_views': shorts_metrics_6.get('avg_views', 0),
                    'avg_likes': shorts_metrics_6.get('avg_likes', 0),
                    'avg_comments': shorts_metrics_6.get('avg_comments', 0),
                    'er': shorts_er_6
                },
                'last_15_videos': {
                    'avg_views': shorts_metrics_15.get('avg_views', 0),
                    'avg_likes': shorts_metrics_15.get('avg_likes', 0),
                    'avg_comments': shorts_metrics_15.get('avg_comments', 0),
                    'er': shorts_er_15
                }
            },
            'long': {
                'last_6_videos': {
                    'avg_views': long_metrics_6.get('avg_views', 0),
                    'avg_likes': long_metrics_6.get('avg_likes', 0),
                    'avg_comments': long_metrics_6.get('avg_comments', 0),
                    'er': long_er_6
                },
                'last_15_videos': {
                    'avg_views': long_metrics_15.get('avg_views', 0),
                    'avg_likes': long_metrics_15.get('avg_likes', 0),
                    'avg_comments': long_metrics_15.get('avg_comments', 0),
                    'er': long_er_15
                }
            },
            'content_distribution': {
                'short_count': video_categorization['total_shorts'],
                'long_count': video_categorization['total_long'],
                'short_percent': round(video_categorization['shorts_percentage'], 1),
                'long_percent': round(video_categorization['long_percentage'], 1)
            }
        }
        
        return final_metrics

    def _analyze_channel_type(self, video_categorization: Dict, shorts_er_6: float, shorts_er_15: float, 
                             long_er_6: float, long_er_15: float) -> str:
        """Analyze channel type based on content distribution and engagement rates"""
        
        shorts_percentage = video_categorization['shorts_percentage']
        long_percentage = video_categorization['long_percentage']
        
        # Calculate average engagement rates
        shorts_avg_er = (shorts_er_6 + shorts_er_15) / 2
        long_avg_er = (long_er_6 + long_er_15) / 2
        
        # Determine primary format based on content distribution
        if shorts_percentage >= 70:
            primary_format = 'shorts'
        elif long_percentage >= 70:
            primary_format = 'long'
        else:
            primary_format = 'mixed'
        
        return primary_format

    def _analyze_channel_language(self, videos: List[Dict]) -> Dict:
        """Analyze the most common audio language from channel's videos"""
        
        # Extract audio languages from videos
        audio_languages = []
        for video in videos:
            # Check both API response and RSS parsed data
            audio_lang = None
            
            # Try to get from API response (raw_data)
            raw_data = video.get('raw_data', {})
            if raw_data:
                audio_lang = raw_data.get('snippet', {}).get('defaultAudioLanguage')
            
            # Try to get from direct snippet if not in raw_data
            if not audio_lang:
                audio_lang = video.get('snippet', {}).get('defaultAudioLanguage')
            
            # Try to get from video object itself
            if not audio_lang:
                audio_lang = video.get('defaultAudioLanguage')
            
            if audio_lang:
                audio_languages.append(audio_lang)
        
        # Count frequency of each language
        language_counts = {}
        for lang in audio_languages:
            language_counts[lang] = language_counts.get(lang, 0) + 1
        
        # Find most common language
        most_common_lang = None
        most_common_lang_full = None
        max_count = 0
        if language_counts:
            most_common_lang = max(language_counts, key=language_counts.get)
            most_common_lang_full = self._get_full_language_name(most_common_lang)
            max_count = language_counts[most_common_lang]
        
        # Calculate language distribution with full names
        total_videos_with_lang = len(audio_languages)
        language_distribution = {}
        for lang, count in language_counts.items():
            percentage = (count / total_videos_with_lang * 100) if total_videos_with_lang > 0 else 0
            language_distribution[lang] = {
                'code': lang,
                'name': self._get_full_language_name(lang),
                'count': count,
                'percentage': round(percentage, 1)
            }
        
        return {
            'primary_language': most_common_lang,
            'primary_language_name': most_common_lang_full,
            'language_confidence': round((max_count / total_videos_with_lang * 100), 1) if total_videos_with_lang > 0 else 0,
            'total_videos_analyzed': total_videos_with_lang,
            'language_distribution': language_distribution,
            'languages_detected': list(language_counts.keys())
        }

# Example usage class
class YouTubeAPIExample:
    """Example usage of YouTube API Handler"""
    
    def __init__(self, api_key: str = None):
        self.api_handler = YouTubeAPIHandler(api_key)
    
    def example_single_channel(self):
        """Example: Get single channel by handle"""
        channel = self.api_handler.get_channel_by_handle("@BongPosto")
        print(f"Channel: {channel['title'] if channel else 'Not found'}")
        return channel
    
    def example_batch_videos(self):
        """Example: Get multiple videos in batch"""
        video_ids = [
            "9hMz-55SBcc", "RUwKcUOdffU", "RGFtyK1yf2A",
            "Kk_r7dacNIs", "gP-6IJ-duBw"
        ]
        videos = self.api_handler.get_videos_by_id(video_ids)
        print(f"Retrieved {len(videos)} videos")
        return videos
    
    def example_channel_with_recent_videos(self):
        """Example: Get channel with recent videos"""
        data = self.api_handler.get_channel_recent_videos("@BongPosto", max_videos=10)
        print(f"Channel: {data.get('data', {}).get('channel', {}).get('title', 'Not found')}")
        print(f"Recent videos: {len(data.get('data', {}).get('videos', []))}")
        return data
    
    def example_mixed_batch_requests(self):
        """Example: Mixed batch requests"""
        requests_config = [
            {
                'type': 'channel_by_handle',
                'params': {'handle': '@BongPosto'}
            },
            {
                'type': 'channels_by_id',
                'params': {'channel_ids': ['UCX6OQ3DkcsbYNE6H8uQQuVA', 'UC_x5XG1OV2P6uZZ5FSM9Ttw']}
            },
            {
                'type': 'videos_by_id',
                'params': {'video_ids': ['9hMz-55SBcc', 'RUwKcUOdffU']}
            }
        ]
        
        results = self.api_handler.batch_process_mixed_requests(requests_config)
        print(f"Batch results: {list(results.keys())}")
        return results

if __name__ == "__main__":
    # Example usage using configuration
    try:
        # Initialize handler (will use API key from .env file)
        yt_handler = YouTubeAPIHandler()
        
        # Example usage
        example = YouTubeAPIExample()
        
        # Print configuration summary
        print("Configuration Summary:")
        print(json.dumps(Config.get_config_summary(), indent=2))
        print("\n" + "="*50 + "\n")
        
        # Test single channel
        print("Testing single channel...")
        channel = example.example_single_channel()
        
        # Test batch videos
        print("Testing batch videos...")
        videos = example.example_batch_videos()
        
        # Test channel with recent videos
        print("Testing channel with recent videos...")
        channel_data = example.example_channel_with_recent_videos()
        
        # Test mixed batch requests
        print("Testing mixed batch requests...")
        batch_results = example.example_mixed_batch_requests()
        
        # Print cache stats
        print(f"Cache stats: {yt_handler.get_cache_stats()}")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Please make sure your .env file is configured correctly.")
        print("See the README.md for setup instructions.") 