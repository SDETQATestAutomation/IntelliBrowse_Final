"""
User model for MongoDB user document storage.
Defines the user data structure and database operations for authentication.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId

from ..config.env import get_settings
from ..config.logging import get_logger

logger = get_logger(__name__)


class UserModel(BaseModel):
    """
    User document model for MongoDB storage.
    
    Represents a user in the authentication system with secure password storage
    and audit fields for tracking account creation and updates.
    """
    
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    email: EmailStr = Field(..., description="User email address (unique identifier)")
    hashed_password: str = Field(..., description="Bcrypt hashed password")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    is_active: bool = Field(default=True, description="Account active status")
    login_count: int = Field(default=0, description="Number of successful logins")
    last_login: Optional[datetime] = Field(None, description="Last successful login timestamp")
    
    class Config:
        """Pydantic model configuration."""
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat(),
        }
    
    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> "UserModel":
        """
        Create UserModel instance from MongoDB document.
        
        Args:
            data: Raw MongoDB document
            
        Returns:
            UserModel instance
        """
        if not data:
            return None
            
        # Convert ObjectId to string for the id field
        if "_id" in data:
            data["_id"] = str(data["_id"])
            
        return cls(**data)
    
    def to_mongo(self) -> Dict[str, Any]:
        """
        Convert UserModel to MongoDB document format.
        
        Returns:
            Dictionary suitable for MongoDB insertion
        """
        data = self.model_dump(by_alias=True, exclude_unset=True)
        
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        
        # Convert string id back to ObjectId for MongoDB
        if "_id" in data and isinstance(data["_id"], str):
            data["_id"] = ObjectId(data["_id"])
            
        return data
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert UserModel to plain dictionary (safe for API responses).
        Excludes sensitive information like hashed_password.
        
        Returns:
            Dictionary with safe user information
        """
        return {
            "id": self.id,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
            "login_count": self.login_count,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
    
    def update_login_info(self) -> None:
        """Update login tracking information."""
        self.login_count += 1
        self.last_login = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        logger.info(
            f"Updated login info for user {self.email}",
            extra={
                "user_email": self.email,
                "login_count": self.login_count,
                "last_login": self.last_login.isoformat(),
            }
        )


class UserCreateModel(BaseModel):
    """
    Model for creating new users.
    Used for validation during user registration.
    """
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ..., 
        min_length=8, 
        max_length=128,
        description="User password (8-128 characters)"
    )
    
    def validate_password_strength(self) -> bool:
        """
        Validate password meets strength requirements.
        
        Returns:
            True if password meets requirements
            
        Raises:
            ValueError: If password doesn't meet requirements
        """
        password = self.password
        
        # Check length
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        if len(password) > 128:
            raise ValueError("Password must not exceed 128 characters")
        
        # Check for at least one digit
        if not any(char.isdigit() for char in password):
            raise ValueError("Password must contain at least one digit")
        
        # Check for at least one uppercase letter
        if not any(char.isupper() for char in password):
            raise ValueError("Password must contain at least one uppercase letter")
        
        # Check for at least one lowercase letter
        if not any(char.islower() for char in password):
            raise ValueError("Password must contain at least one lowercase letter")
        
        return True


class UserLoginModel(BaseModel):
    """
    Model for user login credentials.
    Used for validation during authentication.
    """
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class UserUpdateModel(BaseModel):
    """
    Model for updating user information.
    Used for partial user updates (future use).
    """
    
    email: Optional[EmailStr] = Field(None, description="Updated email address")
    is_active: Optional[bool] = Field(None, description="Updated active status")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Update timestamp")


# MongoDB collection operations helper
class UserModelOperations:
    """
    Helper class for MongoDB operations on user documents.
    Provides database interaction methods with proper error handling.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.collection_name = self.settings.mongodb_collection_users
    
    @staticmethod
    def get_user_indexes() -> list:
        """
        Get MongoDB indexes for the users collection.
        
        Returns:
            List of index specifications
        """
        return [
            {"key": [("email", 1)], "unique": True, "background": True},
            {"key": [("created_at", -1)], "background": True},
            {"key": [("is_active", 1)], "background": True},
        ]
    
    @staticmethod
    def validate_user_document(data: Dict[str, Any]) -> bool:
        """
        Validate user document structure.
        
        Args:
            data: User document to validate
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If document is invalid
        """
        required_fields = ["email", "hashed_password", "created_at"]
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate email format (basic check)
        email = data.get("email", "")
        if "@" not in email or "." not in email:
            raise ValueError("Invalid email format")
        
        # Validate hashed password exists
        if not data.get("hashed_password"):
            raise ValueError("Hashed password cannot be empty")
        
        return True 