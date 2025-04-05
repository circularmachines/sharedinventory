#!/usr/bin/env python3
"""
Standalone script to download videos from Bluesky posts.
This script focuses on retrieving video content from a post URI.

Usage:
  python download_video.py <post_uri> [--output-dir DIRECTORY]
  
Example:
  python download_video.py at://did:plc:evocjxmi5cps2thb4ya5jcji/app.bsky.feed.post/3ll4mccmmod2y --output-dir ./videos
"""
import os
import sys
import logging
import time
import json
import requests
import argparse
import subprocess
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv
from atproto import Client

def setup_logging():
    """Set up basic logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)

class BlueskyVideoDownloader:
    """Class to handle downloading videos from Bluesky posts"""
    
    def __init__(self, username: str, password: str, max_retries: int = 3, retry_delay: int = 5):
        self.logger = logging.getLogger(__name__ + ".BlueskyVideoDownloader")
        self.username = username
        self.password = password
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.client = Client()
        self.authenticated = False
        
        # Authenticate when creating the instance
        self._authenticate()
    
    def _authenticate(self) -> bool:
        """Authenticate with the Bluesky API"""
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Attempting to authenticate as {self.username}")
                response = self.client.login(self.username, self.password)
                self.did = response.did
                self.authenticated = True
                self.logger.info(f"Authentication successful for {self.username} (DID: {self.did})")
                return True
            except Exception as e:
                self.logger.error(f"Authentication attempt {attempt+1}/{self.max_retries} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    self.logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
        
        self.logger.error(f"Authentication failed after {self.max_retries} attempts")
        return False

    def get_post(self, post_uri: str) -> Optional[Any]:
        """Fetch a specific post by URI"""
        if not self.authenticated:
            self.logger.error("Cannot fetch post: Not authenticated")
            return None
        
        try:
            self.logger.info(f"Fetching post: {post_uri}")
            
            # Parse URI to get repository and rkey
            # Format is usually at://did:plc:xxx/app.bsky.feed.post/rkey
            parts = post_uri.split('/')
            
            if len(parts) < 4 or not post_uri.startswith("at://"):
                self.logger.error(f"Invalid post URI format: {post_uri}")
                return None
            
            # Use get_post_thread to retrieve the post
            response = self.client.app.bsky.feed.get_post_thread({
                'uri': post_uri
            })
            
            if response and hasattr(response, 'thread') and hasattr(response.thread, 'post'):
                self.logger.info(f"Successfully fetched post")
                return response.thread.post
            else:
                self.logger.warning("Post not found or has unexpected format")
                return None
            
        except Exception as e:
            self.logger.error(f"Failed to fetch post: {str(e)}")
            return None
    
    def deep_get(self, obj: Any, path: list, default=None):
        """Safely get a value from a nested object structure using a path list."""
        current = obj
        for key in path:
            if hasattr(current, key):
                current = getattr(current, key)
            elif isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, (list, tuple)) and isinstance(key, int) and len(current) > key:
                current = current[key]
            else:
                return default
        return current

    def extract_video_url(self, post: Any) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract video URL from a post object
        
        Returns:
            Tuple containing (direct_url, playlist_url)
            - direct_url: URL for direct mp4 download if available
            - playlist_url: URL for m3u8 playlist if available
        """
        try:
            self.logger.debug("Extracting video URL from post")
            
            # Debug: Print post structure
            self.logger.debug(f"Post structure: {post}")
            
            direct_url = None
            playlist_url = None
            
            # Check for playlist URL in the embed field (common with Bluesky videos)
            if hasattr(post, 'embed') and hasattr(post.embed, 'playlist'):
                playlist_url = post.embed.playlist
                self.logger.info(f"Found video playlist URL: {playlist_url}")
                
                # Try to extract the base URL from the playlist for direct MP4 access
                # (This might not always work as some videos are only available as HLS streams)
                playlist_parts = playlist_url.split('/')
                if len(playlist_parts) >= 2 and playlist_parts[-1] == 'playlist.m3u8':
                    # Remove the playlist.m3u8 part and construct a potential direct URL
                    base_url = '/'.join(playlist_parts[:-1])
                    potential_direct_url = f"{base_url}/video.mp4"
                    self.logger.debug(f"Potential direct MP4 URL: {potential_direct_url}")
            
            # Various paths where direct video URL can be found
            check_paths = [
                ['embed', 'media', 'video', 'url'],
                ['embed', 'media', 'items', 0, 'video', 'url'],
                ['embedView', 'video', 'url'],
                ['record', 'embed', 'media', 'video', 'url'],
                ['record', 'embed', 'media', 'items', 0, 'video', 'url']
            ]
            
            # Try each path to find a direct video URL
            for path in check_paths:
                url = self.deep_get(post, path)
                if url and isinstance(url, str):
                    direct_url = url
                    self.logger.info(f"Found direct video URL at path {path}: {direct_url}")
                    break
            
            # Only log warning if we found neither type of URL
            if not direct_url and not playlist_url:
                self.logger.warning("No video URL found in post")
            
            return direct_url, playlist_url
            
        except Exception as e:
            self.logger.error(f"Error extracting video URL: {str(e)}")
            return None, None

    def download_from_playlist(self, playlist_url: str, output_path: str) -> bool:
        """
        Download video from an HLS playlist URL using ffmpeg
        
        Args:
            playlist_url: URL to the HLS playlist (.m3u8)
            output_path: Path where the video file will be saved
            
        Returns:
            True if download succeeded, False otherwise
        """
        try:
            self.logger.info(f"Downloading video from HLS playlist: {playlist_url}")
            
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Use ffmpeg to download and convert the HLS stream
            cmd = [
                "ffmpeg",
                "-i", playlist_url,
                "-c", "copy",  # Just copy the streams without re-encoding
                "-bsf:a", "aac_adtstoasc",  # Fix for AAC audio
                "-y",  # Overwrite output file if it exists
                output_path
            ]
            
            self.logger.debug(f"Running command: {' '.join(cmd)}")
            
            # Run the command
            process = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            
            self.logger.info(f"Video successfully downloaded to: {output_path}")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error downloading video with ffmpeg: {str(e)}")
            self.logger.error(f"STDOUT: {e.stdout}")
            self.logger.error(f"STDERR: {e.stderr}")
            return False
            
        except Exception as e:
            self.logger.error(f"Unexpected error downloading video: {str(e)}")
            return False

    def download_video(self, url: str, output_dir: str) -> Optional[str]:
        """Download a video from URL to the specified directory"""
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename from URL
            filename = url.split('/')[-1]
            if '?' in filename:
                filename = filename.split('?')[0]
                
            # Add timestamp to ensure unique filenames
            timestamp = int(time.time())
            
            # If it's an m3u8 file, change the extension to mp4
            if filename.endswith('.m3u8'):
                base_name = filename.replace('playlist.m3u8', '')
                filename = f"{timestamp}_{base_name}video.mp4"
            else:
                filename = f"{timestamp}_{filename}"
            
            # Full output path
            output_path = os.path.join(output_dir, filename)
            
            # Check if it's an HLS playlist
            if url.endswith('.m3u8'):
                return output_path if self.download_from_playlist(url, output_path) else None
            
            # Otherwise do a regular HTTP download
            self.logger.info(f"Downloading video from URL: {url}")
            self.logger.info(f"Saving to: {output_path}")
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            self.logger.info(f"Download completed successfully")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error downloading video: {str(e)}")
            return None

    def download_post_video(self, post_uri: str, output_dir: str = "data/videos") -> Optional[str]:
        """Download video from a post URI"""
        post = self.get_post(post_uri)
        if not post:
            return None
            
        direct_url, playlist_url = self.extract_video_url(post)
        
        # Prefer direct URL if available, otherwise use playlist URL
        url_to_use = direct_url if direct_url else playlist_url
        
        if not url_to_use:
            self.logger.error("No video URL found in post")
            return None
            
        return self.download_video(url_to_use, output_dir)

def main():
    """Main function to download a video from a Bluesky post"""
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="Download a video from a Bluesky post",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("post_uri", help="URI of the Bluesky post containing the video")
    parser.add_argument("--output-dir", "-o", default="data/videos", 
                        help="Directory to save the video (default: data/videos)")
    parser.add_argument("--verbose", "-v", action="store_true", 
                        help="Enable verbose logging")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug mode with detailed logging")
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging()
    if args.verbose or args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials from environment
    username = os.environ.get("BSKY_BOT_USERNAME")
    password = os.environ.get("BSKY_BOT_PASSWORD")
    
    if not username or not password:
        logger.error("Missing Bluesky credentials in environment variables")
        logger.error("Please set BSKY_BOT_USERNAME and BSKY_BOT_PASSWORD in .env file")
        sys.exit(1)
    
    # Initialize the video downloader
    downloader = BlueskyVideoDownloader(username, password)
    
    if not downloader.authenticated:
        logger.error("Failed to authenticate with Bluesky")
        sys.exit(1)
    
    logger.info(f"Attempting to download video from post: {args.post_uri}")
    output_path = downloader.download_post_video(args.post_uri, args.output_dir)
    
    if output_path:
        logger.info(f"Video successfully downloaded to: {output_path}")
        print(f"\nDownload successful!\nVideo saved to: {output_path}")
        # Print just the path to allow for easy piping to other scripts
        print(output_path)
    else:
        logger.error(f"Failed to download video from post: {args.post_uri}")
        print(f"\nDownload failed. See logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
