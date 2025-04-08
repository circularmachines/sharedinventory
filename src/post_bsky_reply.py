#!/usr/bin/env python3
"""
Post Reply to Bluesky
This script handles posting replies to Bluesky posts, with retry logic and error handling.

Input: Post URI + string below 300 characters
Output: N/A (posts reply to Bluesky)
"""

import os
import sys
import logging
import time
import datetime
from typing import Optional
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

def sanitize_text(text: str) -> str:
    """
    Sanitize text while preserving emojis and other Unicode characters.
    Only removes invalid surrogate pairs if they exist.
    """
    try:
        # Only encode and decode if there are surrogate pairs
        return text.encode('utf-16', 'surrogatepass').decode('utf-16')
    except UnicodeEncodeError:
        # If encoding fails, just return the original text
        return text

class BlueskyReplier:
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

    def post_reply(self, parent_uri: str, reply_text: str) -> bool:
        """
        Post a reply to a Bluesky post
        
        Args:
            parent_uri: URI of the post to reply to
            reply_text: Text content of the reply (must be under 300 chars)
            
        Returns:
            bool: True if reply was posted successfully, False otherwise
        """
        if not self.authenticated:
            self.logger.error("Cannot post reply: Not authenticated")
            return False
            
        if len(reply_text) > 300:
            self.logger.error(f"Reply text exceeds 300 characters (current: {len(reply_text)})")
            return False
            
        try:
            self.logger.info(f"Attempting to reply to post: {parent_uri}")
            self.logger.debug(f"Reply text: {reply_text}")
            
            # Parse the parent URI to get rkey and repo
            repo, collection, rkey = self._parse_at_uri(parent_uri)
            if not all([repo, collection, rkey]):
                self.logger.error("Invalid parent URI format")
                return False
            
            # Create the reply
            for attempt in range(self.max_retries):
                try:
                    # Get the parent post thread for reference
                    parent_thread = self.client.app.bsky.feed.get_post_thread({'uri': parent_uri})
                    parent_post = parent_thread.thread.post
                    
                    # Sanitize text while preserving emojis
                    sanitized_text = sanitize_text(reply_text)
                    
                    # Create reply record - note the correct parameter structure and createdAt
                    response = self.client.app.bsky.feed.post.create(
                        self.did,
                        {
                            'text': sanitized_text,
                            'createdAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            'reply': {
                                'root': {
                                    'uri': parent_uri,
                                    'cid': parent_post.cid
                                },
                                'parent': {
                                    'uri': parent_uri,
                                    'cid': parent_post.cid
                                }
                            }
                        }
                    )
                    
                    self.logger.info("Reply posted successfully")
                    self.logger.debug(f"Response: {response}")
                    return True
                    
                except Exception as e:
                    self.logger.error(f"Attempt {attempt+1}/{self.max_retries} failed: {str(e)}")
                    if attempt < self.max_retries - 1:
                        self.logger.info(f"Retrying in {self.retry_delay} seconds...")
                        time.sleep(self.retry_delay)
            
            self.logger.error(f"Failed to post reply after {self.max_retries} attempts")
            return False
            
        except Exception as e:
            self.logger.error(f"Error posting reply: {str(e)}")
            return False
    
    def _parse_at_uri(self, uri: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Parse an AT Protocol URI into its components"""
        try:
            # Expected format: at://did:plc:xyz/app.bsky.feed.post/timestamp
            if not uri.startswith('at://'):
                return None, None, None
                
            # Remove the 'at://' prefix
            parts = uri[5:].split('/')
            if len(parts) != 3:
                return None, None, None
                
            repo = parts[0]  # did:plc:xyz
            collection = parts[1]  # app.bsky.feed.post
            rkey = parts[2]  # timestamp
            
            return repo, collection, rkey
            
        except Exception as e:
            self.logger.error(f"Error parsing URI {uri}: {str(e)}")
            return None, None, None

def post_reply(post_uri: str, reply_text: str, debug: bool = False) -> bool:
    """
    Main interface function to post a reply to a Bluesky post
    
    Args:
        post_uri: URI of the post to reply to
        reply_text: Text content of the reply (must be under 300 chars)
        debug: Enable debug logging if True
        
    Returns:
        bool: True if reply was posted successfully, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    if debug:
        logger.setLevel(logging.DEBUG)
    
    try:
        # Load environment variables
        load_dotenv()
        
        # Get credentials
        username = os.environ.get("BSKY_BOT_USERNAME")
        password = os.environ.get("BSKY_BOT_PASSWORD")
        
        if not username or not password:
            logger.error("Missing Bluesky credentials in environment variables")
            return False
        
        # Initialize replier
        replier = BlueskyReplier(username=username, password=password)
        
        if not replier.authenticated:
            logger.error("Failed to authenticate with Bluesky")
            return False
        
        # Post the reply
        return replier.post_reply(post_uri, reply_text)
        
    except Exception as e:
        logger.error(f"Error in post_reply: {str(e)}")
        return False

def main():
    """Main function with hardcoded example"""
    # Example post URI and reply
    post_uri = "at://did:plc:evocjxmi5cps2thb4ya5jcji/app.bsky.feed.post/3lmc5zjc5ms23"
    reply_text = "The rhythm of these bongos could echo in a cooperative jam session\u2014shared among musicians, storytellers, or dancers in a community space. Beats travel far, sparking connection across cultures. \ud83c\udfb6"
    
    input("Do you really want to post? overuse is not allowed. Press Enter to continue or Ctrl+C to cancel.")

    # Post reply with debug enabled
    success = post_reply(post_uri, reply_text, debug=True)
    
    if success:
        print("\nReply posted successfully")
    else:
        print("\nFailed to post reply")
        sys.exit(1)

if __name__ == "__main__":
    main()