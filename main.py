#!/usr/bin/env python3
"""
Main entry point for the bot.
This script serves as a simple monitor that periodically runs the process module.
"""

import os
import sys
from pathlib import Path

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent))

import time
import logging
from dotenv import load_dotenv
from process import process

# Setup logging
def setup_logging():
    """Configure logging with timestamp and level"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('bot.log')
        ]
    )
    return logging.getLogger(__name__)

def main():
    """Main function that runs the bot monitor"""
    logger = setup_logging()
    logger.info("Starting bot monitor...")
    
    # Load environment variables
    load_dotenv()
    
    # Required environment variables
    required_vars = [
        'BSKY_BOT_USERNAME',
        'BSKY_BOT_PASSWORD',
        'GPT_API_KEY',
        'AZURE_OPENAI_ENDPOINT',
        'GPT_DEPLOYMENT_NAME'
    ]
    
    # Check for required environment variables
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set them in .env file")
        return 1
    
    # Monitor loop
    check_interval = int(os.getenv('CHECK_INTERVAL_SECONDS', '60'))
    logger.info(f"Bot will check for new mentions every {check_interval} seconds")
    
    while True:
        try:
            logger.info("\n=== Starting new processing cycle ===")
            
            # Run the process module
            success = process(debug=False)
            
            if success:
                logger.info("Processing cycle completed successfully")
            else:
                logger.error("Processing cycle failed")
            
            # Sleep until next check
            logger.info(f"Sleeping for {check_interval} seconds...")
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            logger.info("\nBot monitor stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error in monitor loop: {str(e)}")
            time.sleep(check_interval)  # Sleep even on error to avoid rapid retries
    
    return 0

if __name__ == "__main__":
    sys.exit(main())