from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class Member(BaseModel):
    """Model for a SharedInventory member."""
    
    did: str  # Decentralized identifier (DID) - unique identifier for the member
    handle: str
    display_name: Optional[str] = None
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    profile: Dict[str, Any] = Field(default_factory=dict)  # Profile data from Bluesky
    locations: List[str] = Field(default_factory=list)  # Locations where member has items
    preferences: Dict[str, Any] = Field(default_factory=dict)  # User preferences
    
    def to_dict(self):
        """Convert the model to a dictionary for storage in MongoDB."""
        return {
            "did": self.did,
            "handle": self.handle,
            "display_name": self.display_name,
            "joined_at": self.joined_at,
            "profile": self.profile,
            "locations": self.locations,
            "preferences": self.preferences
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create a Member from a dictionary."""
        return cls(**data)
    
    @classmethod
    def from_profile(cls, profile, locations=None, preferences=None):
        """Create a Member from a Bluesky profile."""
        return cls(
            did=profile.did,
            handle=profile.handle,
            display_name=getattr(profile, 'display_name', None),
            profile={
                "description": getattr(profile, 'description', None),
                "avatar": getattr(profile, 'avatar', None),
                "followers": getattr(profile, 'followers_count', 0),
                "following": getattr(profile, 'follows_count', 0)
            },
            locations=locations or [],
            preferences=preferences or {}
        )