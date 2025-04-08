#!/usr/bin/env python3
"""
Standalone script to retrieve the feed for a specific Bluesky author.
This script fetches the most recent posts from a given author,
with no authentication required for public profiles.
"""

import os
import sys
import logging
import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
from urllib.parse import quote

def setup_logging(debug=False):
    """Set up basic logging configuration"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)

class BlueskyAuthorFeedFetcher:
    def __init__(self, public_api_url: str = "https://public.api.bsky.app/xrpc"):
        self.logger = logging.getLogger(__name__)
        self.public_api_url = public_api_url
    
    def get_author_feed(self, 
                        actor: str, 
                        limit: int = 20, 
                        cursor: str = None,
                        filter: str = None) -> Optional[Dict[str, Any]]:
        """Fetch the author's feed from the Bluesky public API
        
        Args:
            actor: The DID or handle of the author
            limit: Number of posts to fetch (max 100)
            cursor: Pagination cursor for fetching more posts
            filter: Optional filter ('posts_with_media', 'posts_with_images', 'posts_no_replies', etc.)
        
        Returns:
            Dict containing feed data or None if request failed
        """
        try:
            self.logger.info(f"Fetching author feed for: {actor} (limit={limit})")
            
            # Build request URL
            endpoint = f"{self.public_api_url}/app.bsky.feed.getAuthorFeed"
            params = {
                "actor": actor,
                "limit": min(limit, 100)  # API has a maximum limit of 100
            }
            
            if cursor:
                params["cursor"] = cursor
                
            if filter:
                params["filter"] = filter
            
            # Make the request
            response = requests.get(endpoint, params=params)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            # Parse response
            data = response.json()
            self.logger.debug(f"Successfully fetched author feed with {len(data.get('feed', []))} posts")
            
            return data
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error fetching author feed: {e}")
            if e.response is not None:
                self.logger.error(f"Response status code: {e.response.status_code}")
                self.logger.error(f"Response body: {e.response.text}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to fetch author feed: {str(e)}")
            return None
    
    def extract_posts_with_media(self, feed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract posts containing media from a feed response
        
        Args:
            feed_data: The response from get_author_feed
            
        Returns:
            List of posts containing media
        """
        posts_with_media = []
        
        try:
            if not feed_data or "feed" not in feed_data:
                self.logger.warning("No feed data to extract media from")
                return posts_with_media
            
            for feed_item in feed_data.get("feed", []):
                post = feed_item.get("post", {})
                
                # Check if post has embedded media
                has_media = False
                record = post.get("record", {})
                embed = record.get("embed", {})
                
                if embed:
                    # Check for images
                    if embed.get("$type") == "app.bsky.embed.images":
                        has_media = True
                    
                    # Check for external media (may include videos)
                    elif embed.get("$type") == "app.bsky.embed.external":
                        has_media = True
                    
                    # Check for record with media
                    elif embed.get("$type") == "app.bsky.embed.record":
                        record_embed = embed.get("record", {}).get("embed", {})
                        if record_embed and (
                            record_embed.get("$type") == "app.bsky.embed.images" or
                            record_embed.get("$type") == "app.bsky.embed.external"
                        ):
                            has_media = True
                
                if has_media:
                    # Extract relevant post information
                    post_info = {
                        "uri": post.get("uri"),
                        "cid": post.get("cid"),
                        "author": {
                            "did": post.get("author", {}).get("did"),
                            "handle": post.get("author", {}).get("handle"),
                            "displayName": post.get("author", {}).get("displayName")
                        },
                        "text": record.get("text", ""),
                        "createdAt": record.get("createdAt"),
                        "replyCount": post.get("replyCount", 0),
                        "repostCount": post.get("repostCount", 0),
                        "likeCount": post.get("likeCount", 0),
                        "indexedAt": post.get("indexedAt"),
                        "embed": embed
                    }
                    posts_with_media.append(post_info)
            
            self.logger.info(f"Extracted {len(posts_with_media)} posts with media")
            return posts_with_media
            
        except Exception as e:
            self.logger.error(f"Error extracting posts with media: {str(e)}")
            return []

def format_feed_output(posts: List[Dict[str, Any]], detailed: bool = False) -> None:
    """Print a readable summary of the feed posts
    
    Args:
        posts: List of posts to print
        detailed: Whether to print detailed information
    """
    print("\n" + "="*80)
    print(f"Found {len(posts)} posts with media")
    
    for i, post in enumerate(posts):
        print(f"\n--- Post {i+1} ---")
        print(f"Author: @{post['author']['handle']} ({post['author'].get('displayName', 'No display name')})")
        print(f"Text: {post['text'][:100]}{'...' if len(post['text']) > 100 else ''}")
        print(f"Created: {post.get('createdAt')}")
        print(f"Engagement: {post.get('likeCount', 0)} likes, {post.get('repostCount', 0)} reposts, {post.get('replyCount', 0)} replies")
        print(f"URI: {post.get('uri')}")
        
        if detailed:
            embed_type = post.get('embed', {}).get('$type', 'No embed')
            print(f"Media type: {embed_type}")
            
            # Special handling for different embed types
            if embed_type == "app.bsky.embed.images":
                images = post.get('embed', {}).get('images', [])
                print(f"Images: {len(images)}")
                for j, img in enumerate(images):
                    print(f"  Image {j+1}: {img.get('alt', 'No alt text')}")
            
            elif embed_type == "app.bsky.embed.external":
                external = post.get('embed', {}).get('external', {})
                print(f"External media: {external.get('title', 'No title')}")
                print(f"  URL: {external.get('uri', 'No URL')}")
                print(f"  Description: {external.get('description', 'No description')}")
    
    print("\n" + "="*80)

def get_author_feed(actor: str, limit: int = 20, debug: bool = False) -> Dict[str, Any]:
    """Main function to retrieve author feed that can be called from external code
    
    Args:
        actor: The DID or handle of the author
        limit: Number of posts to fetch
        debug: Whether to enable debug logging
        
    Returns:
        Dictionary with feed data and extracted posts with media
    """
    logger = setup_logging(debug)
    
    try:
        # Create fetcher
        fetcher = BlueskyAuthorFeedFetcher()
        
        # Get author feed
        feed_data = fetcher.get_author_feed(actor=actor, limit=limit)
        
        if not feed_data:
            logger.error(f"No feed data found for actor: {actor}")
            return {
                'success': False,
                'error': 'Feed not found',
                'feed_data': None,
                'posts_with_media': []
            }
        
        # Extract posts with media
        posts_with_media = fetcher.extract_posts_with_media(feed_data)
        
        return {
            'success': True,
            'feed_data': feed_data,
            'posts_with_media': posts_with_media,
            'cursor': feed_data.get('cursor')
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'feed_data': None,
            'posts_with_media': []
        }

def main():
    """Main function for direct script execution"""
    # Set up logging
    logger = setup_logging(debug=True)
    
    # Use a default actor if none provided
    actor = "did:plc:evocjxmi5cps2thb4ya5jcji"  # Replace with desired default
    limit = 20
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        actor = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            limit = int(sys.argv[2])
        except ValueError:
            logger.warning(f"Invalid limit value: {sys.argv[2]}. Using default: 20")
    
    # Fetch the author feed
    result = get_author_feed(actor=actor, limit=limit, debug=True)
    
    if result['success']:
        # Print feed details
        format_feed_output(result['posts_with_media'], detailed=True)
        
        # Show pagination information
        if result.get('cursor'):
            print(f"\nPagination cursor: {result['cursor']}")
            print("Use this cursor to fetch the next page of results")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()