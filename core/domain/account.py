"""Account domain entity for Office 365 accounts."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class AccountStatus(str, Enum):
    """Account status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    ERROR = "error"


class AccountType(str, Enum):
    """Account type enumeration."""
    OFFICE365 = "office365"
    GMAIL = "gmail"  # For future extension


class Account(BaseModel):
    """Account domain entity for managing external email accounts."""
    
    id: Optional[str] = Field(default=None, description="Account unique identifier")
    user_id: str = Field(..., description="Associated user ID")
    account_type: AccountType = Field(default=AccountType.OFFICE365, description="Account type")
    email_address: str = Field(..., description="Account email address")
    display_name: Optional[str] = Field(default=None, description="Account display name")
    tenant_id: Optional[str] = Field(default=None, description="Azure tenant ID")
    client_id: Optional[str] = Field(default=None, description="Azure client ID")
    status: AccountStatus = Field(default=AccountStatus.ACTIVE, description="Account status")
    
    # Token management
    access_token: Optional[str] = Field(default=None, description="Current access token")
    refresh_token: Optional[str] = Field(default=None, description="Refresh token")
    token_expires_at: Optional[datetime] = Field(default=None, description="Token expiration time")
    
    # Sync settings
    last_sync_at: Optional[datetime] = Field(default=None, description="Last synchronization time")
    sync_enabled: bool = Field(default=True, description="Whether sync is enabled")
    delta_link: Optional[str] = Field(default=None, description="Graph API delta link for incremental sync")
    
    # Metadata
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    last_error: Optional[str] = Field(default=None, description="Last error message")
    error_count: int = Field(default=0, description="Consecutive error count")
    
    @validator("email_address")
    def validate_email(cls, v):
        """Validate email format."""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()
    
    def is_token_valid(self) -> bool:
        """Check if the access token is still valid."""
        if not self.access_token or not self.token_expires_at:
            return False
        return datetime.utcnow() < self.token_expires_at
    
    def is_token_expired(self) -> bool:
        """Check if the access token is expired."""
        return not self.is_token_valid()
    
    def update_tokens(self, access_token: str, refresh_token: str = None, expires_in: int = 3600) -> None:
        """Update account tokens."""
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        self.token_expires_at = datetime.utcnow().replace(microsecond=0) + datetime.timedelta(seconds=expires_in)
        self.updated_at = datetime.utcnow()
        self.clear_error()
    
    def clear_tokens(self) -> None:
        """Clear account tokens."""
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.updated_at = datetime.utcnow()
    
    def update_sync_status(self, delta_link: str = None) -> None:
        """Update synchronization status."""
        self.last_sync_at = datetime.utcnow()
        if delta_link:
            self.delta_link = delta_link
        self.updated_at = datetime.utcnow()
        self.clear_error()
    
    def enable_sync(self) -> None:
        """Enable synchronization for this account."""
        self.sync_enabled = True
        self.updated_at = datetime.utcnow()
    
    def disable_sync(self) -> None:
        """Disable synchronization for this account."""
        self.sync_enabled = False
        self.updated_at = datetime.utcnow()
    
    def activate(self) -> None:
        """Activate the account."""
        self.status = AccountStatus.ACTIVE
        self.updated_at = datetime.utcnow()
        self.clear_error()
    
    def deactivate(self) -> None:
        """Deactivate the account."""
        self.status = AccountStatus.INACTIVE
        self.updated_at = datetime.utcnow()
    
    def mark_expired(self) -> None:
        """Mark the account as expired."""
        self.status = AccountStatus.EXPIRED
        self.updated_at = datetime.utcnow()
    
    def mark_error(self, error_message: str) -> None:
        """Mark the account as having an error."""
        self.status = AccountStatus.ERROR
        self.last_error = error_message
        self.error_count += 1
        self.updated_at = datetime.utcnow()
    
    def clear_error(self) -> None:
        """Clear error status."""
        if self.status == AccountStatus.ERROR:
            self.status = AccountStatus.ACTIVE
        self.last_error = None
        self.error_count = 0
        self.updated_at = datetime.utcnow()
    
    def is_active(self) -> bool:
        """Check if account is active."""
        return self.status == AccountStatus.ACTIVE
    
    def is_sync_ready(self) -> bool:
        """Check if account is ready for synchronization."""
        return (
            self.is_active() and 
            self.sync_enabled and 
            self.is_token_valid()
        )
    
    def should_retry(self, max_errors: int = 5) -> bool:
        """Check if account should be retried after errors."""
        return self.error_count < max_errors
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AccountCreateRequest(BaseModel):
    """Account creation request model."""
    
    user_id: str = Field(..., description="Associated user ID")
    account_type: AccountType = Field(default=AccountType.OFFICE365, description="Account type")
    email_address: str = Field(..., description="Account email address")
    display_name: Optional[str] = Field(default=None, description="Account display name")
    tenant_id: Optional[str] = Field(default=None, description="Azure tenant ID")
    client_id: Optional[str] = Field(default=None, description="Azure client ID")
    
    @validator("email_address")
    def validate_email(cls, v):
        """Validate email format."""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()


class AccountUpdateRequest(BaseModel):
    """Account update request model."""
    
    display_name: Optional[str] = Field(default=None, description="Account display name")
    sync_enabled: Optional[bool] = Field(default=None, description="Whether sync is enabled")
    status: Optional[AccountStatus] = Field(default=None, description="Account status")


class AccountResponse(BaseModel):
    """Account response model."""
    
    id: str = Field(..., description="Account unique identifier")
    user_id: str = Field(..., description="Associated user ID")
    account_type: AccountType = Field(..., description="Account type")
    email_address: str = Field(..., description="Account email address")
    display_name: Optional[str] = Field(default=None, description="Account display name")
    status: AccountStatus = Field(..., description="Account status")
    sync_enabled: bool = Field(..., description="Whether sync is enabled")
    last_sync_at: Optional[datetime] = Field(default=None, description="Last synchronization time")
    token_valid: bool = Field(..., description="Whether access token is valid")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    last_error: Optional[str] = Field(default=None, description="Last error message")
    error_count: int = Field(..., description="Consecutive error count")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class TokenUpdateRequest(BaseModel):
    """Token update request model."""
    
    access_token: str = Field(..., description="Access token")
    refresh_token: Optional[str] = Field(default=None, description="Refresh token")
    expires_in: int = Field(default=3600, description="Token expiration time in seconds")
