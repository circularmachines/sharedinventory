from atproto import Client
from typing import List, Dict, Any, Optional
import logging
import time
from ..utils.config import BLUESKY_USERNAME, BLUESKY_PASSWORD

logger = logging.getLogger(__name__)

class BlueskyClient:
    """Client for interacting with the Bluesky API."""
    
    def __init__(self):
        """Initialize the Bluesky client."""
        self.client = Client()
        self.last_notification_seen_at = None
        self._login()
    
    def _login(self):
        """Log in to Bluesky."""
        try:
            self.client.login(BLUESKY_USERNAME, BLUESKY_PASSWORD)
            logger.info(f"Logged in as {BLUESKY_USERNAME}")
        except Exception as e:
            logger.error(f"Failed to login: {str(e)}")
            raise
    
    def get_notifications(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent notifications.
        
        Args:
            limit: Maximum number of notifications to fetch.
            
        Returns:
            List of notification objects.
        """
        try:
            # Get notifications
            response = self.client.app.bsky.notification.list_notifications(limit=limit)
            
            # Update the last seen timestamp
            if not self.last_notification_seen_at:
                # Mark all as read if this is the first time checking
                self.client.app.bsky.notification.update_seen(seen_at=response.seen_at)
                self.last_notification_seen_at = response.seen_at
                return []
            
            # Filter notifications that came after the last check
            new_notifications = []
            for notification in response.notifications:
                if self.last_notification_seen_at and notification.indexed_at > self.last_notification_seen_at:
                    new_notifications.append(notification)
            
            if new_notifications:
                # Update seen timestamp
                self.client.app.bsky.notification.update_seen(seen_at=response.seen_at)
                self.last_notification_seen_at = response.seen_at
            
            return new_notifications
            
        except Exception as e:
            logger.error(f"Error getting notifications: {str(e)}")
            # If there's an auth error, try to login again
            if "Authentication Required" in str(e):
                logger.info("Attempting to re-login")
                self._login()
                return self.get_notifications(limit)
            return []
    
    def filter_mentions(self, notifications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter notifications to only include mentions.
        
        Args:
            notifications: List of notification objects.
            
        Returns:
            List of mention notifications.
        """
        return [n for n in notifications if n.reason == 'mention']
    
    def reply_to_post(self, uri: str, cid: str, text: str) -> bool:
        """
        Reply to a post.
        
        Args:
            uri: URI of the post to reply to.
            cid: CID of the post to reply to.
            text: Text content of the reply.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Create reference to the post we're replying to
            parent_ref = {"uri": uri, "cid": cid}
            
            # Create the reply reference
            reply_ref = {
                "parent": parent_ref,
                "root": parent_ref
            }
            
            # Send the reply
            response = self.client.send_post(
                text=text,
                reply_to=reply_ref
            )
            logger.info(f"Replied to post {uri}")
            return True
        except Exception as e:
            logger.error(f"Error replying to post: {str(e)}")
            return False
    
    def get_post_details(self, uri: str) -> Dict[str, Any]:
        """
        Get details about a post.
        
        Args:
            uri: URI of the post to get details for.
            
        Returns:
            Post details.
        """
        try:
            thread = self.client.get_post_thread(uri=uri)
            return thread
        except Exception as e:
            logger.error(f"Error getting post details: {str(e)}")
            return {}