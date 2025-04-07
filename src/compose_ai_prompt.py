#!/usr/bin/env python3
"""
Standalone script to compose prompts for AI models.
This script takes text, images, transcriptions, and video frames as input
and outputs a structured list of messages to be sent to an AI.

Usage:
  python compose_ai_prompt.py [options]

Examples:
  python compose_ai_prompt.py --text "Analyze this video" --transcript-path path/to/transcript.json --image-paths path1.jpg path2.jpg
  python compose_ai_prompt.py --post-uri at://did:plc:xxx/app.bsky.feed.post/rkey --frame-dir path/to/frames
"""

import os
import sys
import json
import base64
import logging
import argparse
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import mimetypes
from dotenv import load_dotenv

def setup_logging(debug=False):
    """Set up basic logging configuration"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)

class AIPromptComposer:
    """Class to handle composition of prompts for AI models"""
    
    def __init__(self, system_message: Optional[str] = None):
        self.logger = logging.getLogger(__name__ + ".AIPromptComposer")
        self.messages = []
        
        # Add system message if provided
        if system_message:
            self.add_system_message(system_message)
        else:
            # Default system message
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
        
        # Add text if provided
        if text_content:
            content.append({
                "type": "text",
                "text": text_content
            })
        
        # Add each image
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
        
        # Add the message if we have content
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
            
            # Extract transcript text
            if "text" in transcript_data:
                transcript_text = f"Transcript:\n{transcript_data['text']}"
                self.add_user_message(transcript_text)
            
            # Return the full transcript data for further processing
            return transcript_data
            
        except Exception as e:
            self.logger.error(f"Error loading transcript: {str(e)}")
            return None
    
    def add_frame_with_segment(self, segment_frames: List[Dict[str, Any]], segment_text: str) -> None:
        """Add frames with their corresponding segment text"""
        frame_paths = [frame['path'] for frame in segment_frames]
        
        if frame_paths:
            # Gather the frames
            content = []
            content.append({
                "type": "text",
                "text": f"Segment: {segment_text}"
            })
            
            for frame_path in frame_paths:
                encoded_image = self.encode_image(frame_path)
                if encoded_image:
                    mime_type = self.get_mime_type(frame_path)
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{encoded_image}"
                        }
                    })
            
            # Add the message with text and images
            if len(content) > 1:  # Make sure we have at least one image
                self.messages.append({
                    "role": "user",
                    "content": content
                })
                self.logger.info(f"Added segment with {len(frame_paths)} frames")
    
    def add_frames_from_transcript_segments(self, transcript_data: Dict[str, Any], max_segments: int = 10) -> None:
        """Add frames from transcript segments where frames are embedded in the segments"""
        try:
            if not transcript_data or "segments" not in transcript_data:
                self.logger.warning("No segments found in transcript data")
                return
            
            segments_with_frames = []
            
            # Find segments that have frames
            for i, segment in enumerate(transcript_data["segments"]):
                if "frames" in segment and segment["frames"]:
                    segments_with_frames.append({
                        "index": i,
                        "text": segment["text"],
                        "frames": segment["frames"]
                    })
            
            if not segments_with_frames:
                self.logger.warning("No segments with frames found in transcript")
                return
                
            self.logger.info(f"Found {len(segments_with_frames)} segments with frames")
            
            # Limit the number of segments to include
            selected_segments = segments_with_frames
            if len(segments_with_frames) > max_segments:
                # Select segments evenly distributed
                step = len(segments_with_frames) // max_segments
                selected_segments = []
                
                for i in range(0, len(segments_with_frames), step):
                    if len(selected_segments) < max_segments:
                        selected_segments.append(segments_with_frames[i])
            
            # Add each segment with its frames
            for segment_info in selected_segments:
                self.add_frame_with_segment(
                    segment_info["frames"],
                    segment_info["text"]
                )
                
        except Exception as e:
            self.logger.error(f"Error adding frames from transcript segments: {str(e)}")
    
    def add_frames_from_transcript(self, 
                                  transcript_data: Dict[str, Any], 
                                  frame_dir: str,
                                  max_frames: int = 5) -> None:
        """Add key frames from a transcript using frames stored in frame_dir"""
        try:
            # First check if frames are embedded in segments
            if transcript_data and "segments" in transcript_data:
                for segment in transcript_data["segments"]:
                    if "frames" in segment and segment["frames"]:
                        self.logger.info("Detected frames embedded in transcript segments")
                        self.add_frames_from_transcript_segments(transcript_data)
                        return
            
            # If no frames embedded, use traditional method with frame_dir
            if not transcript_data or "segments" not in transcript_data:
                self.logger.warning("No segments found in transcript data")
                return
            
            frame_path = Path(frame_dir)
            if not frame_path.exists() or not frame_path.is_dir():
                self.logger.error(f"Frame directory does not exist: {frame_dir}")
                return
            
            # Get list of available frames
            available_frames = list(frame_path.glob("frame_*.jpg"))
            if not available_frames:
                self.logger.warning(f"No frames found in directory: {frame_dir}")
                return
                
            self.logger.info(f"Found {len(available_frames)} frames in directory")
            
            # Select frames to include - either at key points or evenly distributed
            selected_frames = []
            
            if len(available_frames) <= max_frames:
                # Use all frames if we have fewer than max_frames
                selected_frames = available_frames
            else:
                # Distribute frames evenly
                step = len(available_frames) // max_frames
                for i in range(0, len(available_frames), step):
                    if len(selected_frames) < max_frames:
                        selected_frames.append(available_frames[i])
            
            # Add frames to the message
            if selected_frames:
                frame_paths = [str(frame) for frame in selected_frames]
                self.add_images_to_message(
                    frame_paths, 
                    f"Key frames from video ({len(frame_paths)} of {len(available_frames)} total frames):"
                )
            
        except Exception as e:
            self.logger.error(f"Error adding frames from transcript: {str(e)}")
    
    def get_messages(self) -> List[Dict[str, Any]]:
        """Get the complete list of messages"""
        return self.messages


def process_inputs(args):
    """Process command line arguments and compose AI prompt"""
    logger = logging.getLogger(__name__)
    
    # Initialize composer with system message if provided
    composer = AIPromptComposer(args.system_message)
    
    # Add initial text if provided
    if args.text:
        composer.add_user_message(args.text)
    
    # Process transcript if provided
    transcript_data = None
    if args.transcript_path:
        transcript_data = composer.add_transcript(args.transcript_path)
        
        # Add frames directly from transcript segments if available
        if transcript_data:
            # Check if any segments have frames
            has_embedded_frames = False
            if "segments" in transcript_data:
                for segment in transcript_data["segments"]:
                    if "frames" in segment and segment["frames"]:
                        has_embedded_frames = True
                        break
            
            if has_embedded_frames:
                logger.info("Using frames embedded in transcript segments")
                composer.add_frames_from_transcript_segments(transcript_data)
            elif args.frame_dir:
                logger.info("Using external frame directory")
                composer.add_frames_from_transcript(transcript_data, args.frame_dir, args.max_frames)
    
    # Add individual images if provided
    if args.image_paths:
        composer.add_images_to_message(args.image_paths, "Images for analysis:")
    
    # Add frames from directory if provided (only if not already added from transcript)
    if args.frame_dir and (not transcript_data or not any(
            "frames" in segment for segment in transcript_data.get("segments", [])
        )):
        frame_path = Path(args.frame_dir)
        if frame_path.exists() and frame_path.is_dir():
            available_frames = list(frame_path.glob("frame_*.jpg"))
            if available_frames:
                # Select up to max_frames
                selected_frames = available_frames[:args.max_frames]
                frame_paths = [str(frame) for frame in selected_frames]
                composer.add_images_to_message(
                    frame_paths,
                    f"Video frames for analysis ({len(frame_paths)} of {len(available_frames)} total frames):"
                )
    
    # Get the final messages
    messages = composer.get_messages()
    
    # Output messages based on format
    if args.output_format == "json":
        print(json.dumps(messages, indent=2))
    else:
        # Print a human-readable summary
        print("\n=== AI Prompt Messages ===")
        for i, msg in enumerate(messages):
            role = msg["role"]
            content = msg["content"]
            
            print(f"\n--- Message {i+1} ({role}) ---")
            
            if isinstance(content, str):
                print(f"{content[:200]}..." if len(content) > 200 else content)
            else:
                print(f"[Complex message with {len(content)} items]")
                for j, item in enumerate(content):
                    item_type = item.get("type", "unknown")
                    if item_type == "text":
                        text = item.get("text", "")
                        print(f"  Text: {text[:100]}..." if len(text) > 100 else f"  Text: {text}")
                    elif item_type == "image_url":
                        print(f"  Image: [encoded image data]")
    
    return messages


def main():
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Compose prompts for AI models")
    
    # Required arguments
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Text content to include in the prompt")
    group.add_argument("--post-uri", help="URI of a Bluesky post to analyze")
    
    # Optional arguments
    parser.add_argument("--system-message", help="System message to set the context for the AI")
    parser.add_argument("--transcript-path", help="Path to a transcript JSON file")
    parser.add_argument("--image-paths", nargs="+", help="Paths to image files to include")
    parser.add_argument("--frame-dir", help="Directory containing video frames")
    parser.add_argument("--max-frames", type=int, default=5, help="Maximum number of frames to include")
    parser.add_argument("--max-segments", type=int, default=10, help="Maximum number of segments with frames to include")
    parser.add_argument("--output-format", choices=["json", "summary"], default="json", 
                        help="Output format (json or human-readable summary)")
    parser.add_argument("--output-file", help="Path to save the output (default: print to stdout)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging(args.debug)
    
    # Load environment variables
    load_dotenv()
    
    try:
        # Process inputs and compose prompt
        messages = process_inputs(args)
        
        # Save to file if specified
        if args.output_file:
            with open(args.output_file, 'w') as f:
                json.dump(messages, f, indent=2)
            logger.info(f"Saved output to {args.output_file}")
        
        # Return success
        return 0
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())