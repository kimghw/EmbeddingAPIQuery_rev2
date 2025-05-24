"""Core use cases for business logic."""

from .account_management import (
    AccountManagementUseCase,
    CreateAccountRequest,
    CreateAccountResponse,
    AccountListResponse,
    AccountDetailResponse,
)
from .email_detection import (
    EmailDetectionUseCase,
    EmailChangeDetectionRequest,
    EmailChangeDetectionResponse,
    EmailAnalysisRequest,
    EmailAnalysisResponse,
)
from .external_transmission import (
    ExternalTransmissionUseCase,
    TransmissionRequest,
    TransmissionResponse,
    BulkTransmissionRequest,
    BulkTransmissionResponse,
    RetryTransmissionRequest,
    RetryTransmissionResponse,
)

__all__ = [
    # Account Management
    "AccountManagementUseCase",
    "CreateAccountRequest",
    "CreateAccountResponse",
    "AccountListResponse",
    "AccountDetailResponse",
    
    # Email Detection
    "EmailDetectionUseCase",
    "EmailChangeDetectionRequest",
    "EmailChangeDetectionResponse",
    "EmailAnalysisRequest",
    "EmailAnalysisResponse",
    
    # External Transmission
    "ExternalTransmissionUseCase",
    "TransmissionRequest",
    "TransmissionResponse",
    "BulkTransmissionRequest",
    "BulkTransmissionResponse",
    "RetryTransmissionRequest",
    "RetryTransmissionResponse",
]
