import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bluesky credentials
BLUESKY_USERNAME = os.getenv("BLUESKY_USERNAME")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")

# Application settings
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))

# Database configuration
DB_DIRECTORY = os.getenv("DB_DIRECTORY", "data")
MEMBERS_FILE = os.getenv("MEMBERS_FILE", "members.json")
INVENTORY_FILE = os.getenv("INVENTORY_FILE", "inventory.json")

# Make sure required environment variables are set
def validate_config():
    """Validate that all required configuration variables are set."""
    required_vars = ["BLUESKY_USERNAME", "BLUESKY_PASSWORD"]
    missing = [var for var in required_vars if not locals()[var]]
    
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Please check your .env file."
        )