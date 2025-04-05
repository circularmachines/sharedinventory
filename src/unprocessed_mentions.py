#!/usr/bin/env python3
"""
Standalone script to filter unprocessed mentions from a list of post URIs.
This script takes a list of post URIs and returns only those that have not been
processed before based on a local tracking file.
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


def setup_data_dir() -> bool:
    """Ensure the data directory exists"""
    try:
        if not DATA_DIR.exists():
            logger.info(f"Creating data directory: {DATA_DIR}")
            DATA_DIR.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create data directory: {str(e)}")
        return False


def load_processed_mentions() -> Set[str]:
    """Load the set of previously processed mention URIs"""
    processed = set()
    
    if not PROCESSED_FILE.exists():
        logger.info(f"No processed mentions file found at {PROCESSED_FILE}")
        return processed
    
    try:
        with open(PROCESSED_FILE, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                processed = set(data)
                logger.info(f"Loaded {len(processed)} processed mentions")
            else:
                logger.warning(f"Invalid format in {PROCESSED_FILE}, expected a list")
    except Exception as e:
        logger.error(f"Error loading processed mentions: {str(e)}")
    
    return processed


def save_processed_mentions(mention_uris: List[str]) -> bool:
    """
    Add new mention URIs to the processed list and save to file
    
    Args:
        mention_uris: List of mention URIs to mark as processed
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not setup_data_dir():
        return False
    
    # Load existing processed mentions
    processed = load_processed_mentions()
    
    # Add new mentions
    processed.update(mention_uris)
    
    try:
        with open(PROCESSED_FILE, 'w') as f:
            json.dump(list(processed), f, indent=2)
        logger.info(f"Saved {len(processed)} processed mentions")
        return True
    except Exception as e:
        logger.error(f"Error saving processed mentions: {str(e)}")
        return False


def filter_unprocessed_mentions(mention_uris: List[str]) -> List[str]:
    """
    Filter out mentions that have already been processed
    
    Args:
        mention_uris: List of mention URIs to filter
        
    Returns:
        List of unprocessed mention URIs
    """
    # Load existing processed mentions
    processed = load_processed_mentions()
    
    # Filter unprocessed mentions
    unprocessed = [uri for uri in mention_uris if uri not in processed]
    
    logger.info(f"Found {len(unprocessed)} unprocessed mentions out of {len(mention_uris)} total")
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
    """Main function"""
    logger.info("Starting unprocessed_mentions.py")
    
    # Read mention URIs from stdin
    mention_uris = read_mention_uris_from_stdin()
    
    if not mention_uris:
        logger.warning("No mention URIs provided")
        sys.exit(1)
    
    # Filter unprocessed mentions
    unprocessed = filter_unprocessed_mentions(mention_uris)
    
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