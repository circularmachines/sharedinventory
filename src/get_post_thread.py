#!/usr/bin/env python3
"""
Standalone script to retrieve a full thread for a Bluesky post.
This script focuses on fetching a complete thread given a post URI,
including parent and reply posts.
"""

import os
import sys
import logging
import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
from atproto import Client
import requests

def setup_logging(debug=False):
    """Set up basic logging configuration"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)

class BlueskyThreadFetcher:
    def __init__(self, 
                 username: str = None, 
                 password: str = None, 
                 max_retries: int = 3, 
                 retry_delay: int = 5,
                 public_api_url: str = "https://public.api.bsky.app/xrpc"):
        self.logger = logging.getLogger(__name__)
        self.username = username
        self.password = password
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.public_api_url = public_api_url
        self.client = Client()
        self.authenticated = False
        self.did = None
        
        # Only authenticate if credentials are provided
        if username and password:
            self._authenticate()
    
    def _authenticate(self) -> bool:
        """Authenticate with the Bluesky API"""
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Attempting to authenticate as {self.username}")
                response = self.client.login(self.username, self.password)
                self.did = response.did
                self.authenticated = True
                self.logger.info(f"Authentication successful for {self.username} (DID: {self.did})")
                return True
            except Exception as e:
                self.logger.error(f"Authentication attempt {attempt+1}/{self.max_retries} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    self.logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
        
        self.logger.error(f"Authentication failed after {self.max_retries} attempts")
        return False
    
    def get_post(self, uri: str) -> Optional[Any]:
        """Fetch a specific post by URI"""
        try:
            self.logger.info(f"Fetching post: {uri}")
            
            # Parse URI to get repository and rkey
            # Format is usually at://did:plc:xxx/app.bsky.feed.post/rkey
            parts = uri.split('/')
            
            if len(parts) < 4 or not uri.startswith("at://"):
                self.logger.error(f"Invalid post URI format: {uri}")
                return None
            
            repository = parts[2]
            rkey = parts[4]
            
            # Get post using XRPC API
            response = self.client.app.bsky.feed.get_post({
                'repo': repository,
                'rkey': rkey
            })
            
            self.logger.debug(f"Successfully fetched post")
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to fetch post: {str(e)}")
            return None
    
    def get_post_thread(self, uri: str, depth: int = 5, parent_height: int = 20) -> Optional[Any]:
        """Fetch the complete thread for a post including parents and replies"""
        try:
            self.logger.info(f"Fetching thread for post: {uri} (depth={depth}, parent_height={parent_height})")
            
            # Try using the public API first
            if not self.authenticated:
                try:
                    return self._get_thread_via_public_api(uri, depth, parent_height)
                except Exception as e:
                    self.logger.warning(f"Public API request failed: {str(e)}")
                    self.logger.info("Will attempt to use authenticated client if credentials provided")
                    
                    # If credentials aren't provided, we can't proceed
                    if not self.username or not self.password:
                        raise Exception("Authentication required for this post and no credentials provided")
                    
                    # Otherwise, fall through to authenticated method
            
            # Use authenticated client as fallback or if already authenticated
            response = self.client.app.bsky.feed.get_post_thread({
                'uri': uri,
                'depth': depth,
                'parentHeight': parent_height
            })
            
            if not response or not hasattr(response, 'thread'):
                self.logger.warning("No thread returned from API")
                return None
                
            self.logger.debug(f"Successfully fetched post thread using authenticated client")
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to fetch post thread: {str(e)}")
            return None
            
    def _get_thread_via_public_api(self, uri: str, depth: int = 5, parent_height: int = 20) -> Optional[Any]:
        """Fetch thread using the public API endpoint"""
        self.logger.info(f"Attempting to fetch thread via public API: {uri}")
        
        try:
            # Build request URL and parameters
            endpoint = f"{self.public_api_url}/app.bsky.feed.getPostThread"
            params = {
                "uri": uri,
                "depth": depth,
                "parentHeight": parent_height
            }
            
            # Make the request
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            
            # Convert the JSON response to an object that matches the atproto client's response structure
            data = response.json()
            self.logger.debug("Successfully fetched thread from public API")
            
            # Convert to a compatible format with atproto client
            from types import SimpleNamespace
            return json.loads(json.dumps(data), object_hook=lambda d: SimpleNamespace(**d))
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error fetching thread from public API: {e}")
            if e.response is not None:
                self.logger.error(f"Response status code: {e.response.status_code}")
                self.logger.error(f"Response body: {e.response.text}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch thread from public API: {str(e)}")
            raise

def format_time(timestamp):
    """Format a timestamp into a readable date/time"""
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')

def process_post_info(post_view) -> Dict[str, Any]:
    """Extract key information from a post view"""
    try:
        # Get author information
        author = post_view.author.handle if hasattr(post_view, 'author') and hasattr(post_view.author, 'handle') else "Unknown"
        display_name = post_view.author.display_name if hasattr(post_view, 'author') and hasattr(post_view.author, 'display_name') else None
        
        # Get post text and timestamp
        text = post_view.record.text if hasattr(post_view, 'record') and hasattr(post_view.record, 'text') else ""
        indexed_at = post_view.indexed_at if hasattr(post_view, 'indexed_at') else None
        formatted_time = format_time(indexed_at) if indexed_at else "Unknown"
        
        # Get post identifiers
        uri = post_view.uri if hasattr(post_view, 'uri') else None
        cid = post_view.cid if hasattr(post_view, 'cid') else None
        
        # Check if post is a reply
        is_reply = False
        if hasattr(post_view, 'record') and hasattr(post_view.record, 'reply'):
            is_reply = True
        
        # Check for engagement metrics
        like_count = post_view.like_count if hasattr(post_view, 'like_count') else 0
        reply_count = post_view.reply_count if hasattr(post_view, 'reply_count') else 0
        repost_count = post_view.repost_count if hasattr(post_view, 'repost_count') else 0
        
        return {
            'author': author,
            'display_name': display_name,
            'text': text,
            'time': formatted_time,
            'uri': uri,
            'cid': cid,
            'is_reply': is_reply,
            'likes': like_count,
            'replies': reply_count,
            'reposts': repost_count
        }
    except Exception as e:
        logging.error(f"Error processing post info: {str(e)}")
        return {
            'author': 'Error',
            'text': f'Error processing post: {str(e)}',
            'time': 'Unknown',
            'uri': None
        }

def extract_thread_structure(thread_response) -> Dict[str, Any]:
    """Extract full thread structure from the API response"""
    result = {
        'main_post': None,
        'parent_posts': [],
        'reply_posts': [],
        'thread_depth': 0,
        'has_parent': False,
        'all_post_uris': []  # Added to store all post URIs in the thread
    }
    
    if not thread_response or not hasattr(thread_response, 'thread'):
        return result
    
    try:
        # Extract main post
        main_thread = thread_response.thread
        if hasattr(main_thread, 'post'):
            main_post = process_post_info(main_thread.post)
            result['main_post'] = main_post
            if main_post['uri']:
                result['all_post_uris'].append(main_post['uri'])
            
        # Extract parent posts (going up the thread)
        current = main_thread
        while hasattr(current, 'parent') and current.parent:
            if hasattr(current.parent, 'post'):
                parent_post = process_post_info(current.parent.post)
                result['has_parent'] = True
                result['parent_posts'].append(parent_post)
                if parent_post['uri']:
                    result['all_post_uris'].append(parent_post['uri'])
                current = current.parent
            else:
                break
            
        # Reverse parent posts to get chronological order
        result['parent_posts'].reverse()
        
        # Extract reply posts (going down the thread)
        if hasattr(main_thread, 'replies'):
            for reply in main_thread.replies:
                if hasattr(reply, 'post'):
                    reply_post = process_post_info(reply.post)
                    result['reply_posts'].append(reply_post)
                    if reply_post['uri']:
                        result['all_post_uris'].append(reply_post['uri'])
                    
        # Calculate thread depth
        result['thread_depth'] = len(result['parent_posts']) + 1 + len(result['reply_posts'])
        
        return result
        
    except Exception as e:
        logging.error(f"Error extracting thread structure: {str(e)}")
        return result

def print_thread_summary(thread_structure, detailed=False):
    """Print a readable summary of the thread structure"""
    print("\n" + "="*80)
    
    # Print thread overview
    total_posts = (1 if thread_structure['main_post'] else 0) + \
                  len(thread_structure['parent_posts']) + \
                  len(thread_structure['reply_posts'])
                  
    print(f"Thread with {total_posts} posts (depth: {thread_structure['thread_depth']})")
    
    # Print parent posts
    if thread_structure['parent_posts']:
        print("\nPARENT POSTS:")
        for i, post in enumerate(thread_structure['parent_posts']):
            print(f"{i+1}. {post['time']} by @{post['author']}")
            print(f"   Text: {post['text'][:80]}{'...' if len(post['text']) > 80 else ''}")
            print(f"   URI: {post['uri']}")
            if detailed:
                print(f"   Engagement: {post['likes']} likes, {post['reposts']} reposts, {post['replies']} replies")
            print()
    
    # Print main post
    if thread_structure['main_post']:
        print("\nMAIN POST:")
        post = thread_structure['main_post']
        print(f"{post['time']} by @{post['author']}")
        print(f"Text: {post['text']}")
        print(f"URI: {post['uri']}")
        print(f"Is Reply: {'Yes' if post['is_reply'] else 'No'}")
        if detailed:
            print(f"Engagement: {post['likes']} likes, {post['reposts']} reposts, {post['replies']} replies")
    else:
        print("\nMAIN POST: Not available")
    
    # Print reply posts
    if thread_structure['reply_posts']:
        print("\nREPLY POSTS:")
        for i, post in enumerate(thread_structure['reply_posts']):
            print(f"{i+1}. {post['time']} by @{post['author']}")
            print(f"   Text: {post['text'][:80]}{'...' if len(post['text']) > 80 else ''}")
            print(f"   URI: {post['uri']}")
            if detailed:
                print(f"   Engagement: {post['likes']} likes, {post['reposts']} reposts, {post['replies']} replies")
            print()
    
    # Always output the list of all post URIs for easy parsing
    print("\nALL POST URIs:")
    for uri in thread_structure['all_post_uris']:
        print(uri)
        
    # Output the URIs as JSON for programmatic use
    print("\nPOST URIs (JSON format):")
    print(json.dumps(thread_structure['all_post_uris']))
    
    print("="*80 + "\n")

def get_thread(uri: str, debug: bool = False) -> Dict[str, Any]:
    """Main function to retrieve a thread that can be called from external code"""
    logger = setup_logging(debug)
    
    try:
        # Create client without authentication for public posts
        client = BlueskyThreadFetcher()
        
        # Get post thread
        thread_response = client.get_post_thread(uri, depth=5, parent_height=20)
        
        if not thread_response:
            logger.error(f"No thread found for post URI: {uri}")
            return {
                'success': False,
                'error': 'Thread not found',
                'thread_structure': None
            }
        
        # Extract thread structure
        thread_structure = extract_thread_structure(thread_response)
        
        return {
            'success': True,
            'thread_structure': thread_structure
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'thread_structure': None
        }

def main():
    """Main function for direct script execution"""
    # Set up logging
    logger = setup_logging(debug=True)
    
    # Get post URI from command line or use default example
    post_uri = "at://did:plc:evocjxmi5cps2thb4ya5jcji/app.bsky.feed.post/3llxwrggehi26"
    if len(sys.argv) > 1:
        post_uri = sys.argv[1]
    
    # Fetch the thread
    result = get_thread(post_uri, debug=True)
    
    if result['success']:
        # Print thread details
        print_thread_summary(result['thread_structure'], detailed=True)
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()