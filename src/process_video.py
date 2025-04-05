#!/usr/bin/env python3
"""
Standalone script to process downloaded videos from Bluesky posts.
This script handles audio extraction, transcription, and frame extraction from videos.

Usage:
  python process_video.py <video_path> [--no-audio] [--no-frames] [--no-transcribe] [--output-dir DIRECTORY]

Examples:
  python process_video.py data/videos/video.mp4
  python process_video.py data/videos/video.mp4 --no-transcribe
  python process_video.py data/videos/video.mp4 --output-dir ./processed
"""
import os
import sys
import json
import logging
import tempfile
import subprocess
import argparse
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv
import cv2
from openai import AzureOpenAI

def setup_logging():
    """Set up basic logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)

class VideoProcessor:
    """Class to handle video processing tasks"""
    
    def __init__(self, 
                 openai_api_key: Optional[str] = None, 
                 azure_endpoint: Optional[str] = None,
                 api_version: Optional[str] = None,
                 output_dir: str = "data/processed_videos"):
        self.logger = logging.getLogger(__name__ + ".VideoProcessor")
        self.openai_api_key = openai_api_key
        self.azure_endpoint = azure_endpoint
        self.api_version = api_version
        self.output_dir = output_dir
        
        # Check if Azure OpenAI credentials are provided
        self.azure_client = None
        if openai_api_key and azure_endpoint and api_version:
            self.logger.info("Azure OpenAI API credentials configured")
            self.azure_client = AzureOpenAI(
                api_key=openai_api_key,
                azure_endpoint=azure_endpoint,
                api_version=api_version
            )
        else:
            self.logger.warning("Azure OpenAI API credentials not provided, transcription will not work")

    def extract_audio(self, video_path: str) -> Optional[str]:
        """Extract audio from a video file"""
        try:
            self.logger.info(f"Extracting audio from: {video_path}")
            
            # Create output directory
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_dir = os.path.join(self.output_dir, "audio")
            os.makedirs(output_dir, exist_ok=True)
            
            # Output path for the audio file
            output_path = os.path.join(output_dir, f"{base_name}.mp3")
            
            # Run ffmpeg to extract audio
            self.logger.debug(f"Running ffmpeg to extract audio to {output_path}")
            cmd = [
                "ffmpeg", "-i", video_path,
                "-q:a", "0", "-map", "a", "-y",
                output_path
            ]
            
            # Execute the command
            process = subprocess.run(
                cmd, 
                check=True, 
                capture_output=True,
                text=True
            )
            
            self.logger.info(f"Audio extraction completed successfully: {output_path}")
            return output_path
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error extracting audio with ffmpeg: {str(e)}")
            self.logger.error(f"STDOUT: {e.stdout}")
            self.logger.error(f"STDERR: {e.stderr}")
            return None
            
        except Exception as e:
            self.logger.error(f"Unexpected error extracting audio: {str(e)}")
            return None

    def transcribe_audio(self, audio_path: str, language: str = "en") -> Optional[Dict[str, Any]]:
        """Transcribe audio using Azure OpenAI Whisper API"""
        try:
            if not self.azure_client:
                self.logger.error("Cannot transcribe without Azure OpenAI client")
                return None
                
            self.logger.info(f"Transcribing audio: {audio_path} (language: {language})")
            
            # Extract video_id from audio path
            video_id = os.path.splitext(os.path.basename(audio_path))[0]
            
            # Ensure the audio file exists
            if not os.path.exists(audio_path):
                self.logger.error(f"Audio file not found: {audio_path}")
                return None
                
            # Create output directory for transcripts
            output_dir = os.path.join(self.output_dir, "transcripts")
            os.makedirs(output_dir, exist_ok=True)
            
            # Path for saving transcript
            transcript_path = os.path.join(output_dir, f"{video_id}_transcript.json")
            
            # Check if transcription already exists
            if os.path.exists(transcript_path):
                self.logger.info(f"Transcription already exists at {transcript_path}")
                with open(transcript_path, 'r') as f:
                    return json.load(f)
            
            # Transcribe using Azure OpenAI's API
            with open(audio_path, "rb") as audio_file:
                self.logger.info(f"Sending audio to Azure OpenAI Whisper API")
                response = self.azure_client.audio.transcriptions.create(
                    model="whisper",  # Uses deployment name from Azure
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=['word', 'segment']
                )
            
            # Extract word-level data
            words_data = []
            if hasattr(response, 'words'):
                for word in response.words:
                    word_data = {
                        'text': word.word,
                        'start': word.start,
                        'end': word.end,
                        'duration': round(word.end - word.start, 3)
                    }
                    words_data.append(word_data)
            
            # Extract segment-level data
            segments_data = []
            if hasattr(response, 'segments'):
                for segment in response.segments:
                    segment_data = {
                        'text': segment.text,
                        'start': segment.start,
                        'end': segment.end,
                        'duration': round(segment.end - segment.start, 3)
                    }
                    segments_data.append(segment_data)
            
            # Format transcript data
            transcript_data = {
                'metadata': {
                    'video_id': video_id,
                    'filename': os.path.basename(audio_path),
                    'filepath': os.path.abspath(audio_path),
                    'language': language,
                    'duration': round(response.duration if hasattr(response, 'duration') else 0, 2)
                },
                'text': response.text,
                'segments': segments_data,
                'words': words_data,
                'transcript_path': transcript_path
            }
            
            # Save transcript to file
            with open(transcript_path, 'w') as f:
                json.dump(transcript_data, f, indent=2)
                
            self.logger.info(f"Transcription completed and saved to: {transcript_path}")
            return transcript_data
            
        except Exception as e:
            self.logger.error(f"Error transcribing audio: {str(e)}")
            return None

    def extract_frames(self, video_path: str, transcript: Optional[Dict[str, Any]] = None) -> List[str]:
        """Extract key frames from video"""
        try:
            self.logger.info(f"Extracting frames from video: {video_path}")
            
            # Create output directory for frames
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            frames_dir = os.path.join(self.output_dir, "frames", base_name)
            os.makedirs(frames_dir, exist_ok=True)
            
            # Open the video file
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.logger.error(f"Could not open video: {video_path}")
                return []
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            self.logger.info(f"Video properties: {frame_count} frames, {fps} fps, {duration:.2f}s duration")
            
            frame_paths = []
            
            # If we have a transcript with segments, use those timestamps for keyframes
            if transcript and "segments" in transcript and transcript["segments"]:
                self.logger.info(f"Extracting frames based on {len(transcript['segments'])} transcript segments")
                
                for i, segment in enumerate(transcript["segments"]):
                    if "start" in segment:
                        time_sec = segment["start"]
                        
                        # Set position in video
                        cap.set(cv2.CAP_PROP_POS_MSEC, time_sec * 1000)
                        
                        # Read the frame
                        success, frame = cap.read()
                        
                        if success:
                            # Save the frame
                            frame_path = os.path.join(frames_dir, f"frame_{i:03d}_{time_sec:.2f}s.jpg")
                            cv2.imwrite(frame_path, frame)
                            frame_paths.append(frame_path)
                            self.logger.debug(f"Saved frame at {time_sec:.2f}s to {frame_path}")
            else:
                # No transcript segments, extract frames at regular intervals (10 seconds)
                interval = 10  # seconds
                self.logger.info(f"No transcript segments, extracting frames every {interval} seconds")
                
                for time_sec in range(0, int(duration), interval):
                    # Set position in video
                    cap.set(cv2.CAP_PROP_POS_MSEC, time_sec * 1000)
                    
                    # Read the frame
                    success, frame = cap.read()
                    
                    if success:
                        # Save the frame
                        frame_path = os.path.join(frames_dir, f"frame_{time_sec//interval:03d}_{time_sec}s.jpg")
                        cv2.imwrite(frame_path, frame)
                        frame_paths.append(frame_path)
                        self.logger.debug(f"Saved frame at {time_sec}s to {frame_path}")
            
            # Release the video capture
            cap.release()
            
            self.logger.info(f"Extracted {len(frame_paths)} frames from video")
            return frame_paths
            
        except Exception as e:
            self.logger.error(f"Error extracting frames: {str(e)}")
            return []

    def process_video(self, video_path: str, extract_audio: bool = True, 
                     transcribe: bool = True, extract_frames: bool = True,
                     language: str = "en") -> Dict[str, Any]:
        """Process a video file with options for each step"""
        result = {
            "video_path": video_path,
            "audio_path": None,
            "transcript_path": None,
            "frame_paths": []
        }
        
        try:
            self.logger.info(f"Starting processing of video: {video_path}")
            
            # 1. Extract audio if requested
            audio_path = None
            if extract_audio:
                audio_path = self.extract_audio(video_path)
                result["audio_path"] = audio_path
            else:
                self.logger.info("Audio extraction skipped")
            
            # 2. Transcribe audio if requested and available
            transcript = None
            if transcribe and audio_path:
                if self.azure_client:
                    transcript = self.transcribe_audio(audio_path, language)
                    if transcript:
                        result["transcript_path"] = transcript.get("transcript_path")
                    else:
                        self.logger.warning("Transcription failed")
                else:
                    self.logger.warning("Cannot transcribe - Azure OpenAI client not configured")
            elif not audio_path and transcribe:
                self.logger.warning("Cannot transcribe - no audio extracted")
            else:
                self.logger.info("Transcription skipped")
            
            # 3. Extract frames if requested
            if extract_frames:
                frame_paths = self.extract_frames(video_path, transcript)
                result["frame_paths"] = frame_paths
            else:
                self.logger.info("Frame extraction skipped")
            
            self.logger.info(f"Video processing completed for: {video_path}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing video: {str(e)}")
            return result

def main():
    """Main function to process a video file"""
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="Process a video file: extract audio, transcribe, and extract frames",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("video_path", help="Path to the video file to process")
    parser.add_argument("--no-audio", action="store_true", 
                        help="Skip audio extraction")
    parser.add_argument("--no-transcribe", action="store_true", 
                        help="Skip transcription")
    parser.add_argument("--no-frames", action="store_true", 
                        help="Skip frame extraction")
    parser.add_argument("--output-dir", default="data/processed_videos", 
                        help="Base directory for output files (default: data/processed_videos)")
    parser.add_argument("--language", default="en",
                        help="Language code for transcription (default: en)")
    parser.add_argument("--verbose", "-v", action="store_true", 
                        help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load environment variables
    load_dotenv()
    
    # Check if video file exists
    if not os.path.exists(args.video_path):
        logger.error(f"Video file not found: {args.video_path}")
        print(f"Error: Video file not found at {args.video_path}")
        sys.exit(1)
    
    # Get Azure OpenAI credentials from environment
    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    whisper_api_key = os.environ.get("WHISPER_API_KEY")
    whisper_api_version = os.environ.get("WHISPER_API_VERSION")
    
    if not all([azure_endpoint, whisper_api_key, whisper_api_version]) and not args.no_transcribe:
        logger.warning("Azure OpenAI credentials not found in environment, transcription will be skipped")
    
    # Initialize video processor
    processor = VideoProcessor(
        openai_api_key=whisper_api_key,
        azure_endpoint=azure_endpoint,
        api_version=whisper_api_version,
        output_dir=args.output_dir
    )
    
    # Process the video with provided options
    logger.info(f"Starting video processing for: {args.video_path}")
    result = processor.process_video(
        args.video_path, 
        extract_audio=not args.no_audio,
        transcribe=not args.no_transcribe,
        extract_frames=not args.no_frames,
        language=args.language
    )
    
    # Print results
    print("\nVideo Processing Results:")
    print(f"Input video: {args.video_path}")
    
    if not args.no_audio:
        print(f"Audio extracted to: {result['audio_path'] or 'Failed'}")
    else:
        print("Audio extraction: Skipped")
    
    if not args.no_transcribe:
        print(f"Transcript saved to: {result['transcript_path'] or 'Not available'}")
    else:
        print("Transcription: Skipped")
    
    if not args.no_frames:
        print(f"Extracted {len(result['frame_paths'])} frames")
        if result['frame_paths']:
            print(f"Sample frames:")
            for i, frame_path in enumerate(result['frame_paths'][:3]):
                print(f"  - {frame_path}")
            
            if len(result['frame_paths']) > 3:
                print(f"  - ... ({len(result['frame_paths']) - 3} more frames)")
    else:
        print("Frame extraction: Skipped")
    
    # Return JSON output for easier processing by other scripts
    output = {
        "video_path": args.video_path,
        "audio_path": result["audio_path"],
        "transcript_path": result["transcript_path"],
        "frame_paths": result["frame_paths"]
    }
    
    # Print just the output paths in JSON format for piping to other scripts
    print("\nJSON output:")
    print(json.dumps(output))

if __name__ == "__main__":
    main()
