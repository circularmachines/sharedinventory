#!/usr/bin/env python3
"""
Standalone script to check Bluesky notifications for mentions.
This script focuses solely on retrieving recent mentions from Bluesky.
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

def setup_logging():
    """Set up basic logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)

class BlueskyMentionsChecker:
    def __init__(self, username: str, password: str, max_retries: int = 3, retry_delay: int = 5):
        self.logger = logging.getLogger(__name__)
        self.username = username
        self.password = password
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.client = Client()
        self.authenticated = False
        self.did = None
        
        # Authenticate when creating the instance
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
    
    def get_mentions(self, limit: int = 20) -> List[Any]:
        """Fetch recent mentions of the authenticated user"""
        if not self.authenticated:
            self.logger.error("Cannot fetch mentions: Not authenticated")
            return []
        
        try:
            self.logger.info(f"Fetching {limit} recent mentions")
            
            # Get notifications list
            response = self.client.app.bsky.notification.list_notifications({
                'limit': limit
            })
            
            if not response or not hasattr(response, 'notifications'):
                self.logger.warning("No notifications returned from API")
                return []
            
            # Filter for mentions only
            mentions = [n for n in response.notifications if n.reason == 'mention']
            
            # Log details about the response for debugging
            self.logger.debug(f"Received {len(mentions)} mention notifications")
            for i, mention in enumerate(mentions[:10], 1):  # Log first 10 mentions for debugging
                try:
                    author = mention.author.handle
                    reason = mention.reason
                    if hasattr(mention, 'record') and hasattr(mention.record, 'text'):
                        text = mention.record.text[:50] + "..." if len(mention.record.text) > 50 else mention.record.text
                    else:
                        text = "No text available"
                    self.logger.debug(f"DEBUG - Mention {i}: from @{author}, reason: {reason}, text: {text}")
                except Exception as e:
                    self.logger.error(f"Error parsing mention {i}: {str(e)}")
            
            return mentions
            
        except Exception as e:
            self.logger.error(f"Failed to fetch mentions: {str(e)}")
            return []

def format_time(timestamp):
    """Format a timestamp into a readable date/time"""
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')

def is_post_a_reply(mention):
    """Determine if a post is a reply by checking its record"""
    # Direct check of the reply field in record
    if hasattr(mention, 'record') and hasattr(mention.record, 'reply'):
        return True
    
    # For mentions in notification format
    if hasattr(mention, 'post') and hasattr(mention.post, 'record') and hasattr(mention.post.record, 'reply'):
        return True
    
    return False

def process_mentions(client, limit=20):
    """Process recent mentions in notifications"""
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Fetching up to {limit} recent mentions")
        
        # Get mentions using the client's get_mentions method
        mentions = client.get_mentions(limit=limit)
        
        if not mentions:
            logger.warning("No mentions found")
            return []
        
        logger.info(f"Found {len(mentions)} mentions")
        
        processed_mentions = []
        for i, mention in enumerate(mentions):
            # Extract post text
            text = ""
            if hasattr(mention, 'record') and hasattr(mention.record, 'text'):
                text = mention.record.text
            elif hasattr(mention, 'post') and hasattr(mention.post, 'record') and hasattr(mention.post.record, 'text'):
                text = mention.post.record.text
            
            # Get author information
            author = mention.author.handle if hasattr(mention, 'author') and hasattr(mention.author, 'handle') else "Unknown"
            
            # Get post timestamp
            indexed_at = mention.indexed_at if hasattr(mention, 'indexed_at') else "Unknown"
            formatted_time = format_time(indexed_at) if indexed_at != "Unknown" else "Unknown"
            
            # Get URI
            uri = mention.uri if hasattr(mention, 'uri') else None
            
            # Check if post is a reply
            is_reply = is_post_a_reply(mention)
            
            # Format as a readable dictionary
            mention_info = {
                'index': i+1,
                'uri': uri,
                'cid': mention.cid if hasattr(mention, 'cid') else "Unknown",
                'author': author,
                'time': formatted_time,
                'text': text,
                'is_reply': is_reply
            }
            
            processed_mentions.append(mention_info)
        
        return processed_mentions
        
    except Exception as e:
        logger.error(f"Error processing mentions: {str(e)}")
        return []

def get_mentions() -> List[str]:
    """Main interface function that returns a list of mention URIs"""
    logger = setup_logging()
    load_dotenv()
    
    try:
        username = os.environ.get("BSKY_BOT_USERNAME")
        password = os.environ.get("BSKY_BOT_PASSWORD")
        
        if not username or not password:
            logger.error("Missing Bluesky credentials in environment variables")
            return []
            
        client = BlueskyMentionsChecker(
            username=username,
            password=password
        )
        
        if not client.authenticated:
            logger.error("Failed to authenticate with Bluesky")
            return []
        
        mentions = process_mentions(client)
        return [mention['uri'] for mention in mentions if mention['uri']]
        
    except Exception as e:
        logger.error(f"Error getting mentions: {str(e)}")
        return []

def main():
    """Main function to fetch and display mentions"""
    # Set up logging
    logger = setup_logging()
    
    # Load environment variables
    load_dotenv()
    
    # Initialize Bluesky client
    try:
        # Use BSKY_BOT_USERNAME and BSKY_BOT_PASSWORD as specified in instructions
        username = os.environ.get("BSKY_BOT_USERNAME")
        password = os.environ.get("BSKY_BOT_PASSWORD")
        
        if not username or not password:
            logger.error("Missing Bluesky credentials in environment variables")
            logger.error("Please set BSKY_BOT_USERNAME and BSKY_BOT_PASSWORD in .env file")
            sys.exit(1)
            
        client = BlueskyMentionsChecker(
            username=username,
            password=password
        )
        
        if not client.authenticated:
            logger.error("Failed to authenticate with Bluesky")
            sys.exit(1)
        
        # Get recent mentions
        mentions = process_mentions(client)
        
        # Print mentions
        print(f"\n{'='*80}\n")
        print(f"Recent mentions for @{client.username}:\n")
        
        if not mentions:
            print("No mentions found.")
            return
        
        # Get post URIs
        mention_uris = [mention['uri'] for mention in mentions if mention['uri']]
        
        # Print mentions
        for mention in mentions:
            print(f"{mention['index']}. {mention['time']} by @{mention['author']}")
            print(f"   Text: {mention['text'][:80]}{'...' if len(mention['text']) > 80 else ''}")
            print(f"   Is Reply: {'Yes' if mention['is_reply'] else 'No'}")
            print(f"   URI: {mention['uri']}")
            print()
        
        # Output the list of URIs in JSON format for piping to other scripts
        print("\nMention URIs (JSON format):")
        print(json.dumps(mention_uris))
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
