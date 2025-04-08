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
                
            # Add the full transcript text as a user message
            if "text" in transcript_data:
                self.add_user_message(f"Video transcript: {transcript_data['text']}")
            
            # Add individual segments with frames as separate messages
            if "segments" in transcript_data:
                for segment in transcript_data["segments"]:
                    if "text" in segment:
                        segment_text = segment["text"].strip()
                        if not segment_text:
                            continue
                            
                        # If segment has frames, add them with the text
                        if "frames" in segment and segment["frames"]:
                            frame_paths = [frame["path"] for frame in segment["frames"] if frame.get("path")]
                            if frame_paths:
                                timestamp = f"[{segment['start']:.1f}s - {segment['end']:.1f}s]"
                                self.add_images_to_message(
                                    frame_paths,
                                    f"Segment {timestamp}: {segment_text}"
                                )
                        else:
                            # If no frames, just add the text
                            timestamp = f"[{segment['start']:.1f}s - {segment['end']:.1f}s]"
                            self.add_user_message(f"Segment {timestamp}: {segment_text}")
            
            return transcript_data
                
        except Exception as e:
            self.logger.error(f"Error loading transcript: {str(e)}")
            return None
    
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
    system_message_path: Optional[str] = None,
    text_content: Optional[str] = None,
    image_paths: Optional[List[str]] = None,
    debug: bool = False
) -> Optional[List[Dict[str, Any]]]:
    """
    Compose an AI prompt from various inputs including transcripts and images.
    
    Args:
        transcript_path: Path to the transcript JSON file
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
        
        # Process transcript
        if transcript_path and os.path.exists(transcript_path):
            composer.add_transcript(transcript_path)
        
        # Add individual images
        if image_paths:
            for path in image_paths:
                if os.path.exists(path):
                    composer.add_images_to_message([path])
        
        messages = composer.get_messages()
        if not messages:
            logger.warning("No messages were generated")
            return None
            
        return messages
        
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
    transcript_path = "examples/1744119329_video_transcript.json"

    # Process the inputs
    messages = compose_prompt(
        system_message_path=system_message_path,
        transcript_path=transcript_path,
        debug=True
    )

    if messages:
        # Save output to file
        output_file = "data/prompt.json"
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