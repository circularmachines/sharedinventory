#!/usr/bin/env python3
"""
Standalone script to download videos from Bluesky posts.
This script focuses on downloading videos from direct URLs or m3u8 playlist links.
It supports both direct mp4 downloads and HLS streams.
"""

import os
import sys
import logging
import time
import subprocess
import requests
from typing import Optional

def setup_logging(debug=False):
    """Set up basic logging configuration"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)

class VideoDownloader:
    """Simple class to download videos from URLs"""
    
    def __init__(self, output_dir: str = "data/videos"):
        self.logger = logging.getLogger(__name__ + ".VideoDownloader")
        self.output_dir = output_dir
    
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
            if hasattr(e, 'stdout'):
                self.logger.error(f"STDOUT: {e.stdout}")
            if hasattr(e, 'stderr'):
                self.logger.error(f"STDERR: {e.stderr}")
            return False
            
        except Exception as e:
            self.logger.error(f"Unexpected error downloading video: {str(e)}")
            return False
    
    def download(self, url: str, debug: bool = False) -> Optional[str]:
        """
        Download a video from URL
        
        Args:
            url: Direct video URL or m3u8 playlist URL
            debug: Whether to enable debug logging
            
        Returns:
            Path to the downloaded video file or None if download failed
        """
        try:
            # Set debug logging if requested
            if debug:
                logging.getLogger().setLevel(logging.DEBUG)
            
            # Create output directory if it doesn't exist
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Generate filename from URL
            filename = url.split('/')[-1]
            if '?' in filename:
                filename = filename.split('?')[0]
                
            # Add timestamp to ensure unique filenames
            timestamp = int(time.time())
            
            # If it's an m3u8 file, change the extension to mp4
            if filename.endswith('.m3u8') or url.endswith('.m3u8'):
                base_name = filename.replace('playlist.m3u8', '')
                filename = f"{timestamp}_{base_name}video.mp4"
            else:
                filename = f"{timestamp}_{filename}"
                
                # If no extension, add .mp4
                if '.' not in filename:
                    filename += '.mp4'
            
            # Full output path
            output_path = os.path.join(self.output_dir, filename)
            
            # Check if it's an HLS playlist
            if url.endswith('.m3u8'):
                return output_path if self.download_from_playlist(url, output_path) else None
            
            # Otherwise do a regular HTTP download
            self.logger.info(f"Downloading video from URL: {url}")
            self.logger.info(f"Saving to: {output_path}")
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            chunk_size = 8192
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Log progress for large files
                    if total_size > 0 and downloaded % (chunk_size * 100) == 0:
                        percent = (downloaded / total_size) * 100
                        self.logger.debug(f"Download progress: {percent:.1f}%")
                    
            self.logger.info(f"Download completed successfully")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error downloading video: {str(e)}")
            return None

def download_video(url: str, debug: bool = False) -> Optional[str]:
    """Main function to download a video that can be called from external code"""
    downloader = VideoDownloader()
    return downloader.download(url, debug=debug)

def main():
    """Main function with hardcoded example"""
    # Example video URL
    video_url = "https://video.bsky.app/watch/did%3Aplc%3Aevocjxmi5cps2thb4ya5jcji/bafkreieadazv3hijkef4jgwrncfcmfdkciwi6vvjjd4au5avhrcor2dmba/playlist.m3u8"
    # Download the video with debug output
    output_path = download_video(video_url, debug=True)
    
    # Print the result
    if output_path:
        print(f"\nVideo downloaded successfully to: {output_path}")
        # Print just the path to allow for easy piping to other scripts
        print(output_path)
    else:
        print("\nFailed to download video")

if __name__ == "__main__":
    main()
