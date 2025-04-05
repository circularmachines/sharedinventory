#!/usr/bin/env python3
"""
Standalone script to check Bluesky posts for media content (especially videos)
This script will analyze posts and correctly identify media including videos,
even when they might be nested in unusual locations within the post structure.
"""

import os
import sys
import argparse
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from atproto import Client

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def deep_get(obj: Any, path: List[str], default=None):
    """Safely get a value from a nested object structure using a path list."""
    current = obj
    for key in path:
        if hasattr(current, key):
            current = getattr(current, key)
        elif isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current

def detect_post_media(post: Any) -> Dict[str, Any]:
    """
    Enhanced function to detect various types of media in a Bluesky post.
    
    This function thoroughly checks all possible locations where media might be stored
    in the post object structure, including nested embeds and different formats.
    
    Args:
        post: A post object from Bluesky API
        
    Returns:
        Dict with media information including:
        - has_media (bool): Whether the post has any media
        - media_types (list): Types of media found (image, video, etc)
        - media_count (int): Number of media items
        - media_urls (list): URLs to media (when available)
        - raw_media (list): Raw media objects for further processing
    """
    media_info = {
        'has_media': False,
        'media_types': [],
        'media_count': 0,
        'media_urls': [],
        'raw_media': []
    }
    
    # Debug: Print full post structure to troubleshoot
    logger.debug(f"Analyzing post structure: {post}")
    
    # Various paths where media can be found in Bluesky post structures
    check_paths = [
        # Common paths for media
        ['embed'],
        ['embedView'],
        ['record', 'embed'],
        ['value', 'embed'],
        
        # Specific paths for feed view structures
        ['post', 'embed'],
        ['post', 'embedView'],
        ['post', 'record', 'embed'],
        
        # Notification structures
        ['subject', 'embed'],
        ['subject', 'embedView']
    ]
    
    # Try each path to find media
    for base_path in check_paths:
        embed = deep_get(post, base_path)
        if not embed:
            continue
            
        # Check for different embedding formats
        
        # 1. Images/Media format with "items"
        media_items = []
        
        # Check direct media items
        if hasattr(embed, 'media') and hasattr(embed.media, 'items'):
            media_items.extend(embed.media.items)
        elif hasattr(embed, 'images'):
            # Some embeds have direct "images" property
            media_items.extend(embed.images)
        
        # Check for "external" embeds with media
        if hasattr(embed, 'external') and hasattr(embed.external, 'thumb'):
            media_info['has_media'] = True
            media_info['media_count'] += 1
            media_info['media_types'].append('thumbnail')
            if hasattr(embed.external.thumb, 'url'):
                media_info['media_urls'].append(embed.external.thumb.url)
            media_info['raw_media'].append(embed.external.thumb)
        
        # 2. Video-specific format
        if hasattr(embed, 'media') and hasattr(embed.media, 'video'):
            media_info['has_media'] = True
            media_info['media_count'] += 1
            media_info['media_types'].append('video')
            if hasattr(embed.media.video, 'url'):
                media_info['media_urls'].append(embed.media.video.url)
            media_info['raw_media'].append(embed.media.video)
        
        # 3. Direct video property
        if hasattr(embed, 'video'):
            media_info['has_media'] = True
            media_info['media_count'] += 1
            media_info['media_types'].append('video')
            if hasattr(embed.video, 'url'):
                media_info['media_urls'].append(embed.video.url)
            media_info['raw_media'].append(embed.video)
            
        # Process any found media items
        for item in media_items:
            media_info['has_media'] = True
            media_info['media_count'] += 1
            
            # Determine media type
            if hasattr(item, 'mime_type'):
                mime = item.mime_type.lower()
                if mime.startswith('image/'):
                    media_info['media_types'].append('image')
                elif mime.startswith('video/'):
                    media_info['media_types'].append('video')
                else:
                    media_info['media_types'].append(mime)
            elif hasattr(item, 'video'):
                media_info['media_types'].append('video')
                if hasattr(item.video, 'url'):
                    media_info['media_urls'].append(item.video.url)
            elif hasattr(item, 'image'):
                media_info['media_types'].append('image')
                if hasattr(item.image, 'url'):
                    media_info['media_urls'].append(item.image.url)
            else:
                # Try to detect type from other properties
                if hasattr(item, 'alt') or hasattr(item, 'aspectRatio'):
                    media_info['media_types'].append('image')
                else:
                    media_info['media_types'].append('unknown')
            
            media_info['raw_media'].append(item)
    
    # Check for blob-type media in record
    if hasattr(post, 'record') and hasattr(post.record, 'blob'):
        media_info['has_media'] = True
        media_info['media_count'] += 1
        media_info['media_types'].append('blob')
        media_info['raw_media'].append(post.record.blob)
    
    # Deduplicate media types
    if media_info['media_types']:
        media_info['media_types'] = list(set(media_info['media_types']))
    
    return media_info

class StandaloneBlueskyClient:
    """Simple Bluesky client without dependencies on other code"""
    
    def __init__(self, username: str, password: str, max_retries: int = 3):
        self.logger = logging.getLogger(__name__ + ".StandaloneBlueskyClient")
        self.username = username
        self.password = password
        self.max_retries = max_retries
        self.client = Client()
        self.authenticated = False
        self._authenticate()
        
    def _authenticate(self) -> bool:
        """Authenticate with the Bluesky API"""
        attempts = 0
        while attempts < self.max_retries:
            try:
                self.logger.info(f"Authenticating as {self.username}")
                response = self.client.login(self.username, self.password)
                self.did = response.did
                self.authenticated = True
                self.logger.info(f"Authentication successful (DID: {self.did})")
                return True
            except Exception as e:
                attempts += 1
                self.logger.error(f"Authentication attempt {attempts} failed: {str(e)}")
        
        self.logger.error(f"Authentication failed after {self.max_retries} attempts")
        return False
    
    def get_post(self, post_uri: str) -> Optional[Any]:
        """Fetch a specific post by URI"""
        if not self.authenticated:
            self.logger.error("Cannot fetch post: Not authenticated")
            return None
        
        try:
            self.logger.info(f"Fetching post: {post_uri}")
            
            # Parse URI to get repository and rkey
            # Format is usually at://did:plc:xxx/app.bsky.feed.post/rkey
            parts = post_uri.split('/')
            
            if len(parts) < 4 or not post_uri.startswith("at://"):
                self.logger.error(f"Invalid post URI format: {post_uri}")
                return None
            
            repository = parts[2]
            rkey = parts[4]
            
            # Use get_post_thread instead of get_post (which doesn't exist)
            response = self.client.app.bsky.feed.get_post_thread({
                'uri': post_uri
            })
            
            if response and hasattr(response, 'thread') and hasattr(response.thread, 'post'):
                self.logger.info(f"Successfully fetched post")
                return response.thread.post
            else:
                self.logger.warning("Post not found or has unexpected format")
                return None
            
        except Exception as e:
            self.logger.error(f"Failed to fetch post: {str(e)}")
            return None
    
    def get_user_posts(self, username: Optional[str] = None, limit: int = 10):
        """Get posts from a user"""
        if not self.authenticated:
            self.logger.error("Cannot fetch posts: Not authenticated")
            return []
            
        try:
            # If no username provided, use the authenticated user
            target_user = username or self.username
            self.logger.info(f"Fetching up to {limit} posts from @{target_user}")
            
            params = {
                'actor': target_user,
                'limit': limit
            }
            
            # Get author feed
            response = self.client.app.bsky.feed.get_author_feed(params)
            
            if not response or not hasattr(response, 'feed'):
                self.logger.warning(f"No posts found for @{target_user}")
                return []
                
            self.logger.info(f"Found {len(response.feed)} posts")
            return response.feed
            
        except Exception as e:
            self.logger.error(f"Error fetching user posts: {str(e)}")
            return []
    
    def get_recent_mentions(self, limit: int = 10):
        """Get recent mentions for the authenticated user"""
        if not self.authenticated:
            self.logger.error("Cannot fetch mentions: Not authenticated")
            return []
            
        try:
            self.logger.info(f"Fetching {limit} recent mentions")
            
            # Get notifications
            response = self.client.app.bsky.notification.list_notifications({
                'limit': limit
            })
            
            if not response or not hasattr(response, 'notifications'):
                self.logger.warning("No notifications returned from API")
                return []
            
            # Filter for mentions only
            mentions = [n for n in response.notifications if n.reason == 'mention']
            self.logger.info(f"Found {len(mentions)} mention notifications")
            return mentions
            
        except Exception as e:
            self.logger.error(f"Failed to fetch mentions: {str(e)}")
            return []

def format_time(timestamp):
    """Format a timestamp into a readable date/time"""
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')

def analyze_post(post, verbose=False):
    """Analyze a post for media content"""
    # Get basic post info
    post_obj = post.post if hasattr(post, 'post') else post
    
    # Extract post text
    text = post_obj.record.text if hasattr(post_obj, 'record') and hasattr(post_obj.record, 'text') else "No text"
    
    # Get post timestamp
    indexed_at = post_obj.indexed_at if hasattr(post_obj, 'indexed_at') else "Unknown"
    formatted_time = format_time(indexed_at) if indexed_at != "Unknown" else "Unknown"
    
    # Get post URI
    uri = post_obj.uri if hasattr(post_obj, 'uri') else "Unknown URI"
    
    # Detect media with our enhanced function
    media_info = detect_post_media(post)
    
    # Format as a structured dictionary
    post_info = {
        'uri': uri,
        'time': formatted_time,
        'text': text,
        'likes': post_obj.like_count if hasattr(post_obj, 'like_count') else 0,
        'reposts': post_obj.repost_count if hasattr(post_obj, 'repost_count') else 0, 
        'has_media': media_info['has_media'],
        'media_types': media_info['media_types'],
        'media_count': media_info['media_count'],
        'media_urls': media_info['media_urls'],
        'full_post': post  # Store full post data for debugging
    }
    
    # Print summary
    print(f"\nPost from {formatted_time}")
    print(f"Text: {post_info['text']}")
    print(f"URI: {uri}")
    
    if media_info['has_media']:
        types_str = ', '.join(media_info['media_types'])
        print(f"✓ Media found: {media_info['media_count']} items [{types_str}]")
        
        # Print URLs for videos if available
        if 'video' in media_info['media_types'] and media_info['media_urls']:
            for i, url in enumerate(media_info['media_urls']):
                print(f"  Video {i+1}: {url}")
    else:
        print("✗ No media detected")
    
    # Print raw media objects in verbose mode
    if verbose and media_info['has_media']:
        print("\nRaw media objects:")
        for i, media_obj in enumerate(media_info['raw_media']):
            print(f"Media object {i+1}:")
            print(json.dumps(media_obj, indent=2, default=str))
    
    return post_info

def print_post_debug(post, indent=0):
    """Recursively print post structure for debugging"""
    indent_str = " " * indent
    if isinstance(post, dict):
        for k, v in post.items():
            if isinstance(v, (dict, list)) or hasattr(v, "__dict__"):
                print(f"{indent_str}{k}:")
                print_post_debug(v, indent+2)
            else:
                print(f"{indent_str}{k}: {v}")
    elif hasattr(post, "__dict__"):
        attributes = dir(post)
        for attr in attributes:
            if not attr.startswith("_") and not callable(getattr(post, attr)):
                value = getattr(post, attr)
                if isinstance(value, (dict, list)) or hasattr(value, "__dict__"):
                    print(f"{indent_str}{attr}:")
                    print_post_debug(value, indent+2)
                else:
                    print(f"{indent_str}{attr}: {value}")
    elif isinstance(post, list):
        for i, item in enumerate(post):
            print(f"{indent_str}[{i}]:")
            print_post_debug(item, indent+2)
    else:
        print(f"{indent_str}{post}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Check Bluesky posts for media content")
    parser.add_argument("--post", help="URI of a specific post to check")
    parser.add_argument("--user", help="Username to check posts from")
    parser.add_argument("--limit", type=int, default=10, help="Number of posts to check")
    parser.add_argument("--mentions", action="store_true", help="Check recent mentions instead of user posts")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--dump", action="store_true", help="Dump full post structure for debugging")
    args = parser.parse_args()
    
    # Set debug level if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # Load environment variables
    load_dotenv()
    
    # Get credentials from environment using BSKY_BOT variables as specified
    username = os.environ.get("BSKY_BOT_USERNAME")
    password = os.environ.get("BSKY_BOT_PASSWORD")
    
    if not username or not password:
        logger.error("Missing Bluesky credentials in environment variables")
        print("Please set BSKY_BOT_USERNAME and BSKY_BOT_PASSWORD environment variables")
        sys.exit(1)
    
    # Initialize client
    client = StandaloneBlueskyClient(username, password)
    if not client.authenticated:
        logger.error("Failed to authenticate with Bluesky")
        sys.exit(1)
    
    # Check a specific post if requested
    if args.post:
        post = client.get_post(args.post)
        if not post:
            logger.error(f"Could not fetch post: {args.post}")
            sys.exit(1)
            
        print(f"Analyzing specific post: {args.post}")
        post_info = analyze_post(post, args.verbose)
        
        # Dump full post structure if requested
        if args.dump:
            print("\n=== Full Post Structure ===")
            print_post_debug(post)
        return
    
    # Check mentions if requested
    if args.mentions:
        mentions = client.get_recent_mentions(args.limit)
        if not mentions:
            print("No mentions found")
            return
            
        print(f"Analyzing {len(mentions)} recent mentions:")
        
        with_media = 0
        with_video = 0
        
        for i, mention in enumerate(mentions, 1):
            print(f"\n===== Mention {i} =====")
            post_info = analyze_post(mention, args.verbose)
            if post_info['has_media']:
                with_media += 1
                if 'video' in post_info['media_types']:
                    with_video += 1
                    
                # Dump full post structure if requested and it has video
                if args.dump and 'video' in post_info['media_types']:
                    print("\n=== Full Post Structure ===")
                    print_post_debug(mention)
        
        # Print summary
        print(f"\n=== Summary ===")
        print(f"Total mentions analyzed: {len(mentions)}")
        print(f"Posts with media: {with_media} ({with_media/len(mentions)*100:.1f}%)")
        print(f"Posts with video: {with_video} ({with_video/len(mentions)*100:.1f}%)")
        return
    
    # Otherwise check user posts
    target_user = args.user or client.username
    posts = client.get_user_posts(target_user, args.limit)
    
    if not posts:
        print(f"No posts found for @{target_user}")
        return
        
    print(f"Analyzing {len(posts)} posts from @{target_user}:")
    
    with_media = 0
    with_video = 0
    
    for i, post_view in enumerate(posts, 1):
        print(f"\n===== Post {i} =====")
        post_info = analyze_post(post_view, args.verbose)
        if post_info['has_media']:
            with_media += 1
            if 'video' in post_info['media_types']:
                with_video += 1
                
                # Dump full post structure if requested and it has video
                if args.dump and 'video' in post_info['media_types']:
                    print("\n=== Full Post Structure ===")
                    print_post_debug(post_view)
    
    # Print summary
    print(f"\n=== Summary ===")
    print(f"Total posts analyzed: {len(posts)}")
    print(f"Posts with media: {with_media} ({with_media/len(posts)*100:.1f}%)")
    print(f"Posts with video: {with_video} ({with_video/len(posts)*100:.1f}%)")

if __name__ == "__main__":
    main()