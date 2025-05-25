"""Email detection and analysis use cases."""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from enum import Enum

from ..domain.email import Email
from ..domain.account import Account
from ..ports.repository import AccountRepository, EmailRepository
from ..ports.graph_api import GraphAPIPort
from ..ports.config import ConfigPort


# Enums
class ChangeType(str, Enum):
    """Email change types."""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class DetectionMethod(str, Enum):
    """Email detection methods."""
    DELTA_QUERY = "delta_query"
    WEBHOOK = "webhook"
    POLLING = "polling"


# Request/Response Models
class EmailChangeDetectionRequest(BaseModel):
    """Request model for email change detection."""
    account_id: UUID
    method: DetectionMethod = DetectionMethod.DELTA_QUERY
    folder: str = Field("inbox", description="Folder to monitor")
    delta_link: Optional[str] = Field(None, description="Previous delta link for incremental sync")
    hours_back: int = Field(24, description="Hours to look back for changes")


class EmailChangeItem(BaseModel):
    """Individual email change item."""
    message_id: str
    subject: Optional[str]
    sender: Optional[str]
    received_at: Optional[datetime]
    change_type: ChangeType
    folder: str


class EmailChangeDetectionResponse(BaseModel):
    """Response model for email change detection."""
    account_id: UUID
    changes: List[EmailChangeItem]
    total_changes: int
    new_delta_link: Optional[str]
    detection_method: DetectionMethod
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class EmailAnalysisRequest(BaseModel):
    """Request model for email analysis."""
    email_id: UUID
    analysis_types: List[str] = Field(
        default=["content", "attachments", "metadata"],
        description="Types of analysis to perform"
    )


class EmailAnalysisResult(BaseModel):
    """Email analysis result."""
    analysis_type: str
    result: Dict[str, Any]
    confidence: Optional[float] = None
    processing_time_ms: Optional[int] = None


class EmailAnalysisResponse(BaseModel):
    """Response model for email analysis."""
    email_id: UUID
    message_id: str
    analysis_results: List[EmailAnalysisResult]
    total_processing_time_ms: int
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class BulkEmailDetectionRequest(BaseModel):
    """Request model for bulk email detection across multiple accounts."""
    account_ids: List[UUID]
    method: DetectionMethod = DetectionMethod.DELTA_QUERY
    folder: str = "inbox"
    hours_back: int = 24


class BulkEmailDetectionResponse(BaseModel):
    """Response model for bulk email detection."""
    account_results: List[EmailChangeDetectionResponse]
    total_accounts: int
    total_changes: int
    failed_accounts: List[UUID] = Field(default_factory=list)


class SubscriptionManagementRequest(BaseModel):
    """Request model for webhook subscription management."""
    account_id: UUID
    notification_url: str
    resource: str = "me/mailFolders('Inbox')/messages"
    change_types: List[str] = Field(default=["created", "updated", "deleted"])
    expiration_minutes: int = 4230  # Max 3 days


class SubscriptionManagementResponse(BaseModel):
    """Response model for subscription management."""
    account_id: UUID
    subscription_id: str
    notification_url: str
    expires_at: datetime
    status: str = "active"


class EmailsByStatusResponse(BaseModel):
    """Response model for emails by status."""
    emails: List[Email]
    total_count: int
    status: str


# Use Case Implementation
class EmailDetectionUseCase:
    """Use case for detecting and analyzing email changes."""
    
    def __init__(
        self,
        account_repository: AccountRepository,
        email_repository: EmailRepository,
        graph_api: GraphAPIPort,
        config: ConfigPort
    ):
        self.account_repository = account_repository
        self.email_repository = email_repository
        self.graph_api = graph_api
        self.config = config
    
    async def detect_email_changes(
        self, 
        request: EmailChangeDetectionRequest
    ) -> EmailChangeDetectionResponse:
        """
        Detect email changes for a specific account.
        
        Args:
            request: Email change detection request
            
        Returns:
            Email change detection response
            
        Raises:
            ValueError: If account not found or not authorized
        """
        # Get account and validate
        account = await self.account_repository.find_by_id(request.account_id)
        if not account:
            raise ValueError(f"Account with ID {request.account_id} not found")
        
        if not account.access_token:
            raise ValueError(f"Account {request.account_id} is not authorized")
        
        # Check if token needs refresh
        if account.is_token_expired():
            await self._refresh_account_token(account)
            account = await self.account_repository.find_by_id(request.account_id)
        
        changes = []
        new_delta_link = None
        
        if request.method == DetectionMethod.DELTA_QUERY:
            changes, new_delta_link = await self._detect_via_delta_query(
                account, request.folder, request.delta_link
            )
        elif request.method == DetectionMethod.POLLING:
            changes = await self._detect_via_polling(
                account, request.folder, request.hours_back
            )
        else:
            raise ValueError(f"Detection method {request.method} not supported")
        
        # Save detected emails to database
        await self._save_detected_emails(account.id, changes)
        
        return EmailChangeDetectionResponse(
            account_id=request.account_id,
            changes=changes,
            total_changes=len(changes),
            new_delta_link=new_delta_link,
            detection_method=request.method
        )
    
    async def detect_bulk_email_changes(
        self, 
        request: BulkEmailDetectionRequest
    ) -> BulkEmailDetectionResponse:
        """
        Detect email changes for multiple accounts.
        
        Args:
            request: Bulk email detection request
            
        Returns:
            Bulk email detection response
        """
        account_results = []
        failed_accounts = []
        total_changes = 0
        
        for account_id in request.account_ids:
            try:
                detection_request = EmailChangeDetectionRequest(
                    account_id=account_id,
                    method=request.method,
                    folder=request.folder,
                    hours_back=request.hours_back
                )
                
                result = await self.detect_email_changes(detection_request)
                account_results.append(result)
                total_changes += result.total_changes
                
            except Exception as e:
                failed_accounts.append(account_id)
                # Log error but continue with other accounts
                print(f"Failed to detect changes for account {account_id}: {e}")
        
        return BulkEmailDetectionResponse(
            account_results=account_results,
            total_accounts=len(request.account_ids),
            total_changes=total_changes,
            failed_accounts=failed_accounts
        )
    
    async def analyze_email(
        self, 
        request: EmailAnalysisRequest
    ) -> EmailAnalysisResponse:
        """
        Analyze email content and metadata.
        
        Args:
            request: Email analysis request
            
        Returns:
            Email analysis response
            
        Raises:
            ValueError: If email not found
        """
        # Get email from database
        email = await self.email_repository.find_by_id(request.email_id)
        if not email:
            raise ValueError(f"Email with ID {request.email_id} not found")
        
        analysis_results = []
        total_processing_time = 0
        
        for analysis_type in request.analysis_types:
            start_time = datetime.utcnow()
            
            if analysis_type == "content":
                result = await self._analyze_content(email)
            elif analysis_type == "attachments":
                result = await self._analyze_attachments(email)
            elif analysis_type == "metadata":
                result = await self._analyze_metadata(email)
            else:
                result = {"error": f"Unknown analysis type: {analysis_type}"}
            
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            total_processing_time += processing_time
            
            analysis_results.append(EmailAnalysisResult(
                analysis_type=analysis_type,
                result=result,
                processing_time_ms=processing_time
            ))
        
        return EmailAnalysisResponse(
            email_id=request.email_id,
            message_id=email.message_id,
            analysis_results=analysis_results,
            total_processing_time_ms=total_processing_time
        )
    
    async def get_emails_by_status(
        self, 
        status: str, 
        limit: int = 100, 
        offset: int = 0
    ) -> EmailsByStatusResponse:
        """
        Get emails by processing status.
        
        Args:
            status: Processing status to filter by
            limit: Maximum number of emails to return
            offset: Number of emails to skip
            
        Returns:
            Emails by status response
        """
        emails = await self.email_repository.find_by_status(
            status=status,
            limit=limit,
            offset=offset
        )
        
        total_count = await self.email_repository.count_by_status(status)
        
        return EmailsByStatusResponse(
            emails=emails,
            total_count=total_count,
            status=status
        )
    
    async def create_webhook_subscription(
        self, 
        request: SubscriptionManagementRequest
    ) -> SubscriptionManagementResponse:
        """
        Create webhook subscription for email changes.
        
        Args:
            request: Subscription management request
            
        Returns:
            Subscription management response
            
        Raises:
            ValueError: If account not found or subscription fails
        """
        # Get account and validate
        account = await self.account_repository.find_by_id(request.account_id)
        if not account:
            raise ValueError(f"Account with ID {request.account_id} not found")
        
        if not account.access_token:
            raise ValueError(f"Account {request.account_id} is not authorized")
        
        # Check if token needs refresh
        if account.is_token_expired():
            await self._refresh_account_token(account)
            account = await self.account_repository.find_by_id(request.account_id)
        
        # Create subscription
        subscription_info = await self.graph_api.create_subscription(
            access_token=account.access_token,
            notification_url=request.notification_url,
            resource=request.resource,
            change_types=request.change_types,
            expiration_minutes=request.expiration_minutes
        )
        
        # Calculate expiration time
        expires_at = datetime.utcnow() + timedelta(minutes=request.expiration_minutes)
        
        return SubscriptionManagementResponse(
            account_id=request.account_id,
            subscription_id=subscription_info["id"],
            notification_url=request.notification_url,
            expires_at=expires_at
        )
    
    async def renew_webhook_subscription(
        self, 
        account_id: UUID, 
        subscription_id: str,
        expiration_minutes: int = 4230
    ) -> SubscriptionManagementResponse:
        """
        Renew existing webhook subscription.
        
        Args:
            account_id: Account ID
            subscription_id: Subscription ID to renew
            expiration_minutes: New expiration in minutes
            
        Returns:
            Updated subscription information
            
        Raises:
            ValueError: If account not found or renewal fails
        """
        # Get account and validate
        account = await self.account_repository.find_by_id(account_id)
        if not account:
            raise ValueError(f"Account with ID {account_id} not found")
        
        if not account.access_token:
            raise ValueError(f"Account {account_id} is not authorized")
        
        # Check if token needs refresh
        if account.is_token_expired():
            await self._refresh_account_token(account)
            account = await self.account_repository.find_by_id(account_id)
        
        # Renew subscription
        subscription_info = await self.graph_api.renew_subscription(
            access_token=account.access_token,
            subscription_id=subscription_id,
            expiration_minutes=expiration_minutes
        )
        
        # Calculate new expiration time
        expires_at = datetime.utcnow() + timedelta(minutes=expiration_minutes)
        
        return SubscriptionManagementResponse(
            account_id=account_id,
            subscription_id=subscription_id,
            notification_url=subscription_info.get("notificationUrl", ""),
            expires_at=expires_at
        )
    
    # Private helper methods
    async def _detect_via_delta_query(
        self, 
        account: Account, 
        folder: str, 
        delta_link: Optional[str]
    ) -> Tuple[List[EmailChangeItem], str]:
        """Detect changes using delta query."""
        email_changes, new_delta_link = await self.graph_api.get_delta_emails(
            access_token=account.access_token,
            delta_link=delta_link,
            folder=folder
        )
        
        changes = []
        for email_data in email_changes:
            change_type = self._determine_change_type(email_data)
            
            changes.append(EmailChangeItem(
                message_id=email_data.get("id", ""),
                subject=email_data.get("subject"),
                sender=self._extract_sender(email_data),
                received_at=self._parse_datetime(email_data.get("receivedDateTime")),
                change_type=change_type,
                folder=folder
            ))
        
        return changes, new_delta_link
    
    async def _detect_via_polling(
        self, 
        account: Account, 
        folder: str, 
        hours_back: int
    ) -> List[EmailChangeItem]:
        """Detect changes using polling method."""
        # Calculate time filter
        since_time = datetime.utcnow() - timedelta(hours=hours_back)
        filter_query = f"receivedDateTime ge {since_time.isoformat()}Z"
        
        emails = await self.graph_api.get_emails(
            access_token=account.access_token,
            folder=folder,
            filter_query=filter_query,
            order_by="receivedDateTime desc"
        )
        
        changes = []
        for email_data in emails:
            changes.append(EmailChangeItem(
                message_id=email_data.get("id", ""),
                subject=email_data.get("subject"),
                sender=self._extract_sender(email_data),
                received_at=self._parse_datetime(email_data.get("receivedDateTime")),
                change_type=ChangeType.CREATED,  # Polling assumes new emails
                folder=folder
            ))
        
        return changes
    
    async def _save_detected_emails(
        self, 
        account_id: UUID, 
        changes: List[EmailChangeItem]
    ) -> None:
        """Save detected emails to database."""
        emails_to_save = []
        
        for change in changes:
            # Check if email already exists
            existing_email = await self.email_repository.find_by_message_id(change.message_id)
            
            if not existing_email and change.change_type == ChangeType.CREATED:
                email = Email(
                    account_id=account_id,
                    message_id=change.message_id,
                    subject=change.subject or "",
                    sender=change.sender or "",
                    received_at=change.received_at or datetime.utcnow(),
                    folder=change.folder,
                    processing_status="pending"
                )
                emails_to_save.append(email)
        
        if emails_to_save:
            await self.email_repository.bulk_save(emails_to_save)
    
    async def _refresh_account_token(self, account: Account) -> None:
        """Refresh account access token."""
        token_info = await self.graph_api.refresh_token(account)
        await self.account_repository.update_token_info(
            account_id=account.id,
            token_info=token_info
        )
    
    async def _analyze_content(self, email: Email) -> Dict[str, Any]:
        """Analyze email content."""
        return {
            "word_count": len(email.body.split()) if email.body else 0,
            "has_html": "<html>" in email.body.lower() if email.body else False,
            "language": "unknown",  # Could integrate language detection
            "sentiment": "neutral"   # Could integrate sentiment analysis
        }
    
    async def _analyze_attachments(self, email: Email) -> Dict[str, Any]:
        """Analyze email attachments."""
        attachments = email.attachments or []
        
        return {
            "attachment_count": len(attachments),
            "total_size": sum(att.get("size", 0) for att in attachments),
            "file_types": list(set(att.get("contentType", "").split("/")[0] for att in attachments)),
            "has_executable": any(
                att.get("name", "").endswith((".exe", ".bat", ".cmd")) 
                for att in attachments
            )
        }
    
    async def _analyze_metadata(self, email: Email) -> Dict[str, Any]:
        """Analyze email metadata."""
        return {
            "message_id": email.message_id,
            "folder": email.folder,
            "received_at": email.received_at.isoformat() if email.received_at else None,
            "processing_status": email.processing_status,
            "has_attachments": bool(email.attachments),
            "priority": email.priority or "normal"
        }
    
    def _determine_change_type(self, email_data: Dict[str, Any]) -> ChangeType:
        """Determine the type of change from email data."""
        # This is a simplified implementation
        # In reality, you'd need to check specific fields in the delta response
        if email_data.get("@removed"):
            return ChangeType.DELETED
        elif email_data.get("@odata.type") == "#microsoft.graph.message":
            return ChangeType.CREATED
        else:
            return ChangeType.UPDATED
    
    def _extract_sender(self, email_data: Dict[str, Any]) -> Optional[str]:
        """Extract sender email from email data."""
        sender = email_data.get("sender", {})
        email_address = sender.get("emailAddress", {})
        return email_address.get("address")
    
    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object."""
        if not datetime_str:
            return None
        
        try:
            # Handle ISO format with timezone
            if datetime_str.endswith("Z"):
                return datetime.fromisoformat(datetime_str[:-1])
            else:
                return datetime.fromisoformat(datetime_str)
        except ValueError:
            return None


# Custom Exceptions
class EmailDetectionError(Exception):
    """Base exception for email detection errors."""
    pass


class AccountNotAuthorizedError(EmailDetectionError):
    """Account not authorized error."""
    pass


class TokenExpiredError(EmailDetectionError):
    """Token expired error."""
    pass


class SubscriptionError(EmailDetectionError):
    """Webhook subscription error."""
    pass
