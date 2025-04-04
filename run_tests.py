#!/usr/bin/env python3
import unittest
import argparse
import os
import sys
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def run_integration_tests(test_names=None):
    """Run integration tests."""
    logger.info("Running integration tests...")
    
    # Load the test environment variables
    if os.path.exists('.env.test'):
        load_dotenv('.env.test')
        logger.info("Loaded test environment from .env.test")
    else:
        logger.warning(".env.test file not found. Please create it from .env.test.example")
        return False
    
    # Check if required environment variables are set
    required_vars = [
        "TEST_BOT_USERNAME", "TEST_BOT_PASSWORD", 
        "TEST_USER_USERNAME", "TEST_USER_PASSWORD"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required test environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in .env.test file")
        return False
    
    # Discover and run tests
    loader = unittest.TestLoader()
    
    if test_names:
        suite = unittest.TestSuite()
        for test_name in test_names:
            try:
                test_case = loader.loadTestsFromName(f"tests.integration.{test_name}")
                suite.addTest(test_case)
            except (ImportError, AttributeError):
                logger.error(f"Test '{test_name}' not found")
                return False
    else:
        suite = loader.discover('tests/integration', pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def run_unit_tests():
    """Run unit tests."""
    logger.info("Running unit tests...")
    
    loader = unittest.TestLoader()
    suite = loader.discover('tests/unit', pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run tests for the SharedInventory bot')
    
    parser.add_argument(
        '--type', '-t',
        choices=['all', 'unit', 'integration'],
        default='all',
        help='Type of tests to run'
    )
    
    parser.add_argument(
        '--test', '-n',
        nargs='+',
        help='Specific test names to run (e.g., test_mentions)'
    )
    
    parser.add_argument(
        '--quick-mention', '-q',
        action='store_true',
        help='Run a quick test to trigger a mention from test user 1 to the bot'
    )
    
    args = parser.parse_args()
    
    success = True
    
    if args.quick_mention:
        # Import here to avoid circular imports
        from tests.utils import create_test_clients
        
        try:
            # Load test environment
            load_dotenv('.env.test')
            
            # Create test clients
            clients = create_test_clients()
            user_client = clients.get("user1")
            bot_username = os.getenv("TEST_BOT_USERNAME")
            
            if not user_client or not bot_username:
                logger.error("Could not create test clients or bot username not found")
                return 1
            
            # Post a mention
            post = user_client.mention_user(
                bot_username.split('.')[0],  # Remove .bsky.social if present
                f"Quick test mention created by run_tests.py at {os.popen('date').read().strip()}"
            )
            
            logger.info(f"Successfully posted a mention to {bot_username}")
            logger.info(f"Post URI: {post['uri']}")
            logger.info("Wait a minute for the bot to respond, then check the post on Bluesky")
            
        except Exception as e:
            logger.error(f"Error running quick mention test: {e}")
            return 1
        
        return 0
    
    if args.type in ['all', 'unit']:
        unit_success = run_unit_tests()
        success = success and unit_success
    
    if args.type in ['all', 'integration']:
        integration_success = run_integration_tests(args.test)
        success = success and integration_success
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())