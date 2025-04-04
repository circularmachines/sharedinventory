import logging
import sys
from src.bot_handler import BotHandler
from src.utils.config import validate_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main entry point for the SharedInventory bot."""
    try:
        # Validate configuration
        validate_config()
        
        # Create and run the bot handler
        logger.info("Starting SharedInventory bot")
        bot = BotHandler()
        bot.run()
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()