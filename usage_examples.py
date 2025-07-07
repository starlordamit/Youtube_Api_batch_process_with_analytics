#!/usr/bin/env python3
"""
YouTube API Handler Usage Examples
"""

import time
import json
from youtube_api_handler import YouTubeAPIHandler, YouTubeAPIExample
from config import Config

def main():
    """Main function with comprehensive usage examples"""
    
    try:
        # Initialize the handler (will use .env configuration)
        yt_handler = YouTubeAPIHandler()
        
        # Print configuration summary
        print("=== Configuration Summary ===")
        config_summary = Config.get_config_summary()
        print(json.dumps(config_summary, indent=2))
        print(f"\nAPI Key configured: {'✓' if config_summary['youtube_api_key_set'] else '✗'}")
        
    except Exception as e:
        print(f"❌ Configuration Error: {e}")
        print("\n📝 Setup Instructions:")
        print("1. Create a .env file in the project root")
        print("2. Add your YouTube API key: YOUTUBE_API_KEY=your_key_here")
        print("3. Optionally configure other settings (see .env.example)")
        return
    
    print("=== YouTube API Handler Usage Examples ===\n")
    
    # Example 1: Get single channel by handle
    print("1. Getting channel by handle (@BongPosto):")
    try:
        channel = yt_handler.get_channel_by_handle("@BongPosto")
        if channel:
            print(f"   Channel: {channel['title']}")
            print(f"   Subscribers: {channel['subscriber_count']:,}")
            print(f"   Videos: {channel['video_count']:,}")
            print(f"   Views: {channel['view_count']:,}")
        else:
            print("   Channel not found")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 2: Get multiple channels by ID
    print("2. Getting multiple channels by ID:")
    try:
        channel_ids = [
            'UCX6OQ3DkcsbYNE6H8uQQuVA',  # MrBeast
            'UC_x5XG1OV2P6uZZ5FSM9Ttw',  # Google for Developers
            'UCMlzi5avz-Bcn_1A_w-M5cg'   # Bong Posto
        ]
        channels = yt_handler.get_channels_by_id(channel_ids)
        print(f"   Retrieved {len(channels)} channels:")
        for channel in channels:
            print(f"   - {channel['title']}: {channel['subscriber_count']:,} subscribers")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 3: Get multiple videos by ID
    print("3. Getting multiple videos by ID:")
    try:
        video_ids = [
            "9hMz-55SBcc",  # Every parar parlour wali didi
            "RUwKcUOdffU",  # শাশুড়ি vs বোকা বৌমা
            "RGFtyK1yf2A",  # Free Tickets
            "Kk_r7dacNIs",  # Summer Childhood vs Now
            "gP-6IJ-duBw"   # Random Thoughts We All Have
        ]
        videos = yt_handler.get_videos_by_id(video_ids)
        print(f"   Retrieved {len(videos)} videos:")
        for video in videos:
            print(f"   - {video['title'][:50]}...")
            print(f"     Views: {video['view_count']:,}, Likes: {video['like_count']:,}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 4: Get channel RSS feed
    print("4. Getting channel RSS feed:")
    try:
        channel_id = "UCMlzi5avz-Bcn_1A_w-M5cg"  # Bong Posto
        rss_videos = yt_handler.get_channel_videos_rss(channel_id)
        print(f"   Retrieved {len(rss_videos)} recent videos from RSS:")
        for i, video in enumerate(rss_videos[:5]):  # Show first 5
            print(f"   {i+1}. {video['title'][:50]}...")
            print(f"      Published: {video['published']}")
            print(f"      Views: {video['views']:,}" if video['views'] else "      Views: N/A")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 5: Get channel with recent videos (combined)
    print("5. Getting channel with recent videos:")
    try:
        data = yt_handler.get_channel_recent_videos("@BongPosto", max_videos=5)
        if data:
            channel = data['channel']
            recent_videos = data['recent_videos']
            print(f"   Channel: {channel['title']}")
            print(f"   Recent videos ({len(recent_videos)}):")
            for video in recent_videos:
                print(f"   - {video['title'][:50]}...")
                print(f"     Views: {video['view_count']:,}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 6: Batch processing mixed requests
    print("6. Batch processing mixed requests:")
    try:
        requests_config = [
            {
                'type': 'channel_by_handle',
                'params': {'handle': '@BongPosto'}
            },
            {
                'type': 'channels_by_id',
                'params': {'channel_ids': ['UCX6OQ3DkcsbYNE6H8uQQuVA']}
            },
            {
                'type': 'videos_by_id',
                'params': {'video_ids': ['9hMz-55SBcc', 'RUwKcUOdffU']}
            }
        ]
        
        results = yt_handler.batch_process_mixed_requests(requests_config)
        print(f"   Batch processing completed. Results:")
        for key, result in results.items():
            if result:
                print(f"   - {key}: Success")
            else:
                print(f"   - {key}: Failed")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 7: Cache statistics
    print("7. Cache statistics:")
    try:
        stats = yt_handler.get_cache_stats()
        print(f"   Cache hits: {stats['hits']}")
        print(f"   Cache misses: {stats['misses']}")
        hit_rate = stats['hits'] / (stats['hits'] + stats['misses']) * 100 if (stats['hits'] + stats['misses']) > 0 else 0
        print(f"   Hit rate: {hit_rate:.1f}%")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 8: Testing cache functionality
    print("8. Testing cache functionality:")
    try:
        print("   First request (should miss cache):")
        start_time = time.time()
        channel1 = yt_handler.get_channel_by_handle("@BongPosto")
        time1 = time.time() - start_time
        print(f"   Time taken: {time1:.2f} seconds")
        
        print("   Second request (should hit cache):")
        start_time = time.time()
        channel2 = yt_handler.get_channel_by_handle("@BongPosto")
        time2 = time.time() - start_time
        print(f"   Time taken: {time2:.2f} seconds")
        
        print(f"   Speed improvement: {time1/time2:.1f}x faster")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 9: Advanced filtering and formatting
    print("9. Advanced data formatting:")
    try:
        channel = yt_handler.get_channel_by_handle("@BongPosto")
        if channel:
            print("   Channel Summary:")
            print(f"   Name: {channel['title']}")
            print(f"   Handle: {channel['handle']}")
            print(f"   Country: {channel['country']}")
            print(f"   Published: {channel['published_at']}")
            print(f"   Statistics:")
            print(f"     - Subscribers: {channel['subscriber_count']:,}")
            print(f"     - Total Views: {channel['view_count']:,}")
            print(f"     - Total Videos: {channel['video_count']:,}")
            print(f"   Topic Categories:")
            for category in channel['topic_categories']:
                print(f"     - {category}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 10: Error handling demonstration
    print("10. Error handling demonstration:")
    try:
        # Try to get a non-existent channel
        channel = yt_handler.get_channel_by_handle("@NonExistentChannel123456")
        if channel:
            print(f"   Found channel: {channel['title']}")
        else:
            print("   Channel not found (as expected)")
    except Exception as e:
        print(f"   Error handled gracefully: {e}")
    
    print("\n" + "="*50 + "\n")
    print("All examples completed!")

if __name__ == "__main__":
    main() 