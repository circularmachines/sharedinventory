from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

class InventoryItem(BaseModel):
    """Model for an inventory item."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    added_by: str  # DID of the member who added the item
    added_at: datetime = Field(default_factory=datetime.utcnow)
    post_uri: str  # URI of the post that mentioned this item
    image_urls: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    status: str = "available"  # available, borrowed, unavailable
    
    def to_dict(self):
        """Convert the model to a dictionary for storage in MongoDB."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "location": self.location,
            "added_by": self.added_by,
            "added_at": self.added_at,
            "post_uri": self.post_uri,
            "image_urls": self.image_urls,
            "tags": self.tags,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create an InventoryItem from a dictionary."""
        return cls(**data)