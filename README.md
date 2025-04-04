# SharedInventory Bot for Bluesky

A bot for Bluesky that adds members' posts to a shared inventory database.

## Overview

The SharedInventory bot monitors mentions, processes the content of posts, and adds items to a shared inventory. Members can browse this inventory through a web interface (coming in a later phase).

## Features (Phase 1 - MVP)

- **Mention Monitoring**: Bot listens for mentions and responds accordingly
- **Membership Verification**: Checks if users are members before processing their posts
- **Automated Responses**: Provides information on how to join for non-members
- **Basic Member Management**: Stores member information in a database

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
5. Edit `.env` with your Bluesky bot credentials and MongoDB connection string
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

## Project Structure

- `main.py`: Entry point for the application
- `src/`: Source code directory
  - `api/`: API integrations (Bluesky)
  - `bot_handler.py`: Core bot logic
  - `db/`: Database handlers
  - `models/`: Data models
  - `utils/`: Utility functions and configuration

## Future Development

- **Phase 2**: Content analysis for posts (text, images, videos)
- **Phase 3**: Web interface for browsing the inventory

## Requirements

- Python 3.8+
- MongoDB
- Bluesky account for the bot