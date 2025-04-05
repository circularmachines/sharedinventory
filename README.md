# SharedInventory Bot for Bluesky

A bot for Bluesky that adds members' posts to a shared inventory database and processes videos for content analysis.

## Overview

The SharedInventory bot monitors mentions, processes the content of posts (including videos), and adds items to a shared inventory. Members can browse this inventory through a web interface (coming in a later phase).

## Features

### Phase 1 - MVP
- **Mention Monitoring**: Bot listens for mentions and responds accordingly
- **Membership Verification**: Checks if users are members before processing their posts
- **Automated Responses**: Provides information on how to join for non-members
- **Basic Member Management**: Stores member information in a database

### Phase 2 - Content Analysis (Current)
- **Video Processing Pipeline**: 
  - Download videos from Bluesky posts
  - Extract audio from videos
  - Transcribe audio using AI (Whisper)
  - Extract key frames based on transcript segments
- **Content Analysis**: Process text, images, and videos from posts

### Phase 3 - Coming Soon
- **Web Interface**: Browse the inventory and analytics
- **Advanced Analytics**: Insights from processed content

## Setup

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Create a copy of the environment variables file:
   ```
   cp .env.example .env
   ```
5. Edit `.env` with your Bluesky bot credentials, MongoDB connection string, and OpenAI API credentials
6. Start the bot:
   ```
   python main.py
   ```

## Usage

### Becoming a Member

To become a member:
1. Send a direct message to the bot with the text "join SharedInventory"
2. The bot will verify and add you as a member

### Adding Items to the Inventory

Once you're a member:
1. Simply mention the bot in a post describing the item
2. The bot will analyze your post and add the item to the shared inventory
3. If your post contains videos, the bot will automatically process them for content analysis

### Video Processing Tools

The bot includes several command-line tools for video processing:

1. **Download videos from Bluesky**:
   ```
   python src/bin/download_videos.py --user username.bsky.social --limit 5
   ```

2. **Process downloaded videos**:
   ```
   python src/bin/process_videos.py videos/*.mp4
   ```

3. **Extract audio only**:
   ```
   python src/bin/process_videos.py --audio-only videos/*.mp4
   ```

4. **Extract audio and transcribe (no frames)**:
   ```
   python src/bin/process_videos.py --no-frames videos/*.mp4
   ```

5. **Find videos in Bluesky feeds**:
   ```
   python src/bin/find_videos.py --feed popular --limit 50 --output videos.json
   ```

## Project Structure

- `main.py`: Entry point for the bot application
- `src/`: Source code directory
  - `api/`: API integrations (Bluesky)
  - `bin/`: Command-line executable tools
  - `bot_handler.py`: Core bot logic
  - `cli/`: Command-line interface modules
  - `db/`: Database handlers
  - `models/`: Data models
  - `utils/`: Utility functions and configuration
  - `video_utils/`: Video processing utilities
    - `downloader.py`: Functions for downloading videos from Bluesky
    - `processor.py`: Functions for processing videos (extract audio, transcribe, extract frames)
- `tests/`: Unit and integration tests (not included in this repository yet)
- `processed_videos/`: Output directory for processed videos
  - `audio/`: Extracted audio files
  - `transcripts/`: Transcription JSON files
  - `frames/`: Extracted video frames

## Environment Variables

- `BLUESKY_USERNAME`: Bluesky bot username
- `BLUESKY_PASSWORD`: Bluesky bot password
- `MONGODB_URI`: MongoDB connection string
- `OPENAI_API_KEY`: OpenAI API key for transcription (standard OpenAI)
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint (alternative to standard OpenAI)
- `WHISPER_API_KEY`: Azure OpenAI API key
- `WHISPER_API_VERSION`: Azure OpenAI API version (default: "2023-09-01-preview")

## License

This work is licensed under the **Creative Commons Attribution-NonCommercial 4.0 International License**

This means you are free to:
- Share — copy and redistribute the material in any medium or format
- Adapt — remix, transform, and build upon the material

Under the following terms:
- Attribution — You must give appropriate credit, provide a link to the license, and indicate if changes were made.
- NonCommercial — You may not use the material for commercial purposes.

For the full license text, visit: https://creativecommons.org/licenses/by-nc/4.0/legalcode