"""Transmission record domain entity for tracking external API transmissions."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class TransmissionStatus(str, Enum):
    """Transmission status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TransmissionMethod(str, Enum):
    """Transmission method enumeration."""
    HTTP_POST = "http_post"
    HTTP_PUT = "http_put"
    WEBHOOK = "webhook"
    MESSAGE_QUEUE = "message_queue"


class TransmissionRecord(BaseModel):
    """Transmission record domain entity for tracking external API calls."""
    
    id: Optional[str] = Field(default=None, description="Transmission record unique identifier")
    email_id: str = Field(..., description="Associated email ID")
    account_id: str = Field(..., description="Associated account ID")
    
    # Transmission details
    method: TransmissionMethod = Field(default=TransmissionMethod.HTTP_POST, description="Transmission method")
    endpoint_url: str = Field(..., description="Target endpoint URL")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Transmission payload")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    
    # Status tracking
    status: TransmissionStatus = Field(default=TransmissionStatus.PENDING, description="Transmission status")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum number of retries")
    
    # Response tracking
    response_status_code: Optional[int] = Field(default=None, description="HTTP response status code")
    response_body: Optional[str] = Field(default=None, description="Response body")
    response_headers: Dict[str, str] = Field(default_factory=dict, description="Response headers")
    
    # Error tracking
    error_message: Optional[str] = Field(default=None, description="Error message")
    error_details: Optional[Dict[str, Any]] = Field(default=None, description="Detailed error information")
    
    # Timestamps
    created_at: Optional[datetime] = Field(default=None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Transmission start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Transmission completion timestamp")
    next_retry_at: Optional[datetime] = Field(default=None, description="Next retry timestamp")
    
    # Performance metrics
    duration_ms: Optional[int] = Field(default=None, description="Transmission duration in milliseconds")
    payload_size_bytes: Optional[int] = Field(default=None, description="Payload size in bytes")
    
    @validator("endpoint_url")
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
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def mark_success(self, response_status_code: int, response_body: str = None, 
                    response_headers: Dict[str, str] = None, duration_ms: int = None) -> None:
        """Mark transmission as successful."""
        self.status = TransmissionStatus.SUCCESS
        self.response_status_code = response_status_code
        self.response_body = response_body
        self.response_headers = response_headers or {}
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        if duration_ms:
            self.duration_ms = duration_ms
        
        # Clear error information
        self.error_message = None
        self.error_details = None
        self.next_retry_at = None
    
    def mark_failed(self, error_message: str, error_details: Dict[str, Any] = None,
                   response_status_code: int = None, response_body: str = None) -> None:
        """Mark transmission as failed."""
        self.status = TransmissionStatus.FAILED
        self.error_message = error_message
        self.error_details = error_details
        self.response_status_code = response_status_code
        self.response_body = response_body
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        # Schedule retry if applicable
        if self.should_retry():
            self.schedule_retry()
    
    def mark_cancelled(self, reason: str = None) -> None:
        """Mark transmission as cancelled."""
        self.status = TransmissionStatus.CANCELLED
        if reason:
            self.error_message = f"Cancelled: {reason}"
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.next_retry_at = None
    
    def should_retry(self) -> bool:
        """Check if transmission should be retried."""
        return (
            self.status == TransmissionStatus.FAILED and
            self.retry_count < self.max_retries
        )
    
    def schedule_retry(self, delay_seconds: int = None) -> None:
        """Schedule next retry attempt."""
        if not self.should_retry():
            return
        
        self.retry_count += 1
        
        # Calculate exponential backoff delay
        if delay_seconds is None:
            base_delay = 60  # 1 minute base delay
            delay_seconds = base_delay * (2 ** (self.retry_count - 1))
            # Cap at 30 minutes
            delay_seconds = min(delay_seconds, 1800)
        
        self.next_retry_at = datetime.utcnow() + datetime.timedelta(seconds=delay_seconds)
        self.status = TransmissionStatus.PENDING
        self.updated_at = datetime.utcnow()
    
    def reset_for_retry(self) -> None:
        """Reset transmission for manual retry."""
        self.status = TransmissionStatus.PENDING
        self.started_at = None
        self.completed_at = None
        self.next_retry_at = None
        self.error_message = None
        self.error_details = None
        self.response_status_code = None
        self.response_body = None
        self.response_headers = {}
        self.duration_ms = None
        self.updated_at = datetime.utcnow()
    
    def is_ready_for_retry(self) -> bool:
        """Check if transmission is ready for retry."""
        if not self.should_retry():
            return False
        
        if self.next_retry_at is None:
            return True
        
        return datetime.utcnow() >= self.next_retry_at
    
    def is_completed(self) -> bool:
        """Check if transmission is completed (success or final failure)."""
        return self.status in [
            TransmissionStatus.SUCCESS,
            TransmissionStatus.CANCELLED
        ] or (
            self.status == TransmissionStatus.FAILED and 
            not self.should_retry()
        )
    
    def is_successful(self) -> bool:
        """Check if transmission was successful."""
        return self.status == TransmissionStatus.SUCCESS
    
    def get_duration_seconds(self) -> Optional[float]:
        """Get transmission duration in seconds."""
        if self.duration_ms is not None:
            return self.duration_ms / 1000.0
        return None
    
    def calculate_payload_size(self) -> int:
        """Calculate payload size in bytes."""
        import json
        if self.payload:
            payload_json = json.dumps(self.payload, ensure_ascii=False)
            self.payload_size_bytes = len(payload_json.encode('utf-8'))
        else:
            self.payload_size_bytes = 0
        return self.payload_size_bytes
    
    def get_retry_delay_seconds(self) -> int:
        """Get delay until next retry in seconds."""
        if not self.next_retry_at:
            return 0
        
        delta = self.next_retry_at - datetime.utcnow()
        return max(0, int(delta.total_seconds()))
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class TransmissionCreateRequest(BaseModel):
    """Transmission record creation request model."""
    
    email_id: str = Field(..., description="Associated email ID")
    account_id: str = Field(..., description="Associated account ID")
    method: TransmissionMethod = Field(default=TransmissionMethod.HTTP_POST, description="Transmission method")
    endpoint_url: str = Field(..., description="Target endpoint URL")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Transmission payload")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    max_retries: int = Field(default=3, description="Maximum number of retries")
    
    @validator("endpoint_url")
    def validate_endpoint_url(cls, v):
        """Validate endpoint URL format."""
        import re
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, v):
            raise ValueError("Invalid URL format")
        return v


class TransmissionUpdateRequest(BaseModel):
    """Transmission record update request model."""
    
    status: Optional[TransmissionStatus] = Field(default=None, description="Transmission status")
    max_retries: Optional[int] = Field(default=None, description="Maximum number of retries")
    payload: Optional[Dict[str, Any]] = Field(default=None, description="Updated payload")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Updated headers")


class TransmissionResponse(BaseModel):
    """Transmission record response model."""
    
    id: str = Field(..., description="Transmission record unique identifier")
    email_id: str = Field(..., description="Associated email ID")
    account_id: str = Field(..., description="Associated account ID")
    method: TransmissionMethod = Field(..., description="Transmission method")
    endpoint_url: str = Field(..., description="Target endpoint URL")
    status: TransmissionStatus = Field(..., description="Transmission status")
    retry_count: int = Field(..., description="Number of retry attempts")
    max_retries: int = Field(..., description="Maximum number of retries")
    response_status_code: Optional[int] = Field(default=None, description="HTTP response status code")
    error_message: Optional[str] = Field(default=None, description="Error message")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Transmission start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Transmission completion timestamp")
    next_retry_at: Optional[datetime] = Field(default=None, description="Next retry timestamp")
    duration_ms: Optional[int] = Field(default=None, description="Transmission duration in milliseconds")
    payload_size_bytes: Optional[int] = Field(default=None, description="Payload size in bytes")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class TransmissionSearchRequest(BaseModel):
    """Transmission record search request model."""
    
    email_id: Optional[str] = Field(default=None, description="Filter by email ID")
    account_id: Optional[str] = Field(default=None, description="Filter by account ID")
    status: Optional[TransmissionStatus] = Field(default=None, description="Filter by status")
    method: Optional[TransmissionMethod] = Field(default=None, description="Filter by method")
    from_date: Optional[datetime] = Field(default=None, description="Filter from date")
    to_date: Optional[datetime] = Field(default=None, description="Filter to date")
    failed_only: bool = Field(default=False, description="Show only failed transmissions")
    pending_retry: bool = Field(default=False, description="Show only pending retries")
    limit: int = Field(default=50, description="Maximum number of results")
    offset: int = Field(default=0, description="Result offset for pagination")


class TransmissionStatsResponse(BaseModel):
    """Transmission statistics response model."""
    
    total_count: int = Field(..., description="Total number of transmissions")
    success_count: int = Field(..., description="Number of successful transmissions")
    failed_count: int = Field(..., description="Number of failed transmissions")
    pending_count: int = Field(..., description="Number of pending transmissions")
    success_rate: float = Field(..., description="Success rate percentage")
    average_duration_ms: Optional[float] = Field(default=None, description="Average transmission duration")
    total_retries: int = Field(..., description="Total number of retries")
