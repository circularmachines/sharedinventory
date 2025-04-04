import logging
import time
import schedule
from typing import Dict, Any, List

from .api.bluesky_client import BlueskyClient
from .db.database import DatabaseHandler
from .utils.config import POLL_INTERVAL

logger = logging.getLogger(__name__)

class BotHandler:
    """Main handler for the SharedInventory bot."""
    
    def __init__(self):
        """Initialize the bot handler."""
        self.bsky_client = BlueskyClient()
        self.db = DatabaseHandler()
        logger.info("Bot handler initialized")
    
    def process_mention(self, notification):
        """
        Process a mention notification.
        
        Args:
            notification: The notification object containing the mention.
        """
        try:
            # Extract information from the notification
            post_uri = notification.uri
            post_cid = notification.cid
            author_did = notification.author.did
            author_handle = notification.author.handle
            
            # Get details about the mentioned post
            post_details = self.bsky_client.get_post_details(post_uri)
            
            # Check if the user is a member
            if not self.db.is_member(author_did):
                # User is not a member, send information about joining
                response = (
                    f"Hi @{author_handle}! You're not currently a member of SharedInventory. "
                    f"To become a member and start adding items to the shared inventory, "
                    f"please DM me with the text 'join SharedInventory'."
                )
                self.bsky_client.reply_to_post(post_uri, post_cid, response)
                return
            
            # For members, process the post content (in Phase 2, we'll add content analysis)
            # For now, just acknowledge the mention
            response = (
                f"Thanks for the mention, @{author_handle}! "
                f"I've noted your post. In the future, I'll analyze your post content "
                f"and add items to the shared inventory."
            )
            self.bsky_client.reply_to_post(post_uri, post_cid, response)
            
        except Exception as e:
            logger.error(f"Error processing mention: {str(e)}")
    
    def check_notifications(self):
        """Check for new notifications and process any mentions."""
        try:
            logger.info("Checking for new notifications")
            
            # Get new notifications
            notifications = self.bsky_client.get_notifications()
            
            if not notifications:
                logger.info("No new notifications found")
                return
            
            logger.info(f"Found {len(notifications)} new notifications")
            
            # Filter for mentions
            mentions = self.bsky_client.filter_mentions(notifications)
            logger.info(f"Found {len(mentions)} mentions")
            
            # Process each mention
            for mention in mentions:
                self.process_mention(mention)
                
        except Exception as e:
            logger.error(f"Error checking notifications: {str(e)}")
    
    def run(self):
        """Run the bot in a loop, checking for notifications periodically."""
        logger.info(f"Starting bot, checking for notifications every {POLL_INTERVAL} seconds")
        
        # Schedule the notification check
        schedule.every(POLL_INTERVAL).seconds.do(self.check_notifications)
        
        # Run once immediately on startup
        self.check_notifications()
        
        # Main loop
        while True:
            schedule.run_pending()
            time.sleep(1)