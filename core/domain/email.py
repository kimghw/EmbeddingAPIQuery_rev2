"""Email domain entity."""

from datetime import datetime, UTC
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class EmailChangeType(str, Enum):
    """Email change type enumeration."""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class EmailPriority(str, Enum):
    """Email priority enumeration."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class EmailStatus(str, Enum):
    """Email processing status enumeration."""
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    IGNORED = "ignored"


class EmailAttachment(BaseModel):
    """Email attachment model."""
    
    id: Optional[str] = Field(default=None, description="Attachment ID")
    name: str = Field(..., description="Attachment filename")
    content_type: str = Field(..., description="MIME content type")
    size: int = Field(..., description="Attachment size in bytes")
    is_inline: bool = Field(default=False, description="Whether attachment is inline")
    content_id: Optional[str] = Field(default=None, description="Content ID for inline attachments")
    
    def is_image(self) -> bool:
        """Check if attachment is an image."""
        return self.content_type.startswith("image/")
    
    def is_document(self) -> bool:
        """Check if attachment is a document."""
        document_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/plain",
            "text/csv"
        ]
        return self.content_type in document_types


class EmailRecipient(BaseModel):
    """Email recipient model."""
    
    name: Optional[str] = Field(default=None, description="Recipient display name")
    email: str = Field(..., description="Recipient email address")
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        """Validate email format."""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()


class Email(BaseModel):
    """Email domain entity."""
    
    id: Optional[str] = Field(default=None, description="Email unique identifier")
    account_id: str = Field(..., description="Associated account ID")
    message_id: str = Field(..., description="Original message ID from email provider")
    conversation_id: Optional[str] = Field(default=None, description="Conversation/thread ID")
    
    # Email headers
    subject: str = Field(..., description="Email subject")
    sender: EmailRecipient = Field(..., description="Email sender")
    to_recipients: List[EmailRecipient] = Field(default_factory=list, description="To recipients")
    cc_recipients: List[EmailRecipient] = Field(default_factory=list, description="CC recipients")
    bcc_recipients: List[EmailRecipient] = Field(default_factory=list, description="BCC recipients")
    
    # Email content
    body_preview: Optional[str] = Field(default=None, description="Email body preview")
    body_text: Optional[str] = Field(default=None, description="Plain text body")
    body_html: Optional[str] = Field(default=None, description="HTML body")
    
    # Email metadata
    priority: EmailPriority = Field(default=EmailPriority.NORMAL, description="Email priority")
    is_read: bool = Field(default=False, description="Whether email is read")
    is_draft: bool = Field(default=False, description="Whether email is draft")
    has_attachments: bool = Field(default=False, description="Whether email has attachments")
    attachments: List[EmailAttachment] = Field(default_factory=list, description="Email attachments")
    
    # Timestamps
    sent_at: Optional[datetime] = Field(default=None, description="Email sent timestamp")
    received_at: Optional[datetime] = Field(default=None, description="Email received timestamp")
    created_at: Optional[datetime] = Field(default=None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Record update timestamp")
    
    # Change tracking
    change_type: EmailChangeType = Field(default=EmailChangeType.CREATED, description="Type of change detected")
    change_detected_at: Optional[datetime] = Field(default=None, description="When change was detected")
    
    # Processing status
    status: EmailStatus = Field(default=EmailStatus.PENDING, description="Processing status")
    processed_at: Optional[datetime] = Field(default=None, description="Processing timestamp")
    processing_error: Optional[str] = Field(default=None, description="Processing error message")
    retry_count: int = Field(default=0, description="Number of processing retries")
    
    # Additional metadata
    categories: List[str] = Field(default_factory=list, description="Email categories")
    importance: Optional[str] = Field(default=None, description="Email importance level")
    sensitivity: Optional[str] = Field(default=None, description="Email sensitivity level")
    
    def extract_text_content(self) -> str:
        """Extract text content from email body."""
        if self.body_text:
            return self.body_text
        elif self.body_html:
            # Simple HTML to text conversion (in real implementation, use proper HTML parser)
            import re
            text = re.sub(r'<[^>]+>', '', self.body_html)
            return text.strip()
        elif self.body_preview:
            return self.body_preview
        return ""
    
    def get_all_recipients(self) -> List[EmailRecipient]:
        """Get all recipients (To, CC, BCC)."""
        all_recipients = []
        all_recipients.extend(self.to_recipients)
        all_recipients.extend(self.cc_recipients)
        all_recipients.extend(self.bcc_recipients)
        return all_recipients
    
    def get_recipient_emails(self) -> List[str]:
        """Get all recipient email addresses."""
        return [recipient.email for recipient in self.get_all_recipients()]
    
    def has_keyword(self, keyword: str) -> bool:
        """Check if email contains a specific keyword."""
        keyword_lower = keyword.lower()
        text_content = self.extract_text_content().lower()
        subject_lower = self.subject.lower()
        
        return keyword_lower in text_content or keyword_lower in subject_lower
    
    def has_keywords(self, keywords: List[str]) -> bool:
        """Check if email contains any of the specified keywords."""
        return any(self.has_keyword(keyword) for keyword in keywords)
    
    def mark_processed(self) -> None:
        """Mark email as processed."""
        self.status = EmailStatus.PROCESSED
        self.processed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        self.processing_error = None
    
    def mark_failed(self, error_message: str) -> None:
        """Mark email processing as failed."""
        self.status = EmailStatus.FAILED
        self.processing_error = error_message
        self.retry_count += 1
        self.updated_at = datetime.now(UTC)
    
    def mark_ignored(self, reason: str = None) -> None:
        """Mark email as ignored."""
        self.status = EmailStatus.IGNORED
        if reason:
            self.processing_error = f"Ignored: {reason}"
        self.updated_at = datetime.now(UTC)
    
    def reset_for_retry(self) -> None:
        """Reset email status for retry."""
        self.status = EmailStatus.PENDING
        self.processing_error = None
        self.updated_at = datetime.now(UTC)
    
    def should_retry(self, max_retries: int = 3) -> bool:
        """Check if email should be retried."""
        return self.status == EmailStatus.FAILED and self.retry_count < max_retries
    
    def is_high_priority(self) -> bool:
        """Check if email is high priority."""
        return self.priority == EmailPriority.HIGH
    
    def get_attachment_count(self) -> int:
        """Get number of attachments."""
        return len(self.attachments)
    
    def get_total_attachment_size(self) -> int:
        """Get total size of all attachments in bytes."""
        return sum(attachment.size for attachment in self.attachments)
    
    model_config = ConfigDict(
        use_enum_values=True
    )


class EmailCreateRequest(BaseModel):
    """Email creation request model."""
    
    account_id: str = Field(..., description="Associated account ID")
    message_id: str = Field(..., description="Original message ID from email provider")
    subject: str = Field(..., description="Email subject")
    sender_name: Optional[str] = Field(default=None, description="Sender display name")
    sender_email: str = Field(..., description="Sender email address")
    body_preview: Optional[str] = Field(default=None, description="Email body preview")
    sent_at: Optional[datetime] = Field(default=None, description="Email sent timestamp")
    received_at: Optional[datetime] = Field(default=None, description="Email received timestamp")
    change_type: EmailChangeType = Field(default=EmailChangeType.CREATED, description="Type of change detected")


class EmailUpdateRequest(BaseModel):
    """Email update request model."""
    
    status: Optional[EmailStatus] = Field(default=None, description="Processing status")
    is_read: Optional[bool] = Field(default=None, description="Whether email is read")
    categories: Optional[List[str]] = Field(default=None, description="Email categories")


class EmailResponse(BaseModel):
    """Email response model."""
    
    id: str = Field(..., description="Email unique identifier")
    account_id: str = Field(..., description="Associated account ID")
    message_id: str = Field(..., description="Original message ID")
    subject: str = Field(..., description="Email subject")
    sender_name: Optional[str] = Field(default=None, description="Sender display name")
    sender_email: str = Field(..., description="Sender email address")
    recipient_count: int = Field(..., description="Number of recipients")
    body_preview: Optional[str] = Field(default=None, description="Email body preview")
    priority: EmailPriority = Field(..., description="Email priority")
    has_attachments: bool = Field(..., description="Whether email has attachments")
    attachment_count: int = Field(..., description="Number of attachments")
    sent_at: Optional[datetime] = Field(default=None, description="Email sent timestamp")
    received_at: Optional[datetime] = Field(default=None, description="Email received timestamp")
    change_type: EmailChangeType = Field(..., description="Type of change detected")
    change_detected_at: Optional[datetime] = Field(default=None, description="When change was detected")
    status: EmailStatus = Field(..., description="Processing status")
    processed_at: Optional[datetime] = Field(default=None, description="Processing timestamp")
    retry_count: int = Field(..., description="Number of processing retries")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Record update timestamp")
    
    model_config = ConfigDict(
        use_enum_values=True
    )


class EmailSearchRequest(BaseModel):
    """Email search request model."""
    
    account_id: Optional[str] = Field(default=None, description="Filter by account ID")
    status: Optional[EmailStatus] = Field(default=None, description="Filter by status")
    change_type: Optional[EmailChangeType] = Field(default=None, description="Filter by change type")
    has_attachments: Optional[bool] = Field(default=None, description="Filter by attachment presence")
    keywords: Optional[List[str]] = Field(default=None, description="Search keywords")
    from_date: Optional[datetime] = Field(default=None, description="Filter from date")
    to_date: Optional[datetime] = Field(default=None, description="Filter to date")
    limit: int = Field(default=50, description="Maximum number of results")
    offset: int = Field(default=0, description="Result offset for pagination")
