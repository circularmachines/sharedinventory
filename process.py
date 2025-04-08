#!/usr/bin/env python3
"""
Core processing module that orchestrates the bot's workflow.
This script coordinates the execution of all other modules to:
1. Get mentions
2. Filter unprocessed mentions
3. Check media in posts
4. Download videos
5. Process videos
6. Generate AI prompts
7. Call AI API
8. Post replies
"""

import os
import sys
import json
import logging
from pathlib import Path
import time
from typing import List, Dict, Any, Optional

# Import all component modules
from src.get_mentions import get_mentions
from src.filter_mentions import filter_unprocessed_mentions
from src.check_media import check_media
from src.download_video import download_video
from src.process_video import process_video
from src.compose_ai_prompt import compose_prompt
from src.ai_api_call import AIApiCaller
from src.post_bsky_reply import post_reply
from src.get_post_thread import get_thread

# Setup logging
def setup_logging(debug=False):
    """Configure logging with different levels for standalone vs imported use"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)

def get_root_post_uri(thread_structure: Dict[str, Any]) -> str:
    """Get the URI of the root post in a thread"""
    if thread_structure['parent_posts']:
        return thread_structure['parent_posts'][0]['uri']
    return thread_structure['main_post']['uri']

def is_thread_processed(root_uri: str) -> bool:
    """Check if a thread has already been processed"""
    processed_file = Path("data/processed_threads.txt")
    if not processed_file.exists():
        return False
        
    with open(processed_file, 'r') as f:
        return root_uri in f.read().splitlines()

def mark_thread_processed(root_uri: str) -> None:
    """Mark a thread as processed"""
    processed_file = Path("data/processed_threads.txt")
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(processed_file, 'a') as f:
        f.write(f"{root_uri}\n")

class BotProcessor:
    """Main class to handle bot processing workflow"""
    
    def __init__(self, debug: bool = False):
        self.logger = setup_logging(debug)
        self.debug = debug
        self.ai_caller = AIApiCaller()
        
        # Ensure all required directories exist
        self.setup_directories()
    
    def setup_directories(self):
        """Create necessary directories if they don't exist"""
        data_dir = Path("data")
        dirs = [
            data_dir,
            data_dir / "videos",
            data_dir / "processed_videos",
            data_dir / "processed_videos/audio",
            data_dir / "processed_videos/frames",
            data_dir / "processed_videos/transcripts",
            data_dir / "posts"
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Ensured directory exists: {dir_path}")
    
    def process_mentions(self) -> bool:
        """
        Main processing function that orchestrates the entire workflow
        Returns True if processing completed successfully
        """
        try:
            # Step 1: Get mentions
            self.logger.info("Getting mentions...")
            mentions = get_mentions()
            if not mentions:
                self.logger.info("No mentions found")
                return True
            
          #  # Step 2: Filter unprocessed mentions
          #  self.logger.info("Filtering unprocessed mentions...")
          #  unprocessed = filter_unprocessed_mentions(mentions)
          #  if not unprocessed:
          #      self.logger.info("No unprocessed mentions found")
          #      return True
            
            # Process each unprocessed mention
            for mention_uri in mentions:
                self.logger.info(f"\nProcessing mention: {mention_uri}")
                success = self.process_single_mention(mention_uri)
                if not success:
                    self.logger.error(f"Failed to process mention: {mention_uri}")
                    continue
                
                # Add delay between processing mentions
                time.sleep(2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in process_mentions: {str(e)}")
            return False
    
    def process_single_mention(self, mention_uri: str) -> bool:
        """Process a single mention through the entire workflow"""
        try:
            # Step 2: Get full thread info
            self.logger.info("Getting post thread...")
           
            thread_result = get_thread(mention_uri, debug=self.debug)
            
            if not thread_result['success']:
                self.logger.error("Failed to get thread info")
                return False
                
            thread_structure = thread_result['thread_structure']
            
            # Get root post URI and check if thread already processed
            root_uri = get_root_post_uri(thread_structure)
            if is_thread_processed(root_uri):
                self.logger.info(f"Thread {root_uri} has already been processed")
                return True
            
            # Step 3: Check for media
            self.logger.info("Checking media...")
            media_check = check_media(root_uri, debug=self.debug)
            if not media_check or not media_check.get('success'):
                self.logger.error("Media check failed")
                return False
            
            # Extract video URL if present
            video_url = media_check.get('post_info', {}).get('video_url')
            if not video_url:
                self.logger.info("No video found in post")
                return True
            
            # Step 4: Download video
            self.logger.info("Downloading video...")
            video_path = download_video(video_url, debug=self.debug)
            if not video_path:
                self.logger.error("Video download failed")
                return False
            
            # Step 5: Process video
            self.logger.info("Processing video...")
            video_data = process_video(video_path, debug=self.debug)
            if not video_data:
                self.logger.error("Video processing failed")
                return False
            
            # Step 6: Generate AI prompt
            self.logger.info("Composing AI prompt...")
            messages = compose_prompt(
                transcript_path=video_data.get('transcript_path'),
                system_message_path="src/system_message.md",
                text_content=media_check.get('post_info', {}).get('text'),
                debug=self.debug
            )
            


            if not messages:
                self.logger.error("Failed to compose AI prompt")
                return False
            
            self.logger.info(str(messages))
            
            # Step 7: Call AI API
            self.logger.info("Calling AI API...")
            ai_response = self.ai_caller.call_ai_api(messages)
            if not ai_response or 'error' in ai_response:
                self.logger.error(f"AI API call failed: {ai_response.get('error', 'Unknown error')}")
                return False
            
            # Step 8: Post reply
            self.logger.info("Posting reply...")
            friendly_response = ai_response.get('response', ai_response.get('friendly_response', ''))
            if friendly_response:
                success = post_reply(mention_uri, friendly_response)
                if not success:
                    self.logger.error("Failed to post reply")
                    return False
            else:
                self.logger.error("No valid response from AI")
                return False
            
            # Mark thread as processed using root URI
            mark_thread_processed(root_uri)
            
            self.logger.info("Successfully processed mention")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing mention {mention_uri}: {str(e)}")
            return False

def process(debug: bool = False) -> bool:
    """Main interface function that can be called from external code"""
    processor = BotProcessor(debug=debug)
    return processor.process_mentions()

def main():
    """Main function with hardcoded examples"""
    logger = setup_logging(debug=True)
    logger.info("Starting bot processor...")
    
    success = process(debug=True)
    
    if success:
        print("\nProcessing completed successfully")
        return 0
    else:
        print("\nProcessing failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())