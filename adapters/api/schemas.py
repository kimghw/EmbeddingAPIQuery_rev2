"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr


# Base schemas
class BaseResponse(BaseModel):
    """Base response schema."""
    success: bool
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseResponse):
    """Error response schema."""
    success: bool = False
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# User schemas
class UserBase(BaseModel):
    """Base user schema."""
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    """User creation schema."""
    password: str = Field(..., min_length=8)


class UserResponse(UserBase):
    """User response schema."""
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserListResponse(BaseResponse):
    """User list response schema."""
    users: List[UserResponse]
    total: int


# Account schemas
class AccountBase(BaseModel):
    """Base account schema."""
    email: EmailStr
    display_name: Optional[str] = None


class AccountCreate(AccountBase):
    """Account creation schema."""
    username: str = Field(..., min_length=3, max_length=50)


class AccountUpdate(BaseModel):
    """Account update schema."""
    display_name: Optional[str] = None
    is_active: Optional[bool] = None


class AccountResponse(AccountBase):
    """Account response schema."""
    id: UUID
    user_id: UUID
    is_active: bool
    is_authorized: bool
    last_sync_at: Optional[datetime] = None
    delta_link: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AccountListResponse(BaseResponse):
    """Account list response schema."""
    accounts: List[AccountResponse]
    total: int


class AccountCreateResponse(BaseResponse):
    """Account creation response schema."""
    account: AccountResponse


class AuthorizationUrlResponse(BaseResponse):
    """Authorization URL response schema."""
    authorization_url: str
    state: Optional[str] = None


class AuthorizeAccountRequest(BaseModel):
    """Account authorization request schema."""
    authorization_code: str = Field(..., min_length=1)


class AuthorizeAccountResponse(BaseResponse):
    """Account authorization response schema."""
    account: AccountResponse


# Email schemas
class EmailBase(BaseModel):
    """Base email schema."""
    subject: str
    sender: str
    recipients: List[str] = Field(default_factory=list)
    cc_recipients: List[str] = Field(default_factory=list)
    bcc_recipients: List[str] = Field(default_factory=list)


class EmailResponse(EmailBase):
    """Email response schema."""
    id: UUID
    account_id: UUID
    message_id: str
    conversation_id: Optional[str] = None
    body_preview: Optional[str] = None
    received_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    importance: str = "normal"
    is_read: bool = False
    has_attachments: bool = False
    folder: str = "inbox"
    processing_status: str = "pending"
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmailListResponse(BaseResponse):
    """Email list response schema."""
    emails: List[EmailResponse]
    total: int


class EmailDetectionRequest(BaseModel):
    """Email detection request schema."""
    account_id: Optional[UUID] = None
    limit: int = Field(default=100, ge=1, le=1000)
    use_delta: bool = True


class EmailDetectionResponse(BaseResponse):
    """Email detection response schema."""
    emails: List[EmailResponse]
    new_count: int
    updated_count: int
    total_processed: int


# Transmission schemas
class TransmissionRecordResponse(BaseModel):
    """Transmission record response schema."""
    id: UUID
    email_id: UUID
    status: str
    endpoint: Optional[str] = None
    method: str = "POST"
    response_status_code: Optional[int] = None
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    processing_time_ms: Optional[int] = None
    transmitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TransmissionListResponse(BaseResponse):
    """Transmission list response schema."""
    transmissions: List[TransmissionRecordResponse]
    total: int


class TransmissionRequest(BaseModel):
    """Transmission request schema."""
    status: str = "pending"
    limit: int = Field(default=50, ge=1, le=500)
    endpoint: Optional[str] = None


class TransmissionResponse(BaseResponse):
    """Transmission response schema."""
    transmission_records: List[TransmissionRecordResponse]
    total_processed: int
    successful_count: int
    failed_count: int


class TransmissionSummaryResponse(BaseResponse):
    """Transmission summary response schema."""
    summary: Dict[str, int]


class RetryTransmissionRequest(BaseModel):
    """Retry transmission request schema."""
    limit: int = Field(default=20, ge=1, le=100)


# Health check schemas
class HealthCheckResponse(BaseModel):
    """Health check response schema."""
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, bool]
    version: str = "1.0.0"


class DatabaseHealthResponse(BaseModel):
    """Database health response schema."""
    status: str
    connection: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Configuration schemas
class ConfigurationResponse(BaseModel):
    """Configuration response schema."""
    environment: str
    database_url_masked: str
    graph_api_endpoint: str
    external_api_url: str
    client_id_masked: str
    client_secret_configured: bool
    external_api_key_configured: bool


class ConnectionTestResponse(BaseModel):
    """Connection test response schema."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tests: Dict[str, Dict[str, Any]]
    overall_result: Dict[str, Any]


# Webhook schemas (for future implementation)
class WebhookNotification(BaseModel):
    """Webhook notification schema."""
    subscription_id: str
    client_state: Optional[str] = None
    expiration_date_time: datetime
    resource: str
    resource_data: Dict[str, Any]
    change_type: str


class WebhookValidationRequest(BaseModel):
    """Webhook validation request schema."""
    validation_token: str


class WebhookValidationResponse(BaseModel):
    """Webhook validation response schema."""
    validation_token: str


# Pagination schemas
class PaginationParams(BaseModel):
    """Pagination parameters schema."""
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    """Paginated response schema."""
    page: int
    size: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool


# Filter schemas
class EmailFilterParams(BaseModel):
    """Email filter parameters schema."""
    account_id: Optional[UUID] = None
    status: Optional[str] = None
    sender: Optional[str] = None
    subject_contains: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    has_attachments: Optional[bool] = None
    is_read: Optional[bool] = None


class TransmissionFilterParams(BaseModel):
    """Transmission filter parameters schema."""
    email_id: Optional[UUID] = None
    status: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_retry_count: Optional[int] = None
    max_retry_count: Optional[int] = None


# Batch operation schemas
class BatchOperationRequest(BaseModel):
    """Batch operation request schema."""
    ids: List[UUID] = Field(..., min_items=1, max_items=100)


class BatchOperationResponse(BaseResponse):
    """Batch operation response schema."""
    processed: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)


# Statistics schemas
class EmailStatistics(BaseModel):
    """Email statistics schema."""
    total_emails: int
    by_status: Dict[str, int]
    by_account: Dict[str, int]
    recent_activity: Dict[str, int]


class TransmissionStatistics(BaseModel):
    """Transmission statistics schema."""
    total_transmissions: int
    by_status: Dict[str, int]
    success_rate: float
    average_processing_time: Optional[float] = None
    recent_activity: Dict[str, int]


class SystemStatistics(BaseModel):
    """System statistics schema."""
    emails: EmailStatistics
    transmissions: TransmissionStatistics
    accounts: Dict[str, int]
    uptime: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SystemStatisticsResponse(BaseResponse):
    """System statistics response schema."""
    statistics: SystemStatistics
