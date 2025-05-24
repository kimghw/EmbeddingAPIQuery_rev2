"""Graph API port interface for Microsoft Graph API integration."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

from ..domain.email import Email
from ..domain.account import Account


class EmailData(BaseModel):
    """Email data transfer object for Graph API responses."""
    
    id: str
    subject: Optional[str] = None
    body_preview: Optional[str] = None
    body_content: Optional[str] = None
    body_content_type: Optional[str] = None
    sender_email: Optional[str] = None
    sender_name: Optional[str] = None
    to_recipients: List[str] = []
    cc_recipients: List[str] = []
    bcc_recipients: List[str] = []
    received_datetime: Optional[datetime] = None
    sent_datetime: Optional[datetime] = None
    is_read: bool = False
    importance: Optional[str] = None
    has_attachments: bool = False
    attachments: List[Dict[str, Any]] = []
    categories: List[str] = []
    flag_status: Optional[str] = None
    conversation_id: Optional[str] = None
    internet_message_id: Optional[str] = None
    web_link: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class TokenInfo(BaseModel):
    """Token information data transfer object."""
    
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None
    id_token: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class GraphAPIPort(ABC):
    """Microsoft Graph API port interface."""
    
    @abstractmethod
    async def authenticate(self, account: Account) -> Dict[str, Any]:
        """
        Authenticate with Microsoft Graph API using OAuth 2.0.
        
        Args:
            account: Account to authenticate
            
        Returns:
            Token information dictionary
        """
        pass
    
    @abstractmethod
    async def refresh_token(self, account: Account) -> Dict[str, Any]:
        """
        Refresh access token.
        
        Args:
            account: Account with refresh token
            
        Returns:
            New token information dictionary
        """
        pass
    
    @abstractmethod
    async def get_authorization_url(self, state: str = None) -> str:
        """
        Get OAuth authorization URL.
        
        Args:
            state: Optional state parameter for security
            
        Returns:
            Authorization URL
        """
        pass
    
    @abstractmethod
    async def exchange_code_for_token(self, code: str, state: str = None) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from callback
            state: State parameter for validation
            
        Returns:
            Token information dictionary
        """
        pass
    
    @abstractmethod
    async def get_user_profile(self, access_token: str) -> Dict[str, Any]:
        """
        Get user profile information.
        
        Args:
            access_token: Valid access token
            
        Returns:
            User profile data
        """
        pass
    
    @abstractmethod
    async def get_emails(
        self, 
        access_token: str, 
        folder: str = "inbox",
        top: int = 50,
        skip: int = 0,
        filter_query: str = None,
        order_by: str = "receivedDateTime desc"
    ) -> List[Dict[str, Any]]:
        """
        Get emails from specified folder.
        
        Args:
            access_token: Valid access token
            folder: Folder name (inbox, sent, drafts, etc.)
            top: Number of emails to retrieve
            skip: Number of emails to skip
            filter_query: OData filter query
            order_by: Order by clause
            
        Returns:
            List of email data dictionaries
        """
        pass
    
    @abstractmethod
    async def get_email_by_id(self, access_token: str, message_id: str) -> Dict[str, Any]:
        """
        Get specific email by message ID.
        
        Args:
            access_token: Valid access token
            message_id: Email message ID
            
        Returns:
            Email data dictionary
        """
        pass
    
    @abstractmethod
    async def get_delta_emails(
        self, 
        access_token: str, 
        delta_link: str = None,
        folder: str = "inbox"
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Get email changes using delta query.
        
        Args:
            access_token: Valid access token
            delta_link: Previous delta link for incremental sync
            folder: Folder name to monitor
            
        Returns:
            Tuple of (email changes list, new delta link)
        """
        pass
    
    @abstractmethod
    async def create_subscription(
        self, 
        access_token: str,
        notification_url: str,
        resource: str = "me/mailFolders('Inbox')/messages",
        change_types: List[str] = None,
        expiration_minutes: int = 4230  # Max 3 days
    ) -> Dict[str, Any]:
        """
        Create webhook subscription for email changes.
        
        Args:
            access_token: Valid access token
            notification_url: Webhook endpoint URL
            resource: Resource to monitor
            change_types: Types of changes to monitor (created, updated, deleted)
            expiration_minutes: Subscription expiration in minutes
            
        Returns:
            Subscription information
        """
        pass
    
    @abstractmethod
    async def renew_subscription(
        self, 
        access_token: str,
        subscription_id: str,
        expiration_minutes: int = 4230
    ) -> Dict[str, Any]:
        """
        Renew existing webhook subscription.
        
        Args:
            access_token: Valid access token
            subscription_id: Subscription ID to renew
            expiration_minutes: New expiration in minutes
            
        Returns:
            Updated subscription information
        """
        pass
    
    @abstractmethod
    async def delete_subscription(self, access_token: str, subscription_id: str) -> bool:
        """
        Delete webhook subscription.
        
        Args:
            access_token: Valid access token
            subscription_id: Subscription ID to delete
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def get_subscriptions(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Get all active subscriptions.
        
        Args:
            access_token: Valid access token
            
        Returns:
            List of subscription information
        """
        pass
    
    @abstractmethod
    async def send_email(
        self, 
        access_token: str,
        to_recipients: List[str],
        subject: str,
        body: str,
        body_type: str = "HTML",
        cc_recipients: List[str] = None,
        bcc_recipients: List[str] = None,
        attachments: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send email via Graph API.
        
        Args:
            access_token: Valid access token
            to_recipients: List of recipient email addresses
            subject: Email subject
            body: Email body content
            body_type: Body content type (HTML or Text)
            cc_recipients: CC recipients
            bcc_recipients: BCC recipients
            attachments: Email attachments
            
        Returns:
            Sent email information
        """
        pass
    
    @abstractmethod
    async def get_folders(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Get mail folders.
        
        Args:
            access_token: Valid access token
            
        Returns:
            List of folder information
        """
        pass
    
    @abstractmethod
    async def mark_as_read(self, access_token: str, message_id: str) -> bool:
        """
        Mark email as read.
        
        Args:
            access_token: Valid access token
            message_id: Email message ID
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def move_to_folder(
        self, 
        access_token: str, 
        message_id: str, 
        destination_folder_id: str
    ) -> bool:
        """
        Move email to different folder.
        
        Args:
            access_token: Valid access token
            message_id: Email message ID
            destination_folder_id: Target folder ID
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def delete_email(self, access_token: str, message_id: str) -> bool:
        """
        Delete email.
        
        Args:
            access_token: Valid access token
            message_id: Email message ID
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def validate_token(self, access_token: str) -> bool:
        """
        Validate access token.
        
        Args:
            access_token: Access token to validate
            
        Returns:
            True if token is valid
        """
        pass
    
    @abstractmethod
    async def get_token_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get token information and expiration.
        
        Args:
            access_token: Access token
            
        Returns:
            Token information including expiration
        """
        pass


class GraphAPIError(Exception):
    """Graph API specific error."""
    
    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class GraphAPIAuthenticationError(GraphAPIError):
    """Graph API authentication error."""
    pass


# Alias for backward compatibility
AuthenticationError = GraphAPIAuthenticationError


class GraphAPIRateLimitError(GraphAPIError):
    """Graph API rate limit error."""
    pass


class GraphAPINotFoundError(GraphAPIError):
    """Graph API resource not found error."""
    pass


class TokenExpiredError(GraphAPIAuthenticationError):
    """Token expired error."""
    pass


# Additional aliases for backward compatibility
RateLimitError = GraphAPIRateLimitError
NotFoundError = GraphAPINotFoundError
