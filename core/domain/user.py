"""User domain entity."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


class UserStatus(str, Enum):
    """User status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class User(BaseModel):
    """User domain entity."""
    
    id: Optional[str] = Field(default=None, description="User unique identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="User email address")
    full_name: Optional[str] = Field(default=None, description="User full name")
    status: UserStatus = Field(default=UserStatus.ACTIVE, description="User status")
    account_ids: List[str] = Field(default_factory=list, description="Associated account IDs")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    last_login_at: Optional[datetime] = Field(default=None, description="Last login timestamp")
    
    @validator("email")
    def validate_email(cls, v):
        """Validate email format."""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()
    
    @validator("username")
    def validate_username(cls, v):
        """Validate username format."""
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, hyphens, and underscores")
        return v.lower()
    
    def add_account(self, account_id: str) -> None:
        """Add an account to the user."""
        if account_id not in self.account_ids:
            self.account_ids.append(account_id)
            self.updated_at = datetime.utcnow()
    
    def remove_account(self, account_id: str) -> bool:
        """Remove an account from the user."""
        if account_id in self.account_ids:
            self.account_ids.remove(account_id)
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def has_account(self, account_id: str) -> bool:
        """Check if user has a specific account."""
        return account_id in self.account_ids
    
    def activate(self) -> None:
        """Activate the user."""
        self.status = UserStatus.ACTIVE
        self.updated_at = datetime.utcnow()
    
    def deactivate(self) -> None:
        """Deactivate the user."""
        self.status = UserStatus.INACTIVE
        self.updated_at = datetime.utcnow()
    
    def suspend(self) -> None:
        """Suspend the user."""
        self.status = UserStatus.SUSPENDED
        self.updated_at = datetime.utcnow()
    
    def is_active(self) -> bool:
        """Check if user is active."""
        return self.status == UserStatus.ACTIVE
    
    def update_last_login(self) -> None:
        """Update last login timestamp."""
        self.last_login_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class UserCreateRequest(BaseModel):
    """User creation request model."""
    
    username: str = Field(..., description="Username")
    email: str = Field(..., description="User email address")
    full_name: Optional[str] = Field(default=None, description="User full name")
    
    @validator("email")
    def validate_email(cls, v):
        """Validate email format."""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()
    
    @validator("username")
    def validate_username(cls, v):
        """Validate username format."""
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, hyphens, and underscores")
        return v.lower()


class UserUpdateRequest(BaseModel):
    """User update request model."""
    
    full_name: Optional[str] = Field(default=None, description="User full name")
    status: Optional[UserStatus] = Field(default=None, description="User status")


class UserResponse(BaseModel):
    """User response model."""
    
    id: str = Field(..., description="User unique identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="User email address")
    full_name: Optional[str] = Field(default=None, description="User full name")
    status: UserStatus = Field(..., description="User status")
    account_count: int = Field(..., description="Number of associated accounts")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    last_login_at: Optional[datetime] = Field(default=None, description="Last login timestamp")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
