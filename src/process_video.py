#!/usr/bin/env python3
"""
Standalone script to process downloaded videos from Bluesky posts.
This script handles audio extraction, transcription, and frame extraction from videos.
"""
import os
import sys
import json
import logging
import tempfile
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv
import cv2
from openai import AzureOpenAI

def setup_logging(debug=False):
    """Set up basic logging configuration"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)

class VideoProcessor:
    """Class to handle video processing tasks"""
    
    def __init__(self, output_dir: str = "data/processed_videos"):
        self.logger = logging.getLogger(__name__ + ".VideoProcessor")
        self.output_dir = output_dir
        
        # Load environment variables
        load_dotenv()
        
        # Get Azure OpenAI credentials from environment
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        whisper_api_key = os.environ.get("WHISPER_API_KEY")
        whisper_api_version = os.environ.get("WHISPER_API_VERSION")
        
        # Initialize Azure client if credentials are available
        self.azure_client = None
        if all([azure_endpoint, whisper_api_key, whisper_api_version]):
            self.logger.info("Azure OpenAI API credentials configured")
            self.azure_client = AzureOpenAI(
                api_key=whisper_api_key,
                azure_endpoint=azure_endpoint,
                api_version=whisper_api_version
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
                        'duration': round(segment.end - segment.start, 3),
                        'frames': []  # Will be populated after frame extraction
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

    def extract_frames(self, video_path: str, transcript: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
                return {"frame_paths": [], "segment_frames": []}
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            self.logger.info(f"Video properties: {frame_count} frames, {fps} fps, {duration:.2f}s duration")
            
            frame_paths = []
            segment_frames = []  # Store frame info with segment index and timestamp
            
            # If we have a transcript with segments, use those timestamps for keyframes
            if transcript and "segments" in transcript and transcript["segments"]:
                self.logger.info(f"Extracting frames based on {len(transcript['segments'])} transcript segments")
                
                for i, segment in enumerate(transcript["segments"]):
                    if "start" in segment and "end" in segment:
                        # Calculate middle point of the segment
                        start_time = segment["start"]
                        end_time = segment["end"]
                        middle_time = start_time + (end_time - start_time) / 2
                        
                        self.logger.debug(f"Segment {i}: start={start_time:.2f}s, end={end_time:.2f}s, middle={middle_time:.2f}s")
                        
                        # Set position in video to middle of segment
                        cap.set(cv2.CAP_PROP_POS_MSEC, middle_time * 1000)
                        
                        # Read the frame
                        success, frame = cap.read()
                        
                        if success:
                            # Save the frame
                            frame_path = os.path.join(frames_dir, f"frame_{i:03d}_{middle_time:.2f}s.jpg")
                            cv2.imwrite(frame_path, frame)
                            frame_paths.append(frame_path)
                            
                            # Store the frame with segment info
                            segment_frames.append({
                                "segment_index": i,
                                "time_sec": middle_time,
                                "frame_path": frame_path
                            })
                            
                            self.logger.debug(f"Saved frame at middle of segment ({middle_time:.2f}s) to {frame_path}")
                        else:
                            self.logger.warning(f"Failed to extract frame at {middle_time:.2f}s for segment {i}")
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
                        
                        # Store the frame with time info
                        segment_frames.append({
                            "segment_index": -1,  # No specific segment
                            "time_sec": time_sec,
                            "frame_path": frame_path
                        })
                        
                        self.logger.debug(f"Saved frame at {time_sec}s to {frame_path}")
            
            # Release the video capture
            cap.release()
            
            self.logger.info(f"Extracted {len(frame_paths)} frames from video")
            return {"frame_paths": frame_paths, "segment_frames": segment_frames}
            
        except Exception as e:
            self.logger.error(f"Error extracting frames: {str(e)}")
            return {"frame_paths": [], "segment_frames": []}

    def process_video(self, video_path: str, extract_audio: bool = True, 
                     transcribe: bool = True, extract_frames: bool = True,
                     language: str = "en", debug: bool = False) -> Dict[str, Any]:
        """Process a video file with options for each step"""
        # Set up debug logging if requested
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
        
        result = {
            "video_path": video_path,
            "audio_path": None,
            "transcript_path": None,
            "frame_paths": []
        }
        
        try:
            self.logger.info(f"Starting processing of video: {video_path}")
            
            # Check if video file exists
            if not os.path.exists(video_path):
                self.logger.error(f"Video file not found: {video_path}")
                return result
            
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
            frame_data = {"frame_paths": [], "segment_frames": []}
            if extract_frames:
                frame_data = self.extract_frames(video_path, transcript)
                result["frame_paths"] = frame_data["frame_paths"]
            else:
                self.logger.info("Frame extraction skipped")
            
            # 4. Update transcript with frame information if available
            if transcript and frame_data["segment_frames"] and "segments" in transcript:
                self.logger.info("Integrating frame information into transcript segments")
                
                # Associate frames with segments
                for frame_info in frame_data["segment_frames"]:
                    segment_index = frame_info["segment_index"]
                    
                    # Skip frames not associated with a specific segment
                    if segment_index == -1:
                        continue
                    
                    # Make sure segment index is within range
                    if segment_index < len(transcript["segments"]):
                        # Add frame to segment
                        if "frames" not in transcript["segments"][segment_index]:
                            transcript["segments"][segment_index]["frames"] = []
                            
                        transcript["segments"][segment_index]["frames"].append({
                            "path": frame_info["frame_path"],
                            "time": frame_info["time_sec"]
                        })
                
                # Save the updated transcript
                if transcript.get("transcript_path"):
                    try:
                        with open(transcript["transcript_path"], 'w') as f:
                            json.dump(transcript, f, indent=2)
                        self.logger.info("Updated transcript with frame information")
                    except Exception as e:
                        self.logger.error(f"Error saving updated transcript: {str(e)}")
            
            self.logger.info(f"Video processing completed for: {video_path}")
            
            # Print the output paths for debugging
            if debug:
                print("\nProcessing Results:")
                print(f"Input video: {video_path}")
                print(f"Audio path: {result['audio_path'] or 'Not extracted'}")
                print(f"Transcript path: {result['transcript_path'] or 'Not available'}")
                print(f"Number of frames: {len(result['frame_paths'])}")
                if result['frame_paths']:
                    print("Sample frames:")
                    for path in result['frame_paths'][:3]:
                        print(f"  - {path}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing video: {str(e)}")
            return result

def process_video(video_path: str, debug: bool = False) -> Dict[str, Any]:
    """Main function to process a video that can be called from external code"""
    processor = VideoProcessor()
    return processor.process_video(video_path, debug=debug)

def main():
    """Main function demonstrating video processing"""
    # Example usage with a hardcoded video path
    video_path = "data/videos/1744099622_video.mp4"
    
    # Process the video with all features enabled and debug output
    result = process_video(video_path, debug=True)
    
    # Print JSON output for programmatic use
    print("\nJSON output:")
    print(json.dumps(result))

if __name__ == "__main__":
    main()
