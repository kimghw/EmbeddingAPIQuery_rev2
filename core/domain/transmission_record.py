"""Transmission record domain entity."""

from datetime import datetime, UTC
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class TransmissionStatus(str, Enum):
    """Transmission status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class TransmissionMethod(str, Enum):
    """Transmission method enumeration."""
    HTTP_POST = "http_post"
    HTTP_PUT = "http_put"
    WEBHOOK = "webhook"
    EMAIL = "email"
    FTP = "ftp"
    SFTP = "sftp"


class TransmissionPriority(str, Enum):
    """Transmission priority enumeration."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TransmissionRecord(BaseModel):
    """Transmission record domain entity for tracking external data transmissions."""
    
    id: Optional[str] = Field(default=None, description="Transmission record unique identifier")
    account_id: str = Field(..., description="Associated account ID")
    email_id: Optional[str] = Field(default=None, description="Associated email ID")
    
    # Transmission details
    method: TransmissionMethod = Field(..., description="Transmission method")
    endpoint_url: str = Field(..., description="Target endpoint URL")
    priority: TransmissionPriority = Field(default=TransmissionPriority.NORMAL, description="Transmission priority")
    
    # Request data
    request_headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    request_body: Optional[str] = Field(default=None, description="Request body content")
    request_method: str = Field(default="POST", description="HTTP method")
    content_type: str = Field(default="application/json", description="Content type")
    
    # Response data
    response_status_code: Optional[int] = Field(default=None, description="HTTP response status code")
    response_headers: Dict[str, str] = Field(default_factory=dict, description="Response headers")
    response_body: Optional[str] = Field(default=None, description="Response body content")
    response_time_ms: Optional[int] = Field(default=None, description="Response time in milliseconds")
    
    # Status tracking
    status: TransmissionStatus = Field(default=TransmissionStatus.PENDING, description="Transmission status")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    
    # Timestamps
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    scheduled_at: Optional[datetime] = Field(default=None, description="Scheduled transmission time")
    started_at: Optional[datetime] = Field(default=None, description="Transmission start time")
    completed_at: Optional[datetime] = Field(default=None, description="Transmission completion time")
    
    # Error handling
    error_message: Optional[str] = Field(default=None, description="Error message")
    error_code: Optional[str] = Field(default=None, description="Error code")
    last_error_at: Optional[datetime] = Field(default=None, description="Last error timestamp")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Transmission tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator("endpoint_url")
    @classmethod
    def validate_endpoint_url(cls, v):
        """Validate endpoint URL format."""
        import re
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, v):
            raise ValueError("Invalid URL format")
        return v
    
    def start_transmission(self) -> None:
        """Mark transmission as started."""
        self.status = TransmissionStatus.IN_PROGRESS
        self.started_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
    
    def mark_success(self, response_status: int, response_body: str = None, 
                    response_headers: Dict[str, str] = None, response_time_ms: int = None) -> None:
        """Mark transmission as successful."""
        self.status = TransmissionStatus.SUCCESS
        self.response_status_code = response_status
        if response_body:
            self.response_body = response_body
        if response_headers:
            self.response_headers = response_headers
        if response_time_ms:
            self.response_time_ms = response_time_ms
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        self.error_message = None
        self.error_code = None
    
    def mark_failed(self, error_message: str, error_code: str = None, 
                   response_status: int = None, response_body: str = None) -> None:
        """Mark transmission as failed."""
        self.status = TransmissionStatus.FAILED
        self.error_message = error_message
        self.error_code = error_code
        self.last_error_at = datetime.now(UTC)
        if response_status:
            self.response_status_code = response_status
        if response_body:
            self.response_body = response_body
        self.updated_at = datetime.now(UTC)
    
    def increment_retry(self) -> None:
        """Increment retry count and mark for retry."""
        self.retry_count += 1
        if self.retry_count <= self.max_retries:
            self.status = TransmissionStatus.RETRYING
        else:
            self.status = TransmissionStatus.FAILED
        self.updated_at = datetime.now(UTC)
    
    def cancel(self, reason: str = None) -> None:
        """Cancel the transmission."""
        self.status = TransmissionStatus.CANCELLED
        if reason:
            self.error_message = f"Cancelled: {reason}"
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
    
    def reset_for_retry(self) -> None:
        """Reset transmission for retry."""
        self.status = TransmissionStatus.PENDING
        self.started_at = None
        self.completed_at = None
        self.response_status_code = None
        self.response_body = None
        self.response_headers = {}
        self.response_time_ms = None
        self.updated_at = datetime.now(UTC)
    
    def should_retry(self) -> bool:
        """Check if transmission should be retried."""
        return (
            self.status in [TransmissionStatus.FAILED, TransmissionStatus.RETRYING] and
            self.retry_count < self.max_retries
        )
    
    def is_completed(self) -> bool:
        """Check if transmission is completed (success or final failure)."""
        return self.status in [
            TransmissionStatus.SUCCESS,
            TransmissionStatus.FAILED,
            TransmissionStatus.CANCELLED
        ] and (self.status != TransmissionStatus.FAILED or self.retry_count >= self.max_retries)
    
    def is_pending(self) -> bool:
        """Check if transmission is pending."""
        return self.status == TransmissionStatus.PENDING
    
    def is_in_progress(self) -> bool:
        """Check if transmission is in progress."""
        return self.status == TransmissionStatus.IN_PROGRESS
    
    def is_successful(self) -> bool:
        """Check if transmission was successful."""
        return self.status == TransmissionStatus.SUCCESS
    
    def is_failed(self) -> bool:
        """Check if transmission failed."""
        return self.status == TransmissionStatus.FAILED
    
    def get_duration_ms(self) -> Optional[int]:
        """Get transmission duration in milliseconds."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the transmission."""
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now(UTC)
    
    def remove_tag(self, tag: str) -> bool:
        """Remove a tag from the transmission."""
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.now(UTC)
            return True
        return False
    
    def has_tag(self, tag: str) -> bool:
        """Check if transmission has a specific tag."""
        return tag in self.tags
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value."""
        self.metadata[key] = value
        self.updated_at = datetime.now(UTC)
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        return self.metadata.get(key, default)
    
    model_config = ConfigDict(
        use_enum_values=True
    )


class TransmissionCreateRequest(BaseModel):
    """Transmission creation request model."""
    
    account_id: str = Field(..., description="Associated account ID")
    email_id: Optional[str] = Field(default=None, description="Associated email ID")
    method: TransmissionMethod = Field(..., description="Transmission method")
    endpoint_url: str = Field(..., description="Target endpoint URL")
    priority: TransmissionPriority = Field(default=TransmissionPriority.NORMAL, description="Transmission priority")
    request_headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    request_body: Optional[str] = Field(default=None, description="Request body content")
    request_method: str = Field(default="POST", description="HTTP method")
    content_type: str = Field(default="application/json", description="Content type")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    scheduled_at: Optional[datetime] = Field(default=None, description="Scheduled transmission time")
    tags: List[str] = Field(default_factory=list, description="Transmission tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator("endpoint_url")
    @classmethod
    def validate_endpoint_url(cls, v):
        """Validate endpoint URL format."""
        import re
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, v):
            raise ValueError("Invalid URL format")
        return v


class TransmissionUpdateRequest(BaseModel):
    """Transmission update request model."""
    
    status: Optional[TransmissionStatus] = Field(default=None, description="Transmission status")
    priority: Optional[TransmissionPriority] = Field(default=None, description="Transmission priority")
    scheduled_at: Optional[datetime] = Field(default=None, description="Scheduled transmission time")
    max_retries: Optional[int] = Field(default=None, description="Maximum retry attempts")
    tags: Optional[List[str]] = Field(default=None, description="Transmission tags")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class TransmissionResponse(BaseModel):
    """Transmission response model."""
    
    id: str = Field(..., description="Transmission record unique identifier")
    account_id: str = Field(..., description="Associated account ID")
    email_id: Optional[str] = Field(default=None, description="Associated email ID")
    method: TransmissionMethod = Field(..., description="Transmission method")
    endpoint_url: str = Field(..., description="Target endpoint URL")
    priority: TransmissionPriority = Field(..., description="Transmission priority")
    status: TransmissionStatus = Field(..., description="Transmission status")
    retry_count: int = Field(..., description="Number of retry attempts")
    max_retries: int = Field(..., description="Maximum retry attempts")
    response_status_code: Optional[int] = Field(default=None, description="HTTP response status code")
    response_time_ms: Optional[int] = Field(default=None, description="Response time in milliseconds")
    duration_ms: Optional[int] = Field(default=None, description="Total transmission duration")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    scheduled_at: Optional[datetime] = Field(default=None, description="Scheduled transmission time")
    started_at: Optional[datetime] = Field(default=None, description="Transmission start time")
    completed_at: Optional[datetime] = Field(default=None, description="Transmission completion time")
    error_message: Optional[str] = Field(default=None, description="Error message")
    error_code: Optional[str] = Field(default=None, description="Error code")
    tags: List[str] = Field(..., description="Transmission tags")
    
    model_config = ConfigDict(
        use_enum_values=True
    )


class TransmissionSearchRequest(BaseModel):
    """Transmission search request model."""
    
    account_id: Optional[str] = Field(default=None, description="Filter by account ID")
    email_id: Optional[str] = Field(default=None, description="Filter by email ID")
    status: Optional[TransmissionStatus] = Field(default=None, description="Filter by status")
    method: Optional[TransmissionMethod] = Field(default=None, description="Filter by method")
    priority: Optional[TransmissionPriority] = Field(default=None, description="Filter by priority")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")
    from_date: Optional[datetime] = Field(default=None, description="Filter from date")
    to_date: Optional[datetime] = Field(default=None, description="Filter to date")
    limit: int = Field(default=50, description="Maximum number of results")
    offset: int = Field(default=0, description="Result offset for pagination")


class TransmissionSummary(BaseModel):
    """Transmission summary statistics."""
    
    total_count: int = Field(..., description="Total transmission count")
    pending_count: int = Field(..., description="Pending transmission count")
    in_progress_count: int = Field(..., description="In progress transmission count")
    success_count: int = Field(..., description="Successful transmission count")
    failed_count: int = Field(..., description="Failed transmission count")
    cancelled_count: int = Field(..., description="Cancelled transmission count")
    success_rate: float = Field(..., description="Success rate percentage")
    average_response_time_ms: Optional[float] = Field(default=None, description="Average response time")
    last_transmission_at: Optional[datetime] = Field(default=None, description="Last transmission timestamp")
    
    model_config = ConfigDict(
        use_enum_values=True
    )
