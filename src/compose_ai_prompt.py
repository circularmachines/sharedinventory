#!/usr/bin/env python3
"""
Compose prompts for AI models from various inputs including transcripts, frames, and images.
This script takes text, images, transcriptions, and video frames as input
and outputs a structured list of messages to be sent to an AI.
"""

# 1. IMPORTS
import os
import sys
import json
import base64
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import mimetypes

# 2. SETUP LOGGING FUNCTION
def setup_logging(debug=False) -> logging.Logger:
    """Configure logging with different levels for standalone vs imported use"""
    logger = logging.getLogger(__name__)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    return logger

# 3. HELPER CLASSES/FUNCTIONS
class AIPromptComposer:
    """Class to handle composition of prompts for AI models"""
    
    def __init__(self, system_message: Optional[str] = None):
        self.logger = logging.getLogger(__name__ + ".AIPromptComposer")
        self.messages = []
        
        if system_message:
            self.add_system_message(system_message)
        else:
            default_message = "You are a helpful assistant. Analyze the provided content and respond accordingly."
            self.add_system_message(default_message)
    
    def add_system_message(self, content: str) -> None:
        """Add a system message to the prompt"""
        self.logger.debug(f"Adding system message: {content[:50]}...")
        self.messages.append({
            "role": "system",
            "content": content
        })
    
    def add_user_message(self, content: Union[str, List]) -> None:
        """Add a user message to the prompt"""
        if isinstance(content, str):
            self.logger.debug(f"Adding user text message: {content[:50]}...")
            self.messages.append({
                "role": "user",
                "content": content
            })
        else:
            self.logger.debug(f"Adding user message with {len(content)} content items")
            self.messages.append({
                "role": "user",
                "content": content
            })
    
    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the prompt"""
        self.logger.debug(f"Adding assistant message: {content[:50]}...")
        self.messages.append({
            "role": "assistant",
            "content": content
        })
    
    def encode_image(self, image_path: str) -> Optional[str]:
        """Encode an image file to base64"""
        try:
            self.logger.debug(f"Encoding image: {image_path}")
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                return encoded_string
        except Exception as e:
            self.logger.error(f"Error encoding image {image_path}: {str(e)}")
            return None
    
    def get_mime_type(self, file_path: str) -> str:
        """Get the MIME type for a file"""
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "application/octet-stream"
    
    def add_images_to_message(self, image_paths: List[str], text_content: str = "") -> None:
        """Add multiple images to a message with optional text"""
        content = []
        
        if text_content:
            content.append({
                "type": "text",
                "text": text_content
            })
        
        for img_path in image_paths:
            encoded_image = self.encode_image(img_path)
            if encoded_image:
                mime_type = self.get_mime_type(img_path)
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{encoded_image}"
                    }
                })
        
        if content:
            self.logger.info(f"Adding user message with {len(content)} content items")
            self.messages.append({
                "role": "user",
                "content": content
            })
        else:
            self.logger.warning("No content was added to the message")
    
    def add_transcript(self, transcript_path: str) -> Optional[Dict[str, Any]]:
        """Add transcript data to the prompt and return the parsed transcript"""
        try:
            self.logger.info(f"Loading transcript from {transcript_path}")
            with open(transcript_path, 'r') as f:
                transcript_data = json.load(f)
            return transcript_data
            
        except Exception as e:
            self.logger.error(f"Error loading transcript: {str(e)}")
            return None
    
    def add_frames_from_transcript(self, transcript_data: Dict[str, Any], 
                                 frame_dir: str, max_frames: int = 5) -> None:
        """Add key frames from transcript using frames stored in frame_dir"""
        try:
            if not transcript_data or "segments" not in transcript_data:
                self.logger.warning("No segments found in transcript data")
                return
            
            frame_path = Path(frame_dir)
            if not frame_path.exists() or not frame_path.is_dir():
                self.logger.error(f"Frame directory does not exist: {frame_dir}")
                return
            
            # Process segments with frames
            for segment in transcript_data["segments"]:
                if "frames" in segment and segment["frames"]:
                    segment_frames = []
                    for frame_info in segment["frames"][:max_frames]:
                        frame_path = frame_info["path"]
                        if Path(frame_path).exists():
                            segment_frames.append(frame_path)
                    
                    if segment_frames:
                        segment_text = segment.get("text", "").strip()
                        self.add_images_to_message(
                            segment_frames,
                            segment_text#f"Key frames from video ({len(segment_frames)} of {len(segment_frames)} total frames):\n{segment_text}"
                        )
            
        except Exception as e:
            self.logger.error(f"Error adding frames from transcript: {str(e)})")
    
    def get_messages(self) -> List[Dict[str, Any]]:
        """Get the complete list of messages"""
        return self.messages

def load_system_message_from_file(file_path: str) -> Optional[str]:
    """Load system message from a file"""
    logger = logging.getLogger(__name__)
    try:
        logger.info(f"Loading system message from file: {file_path}")
        with open(file_path, 'r') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Error loading system message file: {str(e)}")
        return None

# 4. PRIMARY INTERFACE FUNCTION
def compose_prompt(
    transcript_path: Optional[str] = None,
    frame_dir: Optional[str] = None,
    system_message_path: Optional[str] = None,
    text_content: Optional[str] = None,
    image_paths: Optional[List[str]] = None,
    debug: bool = False
) -> Optional[List[Dict[str, Any]]]:
    """
    Compose an AI prompt from various inputs including transcripts, frames, and images.
    
    Args:
        transcript_path: Path to the transcript JSON file
        frame_dir: Directory containing video frames
        system_message_path: Path to system message file
        text_content: Additional text to include in the prompt
        image_paths: List of paths to additional images
        debug: Enable debug logging
    
    Returns:
        List of messages formatted for AI consumption or None if failed
    """
    logger = setup_logging(debug=debug)
    logger.info("Starting prompt composition")
    
    try:
        # Load system message
        system_message = None
        if system_message_path:
            system_message = load_system_message_from_file(system_message_path)
        
        # Initialize composer
        composer = AIPromptComposer(system_message)
        
        # Add text content if provided
        if text_content:
            composer.add_user_message(text_content)
        
        # Process transcript and frames
        if transcript_path:
            transcript_data = composer.add_transcript(transcript_path)
            if transcript_data and frame_dir:
                composer.add_frames_from_transcript(transcript_data, frame_dir)
        
        # Add individual images
        if image_paths:
            composer.add_images_to_message(image_paths, "Additional images for analysis:")
        
        return composer.get_messages()
        
    except Exception as e:
        logger.error(f"Failed to compose prompt: {str(e)}")
        return None

# 5. MAIN FUNCTION
def main():
    """Main function with hardcoded example"""
    # Set up logging
    logger = setup_logging(debug=True)

    # Hardcoded example inputs
    system_message_path = "src/system_message.md"
    transcript_path = "data/processed_videos/transcripts/1744099622_video_transcript.json"
    frame_dir = "data/processed_videos/frames/1743888817_video"

    # Process the inputs
    messages = compose_prompt(
        system_message_path=system_message_path,
        transcript_path=transcript_path,
        frame_dir=frame_dir,
        debug=True
    )

    if messages:
        # Save output to file
        output_file = "data/processed_videos/prompt.json"
        with open(output_file, 'w') as f:
            json.dump(messages, f, indent=2)
        print(f"\nPrompt messages saved successfully to: {output_file}")
        print(output_file)  # Clean output for piping
        return 0
    else:
        print("\nFailed to generate prompt messages")
        return 1

# 6. SCRIPT EXECUTION CHECK
if __name__ == "__main__":
    sys.exit(main())