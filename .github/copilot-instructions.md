never do chmod. run files with python xxx.py ...

add dependencies to requirements.txt then do pip install -r requirements.txt

generally use latest possible version of dependencies

keep main.py simple, it should just be a monitor


## Function file format (src/*.py)

all functions should be in folder scr

every file in src should be optimized for debugging. when running the script in src it should output alot of information to help us solve the task of that specific script. When a function is called from external the debug output should be kept to a minimum. Keep the files as short as possible, exclude any functions that is handled by another script. 


1. IMPORTS:
   - Import necessary libraries (os, requests, logging, etc.)

2. SETUP LOGGING FUNCTION:
   - Configure logging with different levels for standalone vs imported use

3. HELPER CLASSES/FUNCTIONS:
   - Implement VideoDownloader class with methods for different download types
   - Handle edge cases and error conditions

4. PRIMARY INTERFACE FUNCTION:
   - Define download_video(url, debug=False) -> Optional[str]
   - This is the main function that external code will call
   - Should be well-documented with clear docstring
   - Return value should be the path to downloaded video or None if failed

5. MAIN FUNCTION:
   - Keep minimal with hardcoded examples for testing
   - Include debug=True for verbose output when run directly
   - Print clear output suitable for command-line use
   - Never use args
   - Example format:
     ```
     def main():
         """Main function with hardcoded example"""
         video_url = "https://example.com/video.m3u8"
         output_path = download_video(video_url, debug=True)
         
         if output_path:
             print(f"\nVideo downloaded successfully to: {output_path}")
             print(output_path)  # Clean output for piping
         else:
             print("\nFailed to download video")
     ```

6. SCRIPT EXECUTION CHECK:
   - Add standard Python idiom to check if file is being run directly
   - ```
     if __name__ == "__main__":
         main()
     ```




use public bsky endpoint when possible: https://public.api.bsky.app


files in src:

get_mentions.py
- input:  BSKY_BOT_USERNAME and BSKY_BOT_PASSWORD from .env
- output: list of URI for posts that mentions bot

get_post_thread.py:
- input: post URI
- output: complete thread of post URI with how they relate. include users

filter_mentions.py 
- input: 
- output: list of unprocessed posts

check_media.py: 
- input: post URI
- output: media type

download_video.py
- input: video URI
- output: path of saved video

process_video.py:
- input: video path
- output: frame paths, and transcription path

compose_ai_prompt.py:
- input: text, images, transcriptions, video frames
- output: list of messages to be sent to AI

ai_api_call.py:
- input: list of messages
- output: structured ai output

post_bsky_reply.py:
- input: Post URI + string below 300 characters. 
- output: N/A

add_to_database.py
#TBD
 
process.py #runs all functions above

- input: call from main.py
- output: N/A
