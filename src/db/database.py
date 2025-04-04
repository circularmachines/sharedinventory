import logging
import json
import os
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..utils.config import DB_DIRECTORY, MEMBERS_FILE, INVENTORY_FILE

logger = logging.getLogger(__name__)

# Custom JSON encoder to handle datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super(DateTimeEncoder, self).default(obj)

class DatabaseHandler:
    """Handles database operations for the SharedInventory bot using JSON files."""
    
    def __init__(self):
        """Initialize the database handler."""
        try:
            # Ensure the database directory exists
            os.makedirs(DB_DIRECTORY, exist_ok=True)
            
            # Initialize members file if it doesn't exist
            self.members_path = os.path.join(DB_DIRECTORY, MEMBERS_FILE)
            if not os.path.exists(self.members_path):
                self._write_json(self.members_path, [])
            
            # Initialize inventory file if it doesn't exist
            self.inventory_path = os.path.join(DB_DIRECTORY, INVENTORY_FILE)
            if not os.path.exists(self.inventory_path):
                self._write_json(self.inventory_path, [])
            
            logger.info(f"JSON database initialized at {DB_DIRECTORY}")
        except Exception as e:
            logger.error(f"Failed to initialize JSON database: {str(e)}")
            raise
    
    def _read_json(self, file_path: str) -> List[Dict[str, Any]]:
        """Read data from a JSON file."""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {file_path}, returning empty list")
            return []
    
    def _write_json(self, file_path: str, data: List[Dict[str, Any]]) -> bool:
        """Write data to a JSON file with retry logic."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2, cls=DateTimeEncoder)
                return True
            except Exception as e:
                logger.error(f"Error writing to JSON file {file_path} (attempt {attempt+1}/{max_attempts}): {str(e)}")
                if attempt < max_attempts - 1:
                    time.sleep(0.5)  # Wait before retrying
        return False
    
    def is_member(self, user_did: str) -> bool:
        """
        Check if a user is a member.
        
        Args:
            user_did: The DID of the user to check.
            
        Returns:
            True if the user is a member, False otherwise.
        """
        members = self._read_json(self.members_path)
        return any(member["did"] == user_did for member in members)
    
    def add_member(self, user_data: Dict[str, Any]) -> bool:
        """
        Add a new member.
        
        Args:
            user_data: Dictionary containing user information.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            members = self._read_json(self.members_path)
            
            # Check if member already exists
            for i, member in enumerate(members):
                if member["did"] == user_data["did"]:
                    # Update existing member
                    members[i] = user_data
                    return self._write_json(self.members_path, members)
            
            # Add new member
            members.append(user_data)
            return self._write_json(self.members_path, members)
        except Exception as e:
            logger.error(f"Error adding member: {str(e)}")
            return False
    
    def add_inventory_item(self, item_data: Dict[str, Any]) -> bool:
        """
        Add a new inventory item.
        
        Args:
            item_data: Dictionary containing item information.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            items = self._read_json(self.inventory_path)
            items.append(item_data)
            return self._write_json(self.inventory_path, items)
        except Exception as e:
            logger.error(f"Error adding inventory item: {str(e)}")
            return False
    
    def get_items_by_member(self, member_did: str) -> List[Dict[str, Any]]:
        """
        Get all inventory items added by a specific member.
        
        Args:
            member_did: The DID of the member.
            
        Returns:
            List of inventory items.
        """
        try:
            items = self._read_json(self.inventory_path)
            return [item for item in items if item.get("added_by") == member_did]
        except Exception as e:
            logger.error(f"Error getting items by member: {str(e)}")
            return []