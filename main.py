import os
import time
import logging
import schedule
from dotenv import load_dotenv
import sys
import argparse

from src.api.bluesky_client import BlueskyClient
from src.bot_handler import BotHandler
from src.utils.config import setup_logging
from src.utils.debug import test_mention_processing, test_video_extraction

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='SharedInventory Bluesky Bot')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--test-mentions', action='store_true', help='Test mention processing')
    parser.add_argument('--test-video', metavar='VIDEO_URL', help='Test video download and processing')
    parser.add_argument('--test-post-video', metavar='POST_URI', help='Test video extraction from a post URI')
    return parser.parse_args()

def main():
    """Main entry point for the SharedInventory Bot"""
    args = parse_args()
    
    # Load environment variables from .env file
    load_dotenv(override=True)
    
    # Setup logging (debug mode if requested)
    log_level = logging.DEBUG if args.debug else None
    setup_logging(log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting SharedInventory Bot")
    
    # Check for required environment variables
    required_env_vars = ["BLUESKY_USERNAME", "BLUESKY_PASSWORD"]
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    # Initialize the Bluesky client
    try:
        # Note: Using atproto==0.0.59 for video download capability
        bluesky_client = BlueskyClient(
            username=os.environ.get("BLUESKY_USERNAME"),
            password=os.environ.get("BLUESKY_PASSWORD"),
            max_retries=3,
            retry_delay=5
        )
        
        # Initialize bot handler
        bot_handler = BotHandler(bluesky_client)
        
        # If in test mode, run the test and exit
        if args.test_mentions:
            logger.info("Running in mention test mode")
            test_mention_processing(bluesky_client, bot_handler)
            return
            
        # If testing video processing from URL
        elif args.test_video:
            from src.video_utils.downloader import download_video
            from src.video_utils.processor import process_video
            from src.utils.config import VIDEOS_DIR
            
            video_url = args.test_video
            output_path = os.path.join(VIDEOS_DIR, f"test_video_{int(time.time())}.mp4")
            
            logger.info(f"Testing video download and processing from: {video_url}")
            if download_video(video_url, output_path):
                logger.info(f"Video downloaded to: {output_path}")
                result = process_video(output_path)
                if "error" in result:
                    logger.error(f"Error processing video: {result['error']}")
                else:
                    logger.info("Video processing successful!")
                    logger.info(f"Audio extracted to: {result['audio_path']}")
                    if result.get('transcript'):
                        logger.info("Transcription successful")
                    if result.get('frames'):
                        logger.info(f"Extracted {len(result['frames'])} frames")
            return
            
        # If testing video extraction from a post URI
        elif args.test_post_video:
            logger.info(f"Testing video extraction from post: {args.test_post_video}")
            test_video_extraction(bluesky_client, args.test_post_video)
            return
        
        # Schedule mention checking every 1 minute
        schedule.every(1).minutes.do(bot_handler.check_mentions)
        logger.info("Scheduled mention checking every 1 minute")
        
        # Run once immediately on startup
        bot_handler.check_mentions()
        
        # Keep the bot running
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
        logger.error("Bot is shutting down due to an error")
        sys.exit(1)

if __name__ == "__main__":
    main()