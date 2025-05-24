"""External API port interface for sending data to external services."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

from ..domain.email import Email
from ..domain.transmission_record import TransmissionRecord


class TransmissionResult(BaseModel):
    """Result of external API transmission."""
    
    success: bool
    status_code: int = 0
    response_data: Dict[str, Any] = {}
    error_message: Optional[str] = None
    processing_time_ms: int = 0
    endpoint: str = ""
    method: str = "POST"
    timestamp: datetime = datetime.utcnow()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z"
        }


class ExternalAPIPort(ABC):
    """External API port interface for data transmission."""
    
    @abstractmethod
    async def send_email_data(
        self, 
        email_data: Dict[str, Any],
        endpoint: str = None,
        headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Send email data to external API.
        
        Args:
            email_data: Email data to send
            endpoint: Optional custom endpoint
            headers: Optional custom headers
            
        Returns:
            API response data
        """
        pass
    
    @abstractmethod
    async def send_bulk_email_data(
        self, 
        emails_data: List[Dict[str, Any]],
        endpoint: str = None,
        headers: Dict[str, str] = None,
        batch_size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Send multiple email data in bulk.
        
        Args:
            emails_data: List of email data to send
            endpoint: Optional custom endpoint
            headers: Optional custom headers
            batch_size: Number of emails per batch
            
        Returns:
            List of API response data
        """
        pass
    
    @abstractmethod
    async def send_notification(
        self, 
        notification_data: Dict[str, Any],
        notification_type: str = "email_change",
        endpoint: str = None
    ) -> Dict[str, Any]:
        """
        Send notification to external service.
        
        Args:
            notification_data: Notification payload
            notification_type: Type of notification
            endpoint: Optional custom endpoint
            
        Returns:
            API response data
        """
        pass
    
    @abstractmethod
    async def send_webhook_data(
        self, 
        webhook_data: Dict[str, Any],
        webhook_url: str,
        headers: Dict[str, str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Send data to webhook endpoint.
        
        Args:
            webhook_data: Data to send
            webhook_url: Webhook URL
            headers: Optional headers
            timeout: Request timeout in seconds
            
        Returns:
            Webhook response data
        """
        pass
    
    @abstractmethod
    async def get_api_status(self, endpoint: str = None) -> Dict[str, Any]:
        """
        Check external API status.
        
        Args:
            endpoint: Optional specific endpoint to check
            
        Returns:
            API status information
        """
        pass
    
    @abstractmethod
    async def validate_api_key(self, api_key: str = None) -> bool:
        """
        Validate API key with external service.
        
        Args:
            api_key: API key to validate (uses default if None)
            
        Returns:
            True if API key is valid
        """
        pass
    
    @abstractmethod
    async def get_rate_limit_info(self) -> Dict[str, Any]:
        """
        Get current rate limit information.
        
        Returns:
            Rate limit information (remaining, reset time, etc.)
        """
        pass
    
    @abstractmethod
    async def retry_failed_transmission(
        self, 
        transmission_record: TransmissionRecord,
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ) -> Dict[str, Any]:
        """
        Retry failed transmission with exponential backoff.
        
        Args:
            transmission_record: Failed transmission record
            max_retries: Maximum number of retries
            backoff_factor: Backoff multiplier
            
        Returns:
            Retry result data
        """
        pass
    
    @abstractmethod
    async def send_custom_payload(
        self, 
        payload: Dict[str, Any],
        endpoint: str,
        method: str = "POST",
        headers: Dict[str, str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Send custom payload to any endpoint.
        
        Args:
            payload: Data payload
            endpoint: Target endpoint URL
            method: HTTP method
            headers: Optional headers
            timeout: Request timeout
            
        Returns:
            API response data
        """
        pass
    
    @abstractmethod
    async def transform_email_for_api(self, email: Email) -> Dict[str, Any]:
        """
        Transform email domain object to API payload format.
        
        Args:
            email: Email domain object
            
        Returns:
            Transformed data for API transmission
        """
        pass
    
    @abstractmethod
    async def handle_api_error(
        self, 
        error: Exception,
        request_data: Dict[str, Any],
        endpoint: str
    ) -> Dict[str, Any]:
        """
        Handle API errors and determine retry strategy.
        
        Args:
            error: Exception that occurred
            request_data: Original request data
            endpoint: Target endpoint
            
        Returns:
            Error handling result with retry information
        """
        pass
    
    @abstractmethod
    async def log_transmission(
        self, 
        email_id: UUID,
        payload: Dict[str, Any],
        response: Dict[str, Any],
        status: str,
        error_message: str = None
    ) -> TransmissionRecord:
        """
        Log transmission attempt.
        
        Args:
            email_id: Email ID that was transmitted
            payload: Data that was sent
            response: API response
            status: Transmission status
            error_message: Error message if failed
            
        Returns:
            Created transmission record
        """
        pass


class ExternalAPIError(Exception):
    """External API specific error."""
    
    def __init__(
        self, 
        message: str, 
        status_code: int = None, 
        error_code: str = None,
        response_data: Dict[str, Any] = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.response_data = response_data or {}


class ExternalAPIAuthenticationError(ExternalAPIError):
    """External API authentication error."""
    pass


class ExternalAPIRateLimitError(ExternalAPIError):
    """External API rate limit error."""
    
    def __init__(
        self, 
        message: str, 
        retry_after: int = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ExternalAPITimeoutError(ExternalAPIError):
    """External API timeout error."""
    pass


class ExternalAPIValidationError(ExternalAPIError):
    """External API validation error."""
    pass


class ExternalAPIServerError(ExternalAPIError):
    """External API server error."""
    pass


class ExternalAPINetworkError(ExternalAPIError):
    """External API network error."""
    pass


# Aliases for backward compatibility
NetworkError = ExternalAPINetworkError
AuthenticationError = ExternalAPIAuthenticationError
RateLimitError = ExternalAPIRateLimitError
