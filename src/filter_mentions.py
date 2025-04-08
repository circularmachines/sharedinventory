#!/usr/bin/env python3
"""
Standalone script to filter unprocessed mentions from a list of post URIs.
This script takes a list of post URIs and returns only those that have not been
processed before based on saved post files and member status.
"""
import os
import sys
import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Set
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Define paths
DATA_DIR = Path(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
PROCESSED_FILE = DATA_DIR / "processed_mentions.json"
POSTS_DIR = DATA_DIR / "posts"
MEMBERS_FILE = DATA_DIR / "members.json"

def setup_data_dir() -> bool:
    """Ensure the data directory exists"""
    try:
        POSTS_DIR.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create data directory: {str(e)}")
        return False

def load_members() -> Dict[str, Any]:
    """Load member information from members.json"""
    members = {}
    try:
        if MEMBERS_FILE.exists():
            with open(MEMBERS_FILE, 'r') as f:
                member_list = json.load(f)
                for member in member_list:
                    # Store by both DID and handle for easy lookup
                    members[member['did']] = member
                    members[member['handle']] = member
            logger.info(f"Loaded {len(member_list)} members")
        return members
    except Exception as e:
        logger.error(f"Error loading members: {str(e)}")
        return {}

def is_member(author: str, members: Dict[str, Any]) -> bool:
    """Check if an author (did or handle) is a member"""
    return author in members

def get_post_info(uri: str) -> Dict[str, Any]:
    """Get post information from saved thread JSON files"""
    try:
        # Extract did and rkey from URI (format: at://did:plc:xxx/app.bsky.feed.post/rkey)
        uri_parts = uri.split('/')
        did = uri_parts[2]
        rkey = uri_parts[-1]
        
        # First try looking in individual post files
        post_file = POSTS_DIR / "posts" / did / f"{rkey}.json"
        if post_file.exists():
            with open(post_file, 'r') as f:
                return {
                    'post': json.load(f),
                    'thread': None  # Thread info not needed for this post
                }
        
        # If not found, look in thread files
        thread_file = POSTS_DIR / "threads" / did / f"{rkey}.json"
        if thread_file.exists():
            with open(thread_file, 'r') as f:
                thread_data = json.load(f)
                return {
                    'post': thread_data['thread']['main_post'],
                    'thread': thread_data['thread']
                }
                
        # Look through all thread files as a last resort
        for author_dir in (POSTS_DIR / "threads").glob('*'):
            if not author_dir.is_dir():
                continue
                
            for file_path in author_dir.glob('*.json'):
                with open(file_path, 'r') as f:
                    thread_data = json.load(f)
                    thread = thread_data['thread']
                    
                    # Check main post
                    if thread['main_post'] and thread['main_post']['uri'].endswith(rkey):
                        return {
                            'post': thread['main_post'],
                            'thread': thread
                        }
                        
                    # Check parent posts
                    for post in thread['parent_posts']:
                        if post['uri'].endswith(rkey):
                            return {
                                'post': post,
                                'thread': thread
                            }
                            
                    # Check reply posts
                    for post in thread['reply_posts']:
                        if post['uri'].endswith(rkey):
                            return {
                                'post': post,
                                'thread': thread
                            }
                            
        logger.warning(f"No thread found containing post: {uri}")
        return None
        
    except Exception as e:
        logger.error(f"Error reading thread files: {str(e)}")
        return None

def get_root_post(thread: Dict[str, Any]) -> Dict[str, Any]:
    """Get the root post from a thread structure"""
    if thread['parent_posts']:
        return thread['parent_posts'][0]  # First parent is the root
    return thread['main_post']  # If no parents, main post is root

def mark_post_processed(uri: str) -> bool:
    """Mark a post as processed in the tracking file"""
    try:
        processed = set()
        if PROCESSED_FILE.exists():
            with open(PROCESSED_FILE, 'r') as f:
                processed = set(json.load(f))
        
        processed.add(uri)
        
        with open(PROCESSED_FILE, 'w') as f:
            json.dump(list(processed), f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error marking post as processed: {str(e)}")
        return False

def filter_unprocessed_mentions(mention_uris: List[str]) -> List[str]:
    """
    Filter mentions based on:
    1. Not already processed
    2. Root post author is a member
    3. Mention author is a member
    
    Returns list of unprocessed mention URIs
    """
    # Load required data
    members = load_members()
    processed = set()
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE, 'r') as f:
            processed = set(json.load(f))
    
    unprocessed = []
    for uri in mention_uris:
        try:
            # Skip if already processed
            if uri in processed:
                logger.debug(f"Skipping processed mention: {uri}")
                continue
            
            # Get thread containing this post
            post_data = get_post_info(uri)
            if not post_data:
                logger.warning(f"No thread found for {uri}")
                continue
            
            post = post_data['post']
            thread = post_data['thread']
            
            # Check mention author is member
            mention_author = post.get('author')
            if not mention_author or not is_member(mention_author, members):
                logger.info(f"Skipping mention from non-member: {mention_author}")
                continue
            
            # Check root post author is member
            root_post = get_root_post(thread)
            if root_post:
                root_author = root_post.get('author')
                if not root_author or not is_member(root_author, members):
                    logger.info(f"Skipping mention in thread started by non-member: {root_author}")
                    continue
            
            # If we get here, the mention passes all checks
            unprocessed.append(uri)
            
        except Exception as e:
            logger.error(f"Error processing mention {uri}: {str(e)}")
    
    logger.info(f"Found {len(unprocessed)} valid unprocessed mentions out of {len(mention_uris)} total")
    return unprocessed

def extract_json_from_output(data: str) -> List[str]:
    """
    Extract JSON from a potentially multi-line output that contains 
    other text besides JSON
    """
    # Try to find JSON array in the output
    json_pattern = r'\[.*\]'
    match = re.search(json_pattern, data, re.DOTALL)
    
    if match:
        try:
            json_str = match.group(0)
            uris = json.loads(json_str)
            if isinstance(uris, list):
                logger.info(f"Successfully extracted {len(uris)} URIs from JSON in output")
                return uris
        except json.JSONDecodeError as e:
            logger.warning(f"Found JSON-like pattern but failed to parse: {e}")
    
    return []

def read_mention_uris_from_stdin() -> List[str]:
    """Read mention URIs from stdin, useful for piping from other scripts"""
    try:
        logger.info("Reading mention URIs from stdin")
        data = sys.stdin.read().strip()
        if not data:
            logger.warning("No data received from stdin")
            return []
        
        # First, try to extract JSON from a potentially multi-line output
        uris = extract_json_from_output(data)
        if uris:
            return uris
        
        # If that doesn't work, try to parse the entire input as JSON
        try:
            uris = json.loads(data)
            if isinstance(uris, list):
                logger.info(f"Successfully parsed {len(uris)} URIs from JSON input")
                return uris
        except json.JSONDecodeError:
            # If not JSON, try looking for URI patterns
            uri_pattern = r'at://[^\s"]+'
            uris = re.findall(uri_pattern, data)
            if uris:
                logger.info(f"Extracted {len(uris)} URIs using regex pattern")
                return uris
                
            # Last resort: try parsing as newline-separated URIs
            potential_uris = [line.strip() for line in data.split('\n') if line.strip()]
            # Filter to keep only lines that might be URIs
            uris = [uri for uri in potential_uris if uri.startswith('at://')]
            if uris:
                logger.info(f"Filtered {len(uris)} potential URIs from input")
                return uris
            
            logger.warning("Could not extract valid URIs from input")
            return []
            
    except Exception as e:
        logger.error(f"Error reading from stdin: {str(e)}")
        return []

def main():
    """Main function with example usage"""
    logger.info("Starting filter_mentions.py")
    
    # Ensure data directory exists
    setup_data_dir()
    
    # Example mentions - in real usage these would come from stdin
    example_mentions = [
        "at://did:plc:xyz/app.bsky.feed.post/123",  # Non-member post
        "at://did:plc:evocjxmi5cps2thb4ya5jcji/app.bsky.feed.post/3lmc5zjc5ms23"  # Member post
    ]
    

    
    # Filter unprocessed mentions
    unprocessed = filter_unprocessed_mentions(example_mentions)
    
    # Display results
    if unprocessed:
        logger.info(f"Found {len(unprocessed)} unprocessed mentions")
        # Output as JSON for piping to other scripts
        print(json.dumps(unprocessed))
    else:
        logger.info("No unprocessed mentions found")
        print("[]")  # Empty JSON array

if __name__ == "__main__":
    main()