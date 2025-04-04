import time
from typing import Dict, Any, Optional, List, Tuple
from atproto import Client
import pymongo
import logging
from tests.test_config import (
    BOT_USERNAME, BOT_PASSWORD,
    TEST_USER_USERNAME, TEST_USER_PASSWORD,
    TEST_USER2_USERNAME, TEST_USER2_PASSWORD,
    DB_CONNECTION_STRING, DB_NAME
)

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_utils")

class TestClient:
    """Helper class for interacting with Bluesky API during tests."""
    
    def __init__(self, username: str, password: str):
        """
        Initialize a test client with the given credentials.
        
        Args:
            username: Bluesky username
            password: Bluesky app password
        """
        self.client = Client()
        self.username = username
        self.password = password
        self._login()
    
    def _login(self) -> None:
        """Log in to Bluesky."""
        try:
            self.client.login(self.username, self.password)
            logger.info(f"Logged in as {self.username}")
        except Exception as e:
            logger.error(f"Failed to login as {self.username}: {str(e)}")
            raise
    
    def create_post(self, text: str, facets: List[Dict] = None) -> Dict[str, Any]:
        """
        Create a post with the given text.
        
        Args:
            text: Text content of the post
            facets: Optional list of facets for rich text
            
        Returns:
            Dictionary with uri and cid of the created post
        """
        try:
            response = self.client.send_post(text=text, facets=facets)
            logger.info(f"Created post: {text[:50]}{'...' if len(text) > 50 else ''}")
            return {
                "uri": response["uri"],
                "cid": response["cid"]
            }
        except Exception as e:
            logger.error(f"Failed to create post: {str(e)}")
            raise

    def create_mention_facets(self, text: str, username: str) -> List[Dict]:
        """
        Create facets for mentions in text.
        
        Args:
            text: The post text
            username: The username to mention
            
        Returns:
            List of facet objects
        """
        try:
            # Make sure username doesn't have @ prefix for lookups
            lookup_username = username
            if lookup_username.startswith('@'):
                lookup_username = lookup_username[1:]
                
            # Get the DID for the username
            profile = self.client.get_profile(actor=lookup_username)
            did = profile.did
            
            # Make sure the mention text starts with @ for the post
            mention_text = username
            if not mention_text.startswith('@'):
                mention_text = f"@{mention_text}"
            
            # Find the byte position of the mention in the text
            text_bytes = text.encode('utf-8')
            mention_bytes = mention_text.encode('utf-8')
            start_idx = text_bytes.find(mention_bytes)
            
            if start_idx >= 0:
                end_idx = start_idx + len(mention_bytes)
                logger.info(f"Creating facet for mention of {mention_text} at positions {start_idx}-{end_idx}")
                
                return [{
                    "index": {
                        "byteStart": start_idx,
                        "byteEnd": end_idx
                    },
                    "features": [{
                        "$type": "app.bsky.richtext.facet#mention",
                        "did": did
                    }]
                }]
            else:
                logger.error(f"Could not find mention '{mention_text}' in text: '{text}'")
                return []
        except Exception as e:
            logger.error(f"Error creating mention facets: {str(e)}")
            return []
    
    def mention_user(self, username: str, text: str) -> Dict[str, Any]:
        """
        Create a post that mentions a user.
        
        Args:
            username: Username to mention (including domain if needed)
            text: Text content of the post
            
        Returns:
            Dictionary with uri and cid of the created post
        """
        # Make sure we're using the full handle with .bsky.social suffix if needed
        if '.' not in username:
            username = f"{username}.bsky.social"
        
        # Add @ prefix if not present for display in post
        if not username.startswith('@'):
            mention_text = f"@{username}"
        else:
            mention_text = username
        
        # Create the full post text
        full_text = f"{mention_text} {text}"
        
        # Try creating facets first, fall back to simple mention if it fails
        try:
            # Create facets for the mention to properly notify the user
            facets = self.create_mention_facets(full_text, username)
            if facets:
                # Create the post with facets
                return self.create_post(full_text, facets)
            else:
                # Fall back to simple text mention without facets
                logger.warning(f"Failed to create facets, falling back to text-only mention")
                return self.create_post(full_text)
        except Exception as e:
            logger.error(f"Error in mention_user: {str(e)}, falling back to text-only mention")
            return self.create_post(full_text)
    
    def get_profile(self, username: str) -> Dict[str, Any]:
        """
        Get a user's profile information.
        
        Args:
            username: Username to look up
            
        Returns:
            Profile information
        """
        try:
            profile = self.client.get_profile(actor=username)
            return profile
        except Exception as e:
            logger.error(f"Failed to get profile for {username}: {str(e)}")
            raise
    
    def get_post_thread(self, uri: str, max_wait: int = 30, check_interval: int = 2) -> Dict[str, Any]:
        """
        Get a post thread with retries to check for replies.
        
        Args:
            uri: URI of the post
            max_wait: Maximum time to wait for replies in seconds
            check_interval: How often to check for replies in seconds
            
        Returns:
            Thread information
        """
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                thread = self.client.get_post_thread(uri=uri)
                if hasattr(thread.thread, 'replies') and thread.thread.replies:
                    return thread
                logger.info(f"No replies yet, waiting {check_interval}s...")
                time.sleep(check_interval)
            except Exception as e:
                logger.error(f"Error getting thread: {str(e)}")
                time.sleep(check_interval)
        
        # Return whatever we have after max_wait
        return self.client.get_post_thread(uri=uri)


def setup_test_database() -> pymongo.database.Database:
    """
    Set up a clean test database.
    
    Returns:
        MongoDB database instance
    """
    client = pymongo.MongoClient(DB_CONNECTION_STRING)
    db = client[DB_NAME]
    
    # Clear any existing data
    for collection in db.list_collection_names():
        db[collection].drop()
    
    logger.info(f"Set up clean test database: {DB_NAME}")
    return db


def create_test_clients() -> Dict[str, TestClient]:
    """
    Create test clients for the bot and test users.
    
    Returns:
        Dictionary of TestClient instances
    """
    clients = {}
    
    try:
        clients["bot"] = TestClient(BOT_USERNAME, BOT_PASSWORD)
        clients["user1"] = TestClient(TEST_USER_USERNAME, TEST_USER_PASSWORD)
        
        # Try to create second test client, but don't fail if it doesn't work
        if TEST_USER2_USERNAME and TEST_USER2_PASSWORD:
            try:
                clients["user2"] = TestClient(TEST_USER2_USERNAME, TEST_USER2_PASSWORD)
            except Exception as e:
                logger.warning(f"Could not create test client for user2: {str(e)}")
                logger.warning("Continuing with bot and user1 only")
    
    except Exception as e:
        logger.error(f"Failed to create test clients: {str(e)}")
        raise
    
    return clients