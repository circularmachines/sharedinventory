#!/usr/bin/env python3
"""
Standalone script to check Bluesky posts for media content (especially videos)
This script will analyze posts and correctly identify media including videos,
even when they might be nested in unusual locations within the post structure.
"""

import os
import sys
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
from dotenv import load_dotenv

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

def extract_video_url(post: Any) -> Optional[str]:
    """
    Extract the video URL from a post, checking multiple possible locations
    
    Args:
        post: A post object from the Bluesky API
        
    Returns:
        The video URL if found, otherwise None
    """
    # Various paths where video URL can be found
    video_url_paths = [
        ['embed', 'media', 'video', 'url'],
        ['embed', 'media', 'items', 0, 'video', 'url'],
        ['embed', 'video', 'url'],
        ['embedView', 'video', 'url'],
        ['record', 'embed', 'media', 'video', 'url'],
        ['record', 'embed', 'media', 'items', 0, 'video', 'url']
    ]
    
    # Check for direct URL
    for path in video_url_paths:
        url = deep_get(post, path)
        if url and isinstance(url, str):
            logger.debug(f"Found video URL at path {path}: {url}")
            return url
    
    # Check for playlist URL (HLS stream)
    playlist_url = deep_get(post, ['embed', 'playlist'])
    if playlist_url:
        logger.debug(f"Found playlist URL: {playlist_url}")
        return playlist_url
    
    # For embedded videos that might require constructing a URL
    ref_link = deep_get(post, ['record', 'embed', 'media', 'video', 'ref', '$link'])
    if ref_link:
        # This is a CID reference - in some cases, videos might be available at a CDN URL
        logger.debug(f"Found video ref link: {ref_link}")
        # Construct potential URL - note: this is implementation dependent
        potential_url = f"https://cdn.bsky.app/img/feed_thumbnail/plain/{ref_link}@jpeg"
        return potential_url
    
    logger.debug("No video URL found")
    return None

class BlueskyMediaChecker:
    """Simple Bluesky client for checking media in posts using public API endpoints"""
    
    def __init__(self, public_api_url: str = "https://public.api.bsky.app/xrpc"):
        self.logger = logging.getLogger(__name__ + ".BlueskyMediaChecker")
        self.public_api_url = public_api_url
        
    def get_post(self, post_uri: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific post by URI using the public API"""
        try:
            self.logger.info(f"Fetching post: {post_uri}")
            
            # Use the public API to fetch the post thread
            endpoint = f"{self.public_api_url}/app.bsky.feed.getPostThread"
            params = {
                "uri": post_uri,
                "depth": 0,
                "parentHeight": 0
            }
            
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            # Extract the post from the thread
            if data and 'thread' in data and 'post' in data['thread']:
                self.logger.info(f"Successfully fetched post")
                return data['thread']['post']
            else:
                self.logger.warning("Post not found or has unexpected format")
                return None
            
        except Exception as e:
            self.logger.error(f"Failed to fetch post: {str(e)}")
            return None
    
    def get_user_posts(self, username: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get posts from a user using the public API"""
        try:
            self.logger.info(f"Fetching up to {limit} posts from @{username}")
            
            # Use the public API to fetch the user's feed
            endpoint = f"{self.public_api_url}/app.bsky.feed.getAuthorFeed"
            params = {
                "actor": username,
                "limit": min(limit, 100)  # API has a maximum limit of 100
            }
            
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            if not data or 'feed' not in data:
                self.logger.warning(f"No posts found for @{username}")
                return []
                
            self.logger.info(f"Found {len(data['feed'])} posts")
            return data['feed']
            
        except Exception as e:
            self.logger.error(f"Error fetching user posts: {str(e)}")
            return []
    
    def check_media(self, post_uri: str, debug: bool = False) -> Dict[str, Any]:
        """Check a post for media content"""
        post = self.get_post(post_uri)
        if not post:
            return {
                'success': False,
                'error': 'Post not found',
                'media_info': None
            }
        
        # Convert the post to an object with attributes for compatibility
        from types import SimpleNamespace
        post_obj = json.loads(json.dumps(post), object_hook=lambda d: SimpleNamespace(**d))
        
        # Detect media
        media_info = detect_post_media(post_obj)
        
        # Extract video URL
        video_url = extract_video_url(post_obj)
        
        # Extract basic post info
        basic_info = {
            'uri': post.get('uri', 'Unknown'),
            'author': post.get('author', {}).get('handle', 'Unknown'),
            'text': post.get('record', {}).get('text', 'No text'),
            'indexed_at': post.get('indexedAt', 'Unknown'),
            'has_media': media_info['has_media'],
            'media_types': media_info['media_types'],
            'media_count': media_info['media_count'],
            'media_urls': media_info['media_urls'],
            'video_url': video_url
        }
        
        result = {
            'success': True,
            'post_info': basic_info,
            'media_info': media_info,
            'raw_post': post if debug else None
        }
        
        return result

def format_time(timestamp):
    """Format a timestamp into a readable date/time"""
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')

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

def print_media_check_result(result, verbose=False):
    """Print the result of a media check in a readable format"""
    if not result['success']:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return
    
    post_info = result['post_info']
    media_info = result['media_info']
    
    # Format time
    formatted_time = format_time(post_info['indexed_at']) if post_info['indexed_at'] != "Unknown" else "Unknown"
    
    # Print post summary
    print(f"\nPost from {formatted_time}")
    print(f"Author: @{post_info['author']}")
    print(f"Text: {post_info['text']}")
    print(f"URI: {post_info['uri']}")
    
    # Print media info
    if media_info['has_media']:
        types_str = ', '.join(media_info['media_types'])
        print(f"✓ Media found: {media_info['media_count']} items [{types_str}]")
        
        # Print URL for video if available
        if 'video' in media_info['media_types'] and post_info.get('video_url'):
            print(f"Video URL: {post_info['video_url']}")
            # Print just the URL on a separate line for easy copying
            print(f"\n{post_info['video_url']}")
    else:
        print("✗ No media detected")
    
    # Print raw media objects in verbose mode
    if verbose and media_info['has_media'] and media_info['raw_media']:
        print("\nRaw media objects:")
        for i, media_obj in enumerate(media_info['raw_media']):
            print(f"Media object {i+1}:")
            print_post_debug(media_obj, indent=2)

def check_media(post_uri: str, debug: bool = False) -> Dict[str, Any]:
    """Main function to check media in a post that can be called from external code"""
    checker = BlueskyMediaChecker()
    return checker.check_media(post_uri, debug)

def main():
    """Main function with hardcoded examples"""
    # Set up debug logging if needed
    debug = True
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize the media checker
    checker = BlueskyMediaChecker()
    
    # Example 1: Check a specific post with a known video
    post_uri = "at://did:plc:evocjxmi5cps2thb4ya5jcji/app.bsky.feed.post/3ll6wm5krgx2l"
    print(f"Example 1: Checking post with URI: {post_uri}")
    result = checker.check_media(post_uri, debug)
    print_media_check_result(result, verbose=True)

if __name__ == "__main__":
    main()