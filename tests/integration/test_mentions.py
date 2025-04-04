import unittest
import time
import os
import sys
import threading
import logging
import json
import tempfile

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tests.utils import create_test_clients
from tests.test_config import validate_test_config, BOT_USERNAME, BOT_PASSWORD
from src.bot_handler import BotHandler
from src.models.member import Member
from src.db.database import DatabaseHandler
from atproto import Client

logger = logging.getLogger(__name__)

class TestBotClient:
    """Test-specific client for the bot."""
    
    def __init__(self):
        """Initialize the test bot client with test credentials."""
        self.client = Client()
        self.client.login(BOT_USERNAME, BOT_PASSWORD)
        self.last_notification_seen_at = None
        logger.info(f"Test bot client initialized with account: {BOT_USERNAME}")
    
    def filter_mentions(self, notifications):
        """Filter notifications to only include mentions."""
        return [n for n in notifications if n.reason == 'mention']
    
    def get_notifications(self, limit=20):
        """Get notifications with test bot credentials."""
        response = self.client.app.bsky.notification.list_notifications(params={'limit': limit})
        
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
    
    def reply_to_post(self, uri, cid, text):
        """Reply to a post using the test bot account."""
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
            logger.info(f"Bot replied to post {uri}")
            return True
        except Exception as e:
            logger.error(f"Error replying to post: {str(e)}")
            return False
    
    def get_post_details(self, uri):
        """Get details about a post."""
        try:
            thread = self.client.get_post_thread(uri=uri)
            return thread
        except Exception as e:
            logger.error(f"Error getting post details: {str(e)}")
            return {}

class TestMentions(unittest.TestCase):
    """Integration tests for mention handling."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests."""
        # Validate test configuration
        validate_test_config()
        
        # Set up test clients
        cls.clients = create_test_clients()
        
        # Create a temporary directory for test database files
        cls.test_db_dir = tempfile.mkdtemp()
        os.environ["DB_DIRECTORY"] = cls.test_db_dir
        
        # Get profiles for test users
        cls.user1_profile = cls.clients["user1"].get_profile(cls.clients["user1"].username)
        if "user2" in cls.clients:
            cls.user2_profile = cls.clients["user2"].get_profile(cls.clients["user2"].username)
        
        # Initialize database handler with test directory
        cls.db_handler = DatabaseHandler()
        
        # Create the test database files
        with open(os.path.join(cls.test_db_dir, "members.json"), 'w') as f:
            json.dump([], f)
        with open(os.path.join(cls.test_db_dir, "inventory.json"), 'w') as f:
            json.dump([], f)
        
        # Start bot in a separate thread
        cls.stop_event = threading.Event()
        cls.bot_thread = threading.Thread(target=cls._run_bot)
        cls.bot_thread.daemon = True
        cls.bot_thread.start()
        
        # Give the bot a moment to initialize
        time.sleep(2)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests are done."""
        # Stop the bot thread
        cls.stop_event.set()
        cls.bot_thread.join(timeout=5)
        
        # Clean up temporary test database files
        try:
            os.unlink(os.path.join(cls.test_db_dir, "members.json"))
            os.unlink(os.path.join(cls.test_db_dir, "inventory.json"))
            os.rmdir(cls.test_db_dir)
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Error cleaning up test files: {e}")
    
    @classmethod
    def _run_bot(cls):
        """Run the bot in a separate thread."""
        # Create a custom bot client with test credentials
        test_bot_client = TestBotClient()
        
        # Create the bot handler with our custom database
        bot_handler = BotHandler()
        
        # Replace the bot's client with our test client
        bot_handler.bsky_client = test_bot_client
        
        # Modified run method that checks for stop event
        while not cls.stop_event.is_set():
            try:
                bot_handler.check_notifications()
                time.sleep(5)  # Check more frequently in tests
            except Exception as e:
                logger.error(f"Error in bot thread: {str(e)}")
                break
    
    def setUp(self):
        """Set up test environment before each test."""
        # Clear any existing test data
        with open(os.path.join(self.test_db_dir, "members.json"), 'w') as f:
            json.dump([], f)
        with open(os.path.join(self.test_db_dir, "inventory.json"), 'w') as f:
            json.dump([], f)
    
    def test_mention_non_member(self):
        """Test that bot responds correctly when mentioned by a non-member."""
        # Post a mention as test user 1 (non-member)
        post = self.clients["user1"].mention_user(
            BOT_USERNAME,
            "Testing mention from a non-member"
        )
        
        # Wait for the bot to check notifications and respond (max 30 seconds)
        thread = self.clients["user1"].get_post_thread(post["uri"], max_wait=30)
        
        # Check if the bot replied
        self.assertTrue(hasattr(thread.thread, 'replies'), "Bot did not reply to the mention")
        self.assertGreaterEqual(len(thread.thread.replies), 1, "Bot did not reply to the mention")
        
        # Verify the reply mentions joining instructions
        reply_text = thread.thread.replies[0].post.record.text.lower()
        self.assertIn("not currently a member", reply_text)
        self.assertIn("join", reply_text)
    
    def test_mention_member(self):
        """Test that bot responds correctly when mentioned by a member."""
        # Add user1 as a member
        member = Member.from_profile(self.user1_profile)
        self.db_handler.add_member(member.to_dict())
        
        # Post a mention as test user 1 (now a member)
        post = self.clients["user1"].mention_user(
            BOT_USERNAME,
            "Testing mention from a member with an item to add"
        )
        
        # Wait for the bot to check notifications and respond
        thread = self.clients["user1"].get_post_thread(post["uri"], max_wait=30)
        
        # Check if the bot replied
        self.assertTrue(hasattr(thread.thread, 'replies'), "Bot did not reply to the mention")
        self.assertGreaterEqual(len(thread.thread.replies), 1, "Bot did not reply to the mention")
        
        # Verify the reply acknowledges the member
        reply_text = thread.thread.replies[0].post.record.text.lower()
        self.assertIn("thanks for the mention", reply_text)
        self.assertNotIn("not currently a member", reply_text)


if __name__ == "__main__":
    unittest.main()