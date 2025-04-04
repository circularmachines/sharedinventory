import os
from dotenv import load_dotenv

# Load test environment variables
load_dotenv('.env.test')

# Bot credentials
BOT_USERNAME = os.getenv("TEST_BOT_USERNAME")
BOT_PASSWORD = os.getenv("TEST_BOT_PASSWORD")

# Test user credentials (for simulating mentions)
TEST_USER_USERNAME = os.getenv("TEST_USER_USERNAME")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD")

# Optional second test user
TEST_USER2_USERNAME = os.getenv("TEST_USER2_USERNAME")
TEST_USER2_PASSWORD = os.getenv("TEST_USER2_PASSWORD")

# MongoDB test database (to avoid affecting production data)
DB_CONNECTION_STRING = os.getenv("TEST_DB_CONNECTION_STRING", "mongodb://localhost:27017/")
DB_NAME = os.getenv("TEST_DB_NAME", "shared_inventory_test")

def validate_test_config():
    """Validate that all required test configuration variables are set."""
    required_vars = ["TEST_BOT_USERNAME", "TEST_BOT_PASSWORD", "TEST_USER_USERNAME", "TEST_USER_PASSWORD"]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        raise EnvironmentError(
            f"Missing required test environment variables: {', '.join(missing)}. "
            f"Please check your .env.test file."
        )