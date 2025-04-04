import logging
import time
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from atproto import Client
from typing import Dict, Any, List, Optional, Tuple
from tests.utils import TestClient
from tests.test_config import BOT_USERNAME, BOT_PASSWORD, TEST_USER_USERNAME, TEST_USER_PASSWORD

logger = logging.getLogger("debug_utils")

def setup_logging():
    """Set up logging for debug tools."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def check_post_visibility(post_uri: str) -> bool:
    """
    Check if a post is visible on Bluesky.
    
    Args:
        post_uri: URI of the post to check
        
    Returns:
        True if the post is visible, False otherwise
    """
    try:
        # Create a client and login
        client = Client()
        client.login(TEST_USER_USERNAME, TEST_USER_PASSWORD)
        
        # Try to fetch the post
        thread = client.get_post_thread(uri=post_uri)
        logger.info(f"Post found: {post_uri}")
        logger.info(f"Post text: {thread.thread.post.record.text}")
        return True
    except Exception as e:
        logger.error(f"Error checking post visibility: {str(e)}")
        return False

def check_bot_notifications(minutes_back: int = 5) -> List[Dict[str, Any]]:
    """
    Check if the bot has received any notifications recently.
    
    Args:
        minutes_back: Look for notifications from the last N minutes
        
    Returns:
        List of notifications
    """
    try:
        # Create a client and login as the bot
        client = Client()
        client.login(BOT_USERNAME, BOT_PASSWORD)
        
        # Get notifications - Using API properly with params
        response = client.app.bsky.notification.list_notifications(params={'limit': 20})
        
        # Calculate the cutoff time
        cutoff_time = None
        if minutes_back > 0:
            import datetime
            cutoff_time = (datetime.datetime.now(datetime.timezone.utc) - 
                          datetime.timedelta(minutes=minutes_back)).isoformat()
        
        # Filter notifications
        recent_notifications = []
        for notification in response.notifications:
            if cutoff_time is None or notification.indexed_at >= cutoff_time:
                notification_data = {
                    "reason": notification.reason,
                    "author": notification.author.handle,
                    "indexed_at": notification.indexed_at,
                    "uri": notification.uri,
                    "is_read": notification.is_read,
                }
                
                # Try to get text if available
                try:
                    if hasattr(notification.record, 'text'):
                        notification_data["text"] = notification.record.text
                    else:
                        notification_data["text"] = None
                except:
                    notification_data["text"] = None
                    
                recent_notifications.append(notification_data)
        
        if recent_notifications:
            logger.info(f"Found {len(recent_notifications)} recent notifications")
            for i, notif in enumerate(recent_notifications):
                logger.info(f"Notification {i+1}:")
                logger.info(f"  Reason: {notif['reason']}")
                logger.info(f"  Author: {notif['author']}")
                logger.info(f"  Time: {notif['indexed_at']}")
                logger.info(f"  Read: {notif['is_read']}")
                logger.info(f"  Text: {notif['text']}")
        else:
            logger.info(f"No notifications found in the last {minutes_back} minutes")
        
        return recent_notifications
    
    except Exception as e:
        logger.error(f"Error checking bot notifications: {str(e)}")
        return []

def create_mention_facets(text: str, username: str) -> Tuple[List[Dict], str]:
    """
    Create facets for mentions in text.
    
    Args:
        text: The post text
        username: The username to mention
        
    Returns:
        Tuple of (facets, text)
    """
    try:
        # Create a client to resolve the handle to a DID
        client = Client()
        client.login(TEST_USER_USERNAME, TEST_USER_PASSWORD)
        
        # Ensure username has the bsky.social domain
        if '.' not in username:
            username = f"{username}.bsky.social"
        
        # Add @ prefix if not present
        mention_text = username
        if not mention_text.startswith('@'):
            mention_text = f"@{mention_text}"
        
        # Resolve the handle to a DID
        profile = client.get_profile(actor=username)
        did = profile.did
        
        # Find where the mention appears in the text
        mention_bytes = mention_text.encode('utf-8')
        text_bytes = text.encode('utf-8')
        
        # Create facets for the mention
        facets = []
        start_idx = text_bytes.find(mention_bytes)
        
        if start_idx >= 0:
            end_idx = start_idx + len(mention_bytes)
            facets.append({
                "index": {
                    "byteStart": start_idx,
                    "byteEnd": end_idx
                },
                "features": [{
                    "$type": "app.bsky.richtext.facet#mention",
                    "did": did
                }]
            })
            logger.info(f"Created facet for mention of {mention_text} at positions {start_idx}-{end_idx}")
        
        return facets, text
    
    except Exception as e:
        logger.error(f"Error creating facets: {str(e)}")
        return [], text

def debug_mention_flow(post_text: str) -> Tuple[bool, str]:
    """
    Debug the entire mention flow by posting a mention and checking if it appears in notifications.
    
    Args:
        post_text: Text to include in the mention post
        
    Returns:
        Tuple of (success, post_uri)
    """
    try:
        setup_logging()
        logger.info("Starting mention flow debugging...")
        
        # Step 1: Create a test client
        test_client = TestClient(TEST_USER_USERNAME, TEST_USER_PASSWORD)
        
        # Use the full handle including .bsky.social for the mention
        bot_handle = BOT_USERNAME  # already includes .bsky.social
        full_text = f"@{bot_handle} {post_text}"
        
        # Create facets for the mention
        facets, _ = create_mention_facets(full_text, bot_handle)
        
        # Create the post with facets
        logger.info(f"Posting mention with facets to {bot_handle}")
        response = test_client.client.send_post(text=full_text, facets=facets)
        post_uri = response["uri"]
        post_cid = response["cid"]
        
        logger.info(f"Posted mention: {post_uri}")
        
        # Step 2: Verify the post is visible
        logger.info("Verifying post visibility...")
        is_visible = check_post_visibility(post_uri)
        if not is_visible:
            logger.error("Post is not visible!")
            return False, post_uri
        
        # Step 3: Wait for notification processing
        wait_time = 60  # seconds
        logger.info(f"Waiting {wait_time} seconds for notification processing...")
        time.sleep(wait_time)
        
        # Step 4: Check if the bot received the notification
        logger.info("Checking if bot received notification...")
        notifications = check_bot_notifications(minutes_back=10)
        
        # Step 5: Verify if the mention is in the notifications
        mention_found = False
        for notif in notifications:
            if notif["reason"] == "mention" and TEST_USER_USERNAME in notif["author"]:
                mention_found = True
                logger.info("Mention notification found!")
                break
        
        if not mention_found:
            logger.error("Mention notification not found in bot's notifications!")
        
        return mention_found, post_uri
    
    except Exception as e:
        logger.error(f"Error in debug flow: {str(e)}")
        return False, ""

if __name__ == "__main__":
    # If run directly, execute the debug mention flow
    import argparse
    parser = argparse.ArgumentParser(description='Debug Bluesky mention notifications')
    parser.add_argument('--text', default="Testing mention notification flow debugging", 
                      help='Text to include in the mention post')
    parser.add_argument('--check-post', 
                      help='Check visibility of an existing post URI')
    parser.add_argument('--check-notifications', action='store_true',
                      help='Check recent bot notifications')
    parser.add_argument('--minutes', type=int, default=5,
                      help='Minutes back to check for notifications')
                      
    args = parser.parse_args()
    setup_logging()
    
    if args.check_post:
        check_post_visibility(args.check_post)
    elif args.check_notifications:
        check_bot_notifications(args.minutes)
    else:
        success, post_uri = debug_mention_flow(args.text)
        logger.info(f"Debug flow {'succeeded' if success else 'failed'}")