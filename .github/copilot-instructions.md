never do chmod. run files with python xxx.py ...

add dependencies to requirements.txt then do pip install -r requirements.txt

generally use latest possible version of dependencies

keep main.py as clean as possible

all functions should be in folder scr

every file in src should be optimized for debugging. when running the script in src it should output alot of information to help us solve the task of that specific script. When a function is called from external the debug output should be kept to a minimum. Keep the files as short as possible, exclude any functions that is handled by another script. 

files in src:

get_mentions.py
- input:  BSKY_BOT_USERNAME and BSKY_BOT_PASSWORD from .env
- output: list of URI for posts that mentions bot

unprocessed_mentions.py 
- input: list of URI for posts
- output: list of unprocessed posts

get_post_thread.py:
- input: post URI
- output: complete thread of post URI with how they relate

check_media.py: 
- input: post URI
- output: media type

download_video.py
- input: post URI
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

make_bsky_post.py:
#TBD

add_to_database.py
#TBD


