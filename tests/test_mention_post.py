#!/usr/bin/env python3

import os
import sys
import time
import logging
import argparse
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from atproto import Client

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_test_environment():
    """Load test environment variables."""
    if os.path.exists('.env.test'):
        load_dotenv('.env.test')
        logger.info("Loaded environment from .env.test")
    else:
        logger.warning("No .env.test file found")

def test_post_mention(sender_username, sender_password, recipient_username, message_text, wait_for_reply=True, reply_timeout=60):
    """
    Post a mention to a recipient and optionally wait for a reply.
    
    Args:
        sender_username: Username of the sender
        sender_password: Password of the sender
        recipient_username: Username of the recipient to mention
        message_text: Text message to include in the mention
        wait_for_reply: Whether to wait for a reply
        reply_timeout: How long to wait for a reply (seconds)
        
    Returns:
        Tuple of (success boolean, post URI, reply text if any)
    """
    try:
        # Login with sender account
        client = Client()
        client.login(sender_username, sender_password)
        logger.info(f"Logged in as {sender_username}")
        
        # Make sure the recipient username has the domain if needed
        if '.' not in recipient_username:
            recipient_username = f"{recipient_username}.bsky.social"
        
        # Prepare the post text with mention
        mention_text = f"@{recipient_username}"
        full_text = f"{mention_text} {message_text}"
        
        # Create facets for the mention
        profile = client.get_profile(actor=recipient_username)
        did = profile.did
        
        # Find the byte position of the mention in the text
        text_bytes = full_text.encode('utf-8')
        mention_bytes = mention_text.encode('utf-8')
        start_idx = text_bytes.find(mention_bytes)
        
        facets = []
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
            logger.info(f"Created facet for mention of {mention_text}")
        else:
            logger.warning(f"Could not find mention text in post. No facet created.")
        
        # Post the mention
        response = client.send_post(text=full_text, facets=facets)
        post_uri = response['uri']
        post_cid = response['cid']
        logger.info(f"Posted mention: {post_uri}")
        
        # Optionally wait for a reply
        reply_text = None
        if wait_for_reply:
            start_time = time.time()
            logger.info(f"Waiting up to {reply_timeout} seconds for a reply...")
            
            while time.time() - start_time < reply_timeout:
                try:
                    thread = client.get_post_thread(uri=post_uri)
                    if hasattr(thread.thread, 'replies') and thread.thread.replies:
                        reply = thread.thread.replies[0]
                        reply_text = reply.post.record.text
                        logger.info(f"Got reply: {reply_text}")
                        break
                    logger.info("No replies yet, waiting 5 seconds...")
                    time.sleep(5)
                except Exception as e:
                    logger.error(f"Error checking for replies: {str(e)}")
                    time.sleep(5)
        
        return True, post_uri, reply_text
        
    except Exception as e:
        logger.error(f"Error in test_post_mention: {str(e)}")
        return False, None, None

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test posting mentions to Bluesky")
    parser.add_argument("--sender", help="Sender username")
    parser.add_argument("--recipient", help="Recipient username to mention")
    parser.add_argument("--message", default="This is a test mention posted from the test_mention_post.py script", 
                       help="Message text to include in the post")
    parser.add_argument("--no-wait", action="store_true", 
                       help="Don't wait for a reply")
    parser.add_argument("--timeout", type=int, default=60,
                       help="How long to wait for a reply (seconds)")
    
    args = parser.parse_args()
    
    # Load environment variables
    load_test_environment()
    
    # Get credentials from args or environment
    sender_username = args.sender or os.getenv("TEST_USER_USERNAME")
    sender_password = os.getenv("TEST_USER_PASSWORD")
    recipient_username = args.recipient or os.getenv("BOT_USERNAME")
    
    if not sender_username or not sender_password:
        logger.error("Missing required credentials for sender")
        return 1
    
    if not recipient_username:
        logger.error("Missing recipient username")
        return 1
    
    # Post the mention
    success, post_uri, reply = test_post_mention(
        sender_username,
        sender_password,
        recipient_username,
        args.message,
        not args.no_wait,
        args.timeout
    )
    
    if success:
        logger.info(f"Successfully posted mention: {post_uri}")
        if reply:
            logger.info(f"Received reply: {reply}")
        elif not args.no_wait:
            logger.warning("No reply received within the timeout period")
        return 0
    else:
        logger.error("Failed to post mention")
        return 1
    
if __name__ == "__main__":
    sys.exit(main())