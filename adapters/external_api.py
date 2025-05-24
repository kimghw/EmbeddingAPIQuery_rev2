"""External API adapter implementation."""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin
from uuid import UUID

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.ports.external_api import (
    ExternalAPIPort,
    ExternalAPIError,
    ExternalAPINetworkError,
    ExternalAPIAuthenticationError,
    ExternalAPIRateLimitError,
    TransmissionResult
)
from core.ports.config import ConfigPort
from core.domain.email import Email
from core.domain.transmission_record import TransmissionRecord


logger = logging.getLogger(__name__)


class ExternalAPIAdapter(ExternalAPIPort):
    """External API adapter implementation."""
    
    def __init__(self, config: ConfigPort):
        """
        Initialize External API adapter.
        
        Args:
            config: Configuration port instance
        """
        self.config = config
        self._http_client = None
        
        # Initialize HTTP client
        self._setup_http_client()
        
        logger.info("External API adapter initialized")
    
    def _setup_http_client(self) -> None:
        """Setup HTTP client for external API requests."""
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            headers={
                "User-Agent": "GraphAPIQuery/1.0",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-API-Key": self.config.get_external_api_key()
            }
        )
    
    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._http_client:
            await self._http_client.aclose()
            logger.info("External API HTTP client closed")
    
    # Abstract methods implementation
    async def send_email_data(
        self, 
        email_data: Dict[str, Any],
        endpoint: str = None,
        headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Send email data to external API."""
        try:
            # Determine endpoint
            if endpoint:
                url = urljoin(self.config.get_external_api_url(), endpoint)
            else:
                url = self.config.get_external_api_url()
            
            # Prepare headers
            request_headers = self._http_client.headers.copy()
            if headers:
                request_headers.update(headers)
            
            # Prepare payload
            payload = self._prepare_email_payload(email_data)
            
            logger.info(f"Sending email data to {url}")
            
            response = await self._http_client.post(
                url, 
                json=payload, 
                headers=request_headers
            )
            
            await self._handle_response_errors(response)
            
            # Parse response
            response_data = {}
            try:
                if response.content:
                    response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}
            
            logger.info(f"Email data sent successfully. Status: {response.status_code}")
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to send email data: {e}")
            raise ExternalAPIError(f"Failed to send email data: {e}")
    
    async def send_bulk_email_data(
        self, 
        emails_data: List[Dict[str, Any]],
        endpoint: str = None,
        headers: Dict[str, str] = None,
        batch_size: int = 10
    ) -> List[Dict[str, Any]]:
        """Send multiple email data in bulk."""
        results = []
        
        # Process in batches
        for i in range(0, len(emails_data), batch_size):
            batch = emails_data[i:i + batch_size]
            
            try:
                # Determine endpoint
                if endpoint:
                    url = urljoin(self.config.get_external_api_url(), endpoint)
                else:
                    url = urljoin(self.config.get_external_api_url(), "/bulk")
                
                # Prepare headers
                request_headers = self._http_client.headers.copy()
                if headers:
                    request_headers.update(headers)
                
                # Prepare bulk payload
                payload = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "source": "GraphAPIQuery",
                    "batch_size": len(batch),
                    "emails": [self._prepare_email_payload(email) for email in batch]
                }
                
                logger.info(f"Sending bulk email data batch {i//batch_size + 1} to {url}")
                
                response = await self._http_client.post(
                    url, 
                    json=payload, 
                    headers=request_headers
                )
                
                await self._handle_response_errors(response)
                
                # Parse response
                response_data = {}
                try:
                    if response.content:
                        response_data = response.json()
                except json.JSONDecodeError:
                    response_data = {"raw_response": response.text}
                
                results.append(response_data)
                
            except Exception as e:
                logger.error(f"Failed to send bulk email data batch {i//batch_size + 1}: {e}")
                results.append({"error": str(e), "batch_index": i//batch_size})
        
        logger.info(f"Bulk email data transmission completed. {len(results)} batches processed")
        return results
    
    async def send_notification(
        self, 
        notification_data: Dict[str, Any],
        notification_type: str = "email_change",
        endpoint: str = None
    ) -> Dict[str, Any]:
        """Send notification to external service."""
        try:
            # Determine endpoint
            if endpoint:
                url = urljoin(self.config.get_external_api_url(), endpoint)
            else:
                url = urljoin(self.config.get_external_api_url(), "/notifications")
            
            # Prepare payload
            payload = self._prepare_notification_payload(notification_data, notification_type)
            
            logger.info(f"Sending notification to {url}")
            
            response = await self._http_client.post(url, json=payload)
            
            await self._handle_response_errors(response)
            
            # Parse response
            response_data = {}
            try:
                if response.content:
                    response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}
            
            logger.info(f"Notification sent successfully. Status: {response.status_code}")
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            raise ExternalAPIError(f"Failed to send notification: {e}")
    
    async def send_webhook_data(
        self, 
        webhook_data: Dict[str, Any],
        webhook_url: str,
        headers: Dict[str, str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Send data to webhook endpoint."""
        try:
            # Prepare headers
            request_headers = {"Content-Type": "application/json"}
            if headers:
                request_headers.update(headers)
            
            logger.info(f"Sending webhook data to {webhook_url}")
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    webhook_url, 
                    json=webhook_data, 
                    headers=request_headers
                )
            
            await self._handle_response_errors(response)
            
            # Parse response
            response_data = {}
            try:
                if response.content:
                    response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}
            
            logger.info(f"Webhook data sent successfully. Status: {response.status_code}")
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to send webhook data: {e}")
            raise ExternalAPIError(f"Failed to send webhook data: {e}")
    
    async def get_api_status(self, endpoint: str = None) -> Dict[str, Any]:
        """Check external API status."""
        try:
            # Determine endpoint
            if endpoint:
                url = urljoin(self.config.get_external_api_url(), endpoint)
            else:
                url = urljoin(self.config.get_external_api_url(), "/status")
            
            response = await self._http_client.get(url)
            
            if response.status_code == 200:
                try:
                    status_data = response.json()
                    logger.info("Retrieved API status successfully")
                    return status_data
                except json.JSONDecodeError:
                    return {"status": "unknown", "raw_response": response.text}
            else:
                return {
                    "status": "error",
                    "status_code": response.status_code,
                    "message": response.text
                }
                
        except Exception as e:
            logger.error(f"Failed to get API status: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def validate_api_key(self, api_key: str = None) -> bool:
        """Validate API key with external service."""
        try:
            # Use provided API key or default from config
            key_to_validate = api_key or self.config.get_external_api_key()
            
            if not key_to_validate:
                logger.warning("No API key provided for validation")
                return False
            
            # Test API key by making a simple request
            headers = {"X-API-Key": key_to_validate}
            url = urljoin(self.config.get_external_api_url(), "/validate")
            
            response = await self._http_client.get(url, headers=headers)
            
            is_valid = response.status_code == 200
            
            if is_valid:
                logger.info("API key validation successful")
            else:
                logger.warning(f"API key validation failed: {response.status_code}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"API key validation error: {e}")
            return False
    
    async def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get current rate limit information."""
        try:
            url = urljoin(self.config.get_external_api_url(), "/rate-limit")
            
            response = await self._http_client.get(url)
            
            if response.status_code == 200:
                try:
                    rate_limit_data = response.json()
                    logger.info("Retrieved rate limit info successfully")
                    return rate_limit_data
                except json.JSONDecodeError:
                    # Parse from headers if available
                    return {
                        "remaining": response.headers.get("X-RateLimit-Remaining"),
                        "limit": response.headers.get("X-RateLimit-Limit"),
                        "reset": response.headers.get("X-RateLimit-Reset"),
                        "source": "headers"
                    }
            else:
                return {
                    "error": f"Failed to get rate limit info: {response.status_code}",
                    "remaining": None,
                    "limit": None,
                    "reset": None
                }
                
        except Exception as e:
            logger.error(f"Failed to get rate limit info: {e}")
            return {
                "error": str(e),
                "remaining": None,
                "limit": None,
                "reset": None
            }
    
    async def retry_failed_transmission(
        self, 
        transmission_record: TransmissionRecord,
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ) -> Dict[str, Any]:
        """Retry failed transmission with exponential backoff."""
        try:
            # Extract original data from transmission record
            original_payload = transmission_record.payload or {}
            endpoint = transmission_record.endpoint
            
            logger.info(f"Retrying failed transmission {transmission_record.id}")
            
            # Implement exponential backoff retry
            for attempt in range(max_retries):
                try:
                    # Calculate delay
                    delay = backoff_factor ** attempt
                    if attempt > 0:
                        import asyncio
                        await asyncio.sleep(delay)
                    
                    # Retry the transmission
                    result = await self.send_email_data(original_payload, endpoint)
                    
                    logger.info(f"Retry attempt {attempt + 1} successful for transmission {transmission_record.id}")
                    return {
                        "success": True,
                        "attempt": attempt + 1,
                        "result": result
                    }
                    
                except Exception as retry_error:
                    logger.warning(f"Retry attempt {attempt + 1} failed for transmission {transmission_record.id}: {retry_error}")
                    
                    if attempt == max_retries - 1:
                        # Last attempt failed
                        return {
                            "success": False,
                            "attempts": max_retries,
                            "final_error": str(retry_error)
                        }
            
            return {
                "success": False,
                "attempts": max_retries,
                "error": "All retry attempts exhausted"
            }
            
        except Exception as e:
            logger.error(f"Failed to retry transmission {transmission_record.id}: {e}")
            return {
                "success": False,
                "attempts": 0,
                "error": str(e)
            }
    
    async def send_custom_payload(
        self, 
        payload: Dict[str, Any],
        endpoint: str,
        method: str = "POST",
        headers: Dict[str, str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Send custom payload to any endpoint."""
        try:
            # Prepare headers
            request_headers = self._http_client.headers.copy()
            if headers:
                request_headers.update(headers)
            
            logger.info(f"Sending custom payload to {endpoint} via {method}")
            
            # Make request based on method
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method.upper() == "POST":
                    response = await client.post(endpoint, json=payload, headers=request_headers)
                elif method.upper() == "PUT":
                    response = await client.put(endpoint, json=payload, headers=request_headers)
                elif method.upper() == "PATCH":
                    response = await client.patch(endpoint, json=payload, headers=request_headers)
                elif method.upper() == "GET":
                    response = await client.get(endpoint, params=payload, headers=request_headers)
                else:
                    raise ExternalAPIError(f"Unsupported HTTP method: {method}")
            
            await self._handle_response_errors(response)
            
            # Parse response
            response_data = {}
            try:
                if response.content:
                    response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}
            
            logger.info(f"Custom payload sent successfully. Status: {response.status_code}")
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to send custom payload: {e}")
            raise ExternalAPIError(f"Failed to send custom payload: {e}")
    
    async def transform_email_for_api(self, email: Email) -> Dict[str, Any]:
        """Transform email domain object to API payload format."""
        try:
            # Transform Email domain object to dictionary
            email_data = {
                "id": str(email.id),
                "message_id": email.message_id,
                "conversation_id": email.conversation_id,
                "subject": email.subject,
                "body": email.body,
                "body_preview": email.body_preview,
                "sender": email.sender,
                "recipients": email.recipients,
                "cc_recipients": email.cc_recipients,
                "bcc_recipients": email.bcc_recipients,
                "received_at": email.received_at.isoformat() + "Z" if email.received_at else None,
                "sent_at": email.sent_at.isoformat() + "Z" if email.sent_at else None,
                "importance": email.importance,
                "is_read": email.is_read,
                "has_attachments": email.has_attachments,
                "attachments": email.attachments,
                "folder": email.folder,
                "account_id": str(email.account_id) if email.account_id else None,
                "created_at": email.created_at.isoformat() + "Z" if email.created_at else None,
                "updated_at": email.updated_at.isoformat() + "Z" if email.updated_at else None
            }
            
            # Use existing payload preparation method
            return self._prepare_email_payload(email_data)
            
        except Exception as e:
            logger.error(f"Failed to transform email for API: {e}")
            raise ExternalAPIError(f"Failed to transform email: {e}")
    
    async def handle_api_error(
        self, 
        error: Exception,
        request_data: Dict[str, Any],
        endpoint: str
    ) -> Dict[str, Any]:
        """Handle API errors and determine retry strategy."""
        try:
            error_info = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "endpoint": endpoint,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "request_data_size": len(json.dumps(request_data, default=str)),
                "retry_recommended": False,
                "retry_after_seconds": None,
                "action": "log_and_fail"
            }
            
            # Determine retry strategy based on error type
            if isinstance(error, ExternalAPIRateLimitError):
                error_info.update({
                    "retry_recommended": True,
                    "retry_after_seconds": getattr(error, 'retry_after', 60),
                    "action": "retry_with_backoff"
                })
            elif isinstance(error, ExternalAPINetworkError):
                error_info.update({
                    "retry_recommended": True,
                    "retry_after_seconds": 30,
                    "action": "retry_with_backoff"
                })
            elif isinstance(error, httpx.TimeoutException):
                error_info.update({
                    "retry_recommended": True,
                    "retry_after_seconds": 60,
                    "action": "retry_with_longer_timeout"
                })
            elif isinstance(error, ExternalAPIAuthenticationError):
                error_info.update({
                    "retry_recommended": False,
                    "action": "check_credentials"
                })
            else:
                # Generic server errors might be retryable
                if hasattr(error, 'status_code') and 500 <= error.status_code < 600:
                    error_info.update({
                        "retry_recommended": True,
                        "retry_after_seconds": 120,
                        "action": "retry_with_backoff"
                    })
            
            logger.error(f"API error handled: {error_info}")
            return error_info
            
        except Exception as e:
            logger.error(f"Failed to handle API error: {e}")
            return {
                "error_type": "ErrorHandlingFailed",
                "error_message": str(e),
                "original_error": str(error),
                "retry_recommended": False,
                "action": "manual_intervention_required"
            }
    
    async def log_transmission(
        self, 
        email_id: UUID,
        payload: Dict[str, Any],
        response: Dict[str, Any],
        status: str,
        error_message: str = None
    ) -> TransmissionRecord:
        """Log transmission attempt."""
        try:
            # Create transmission record
            transmission_record = TransmissionRecord(
                email_id=email_id,
                endpoint=self.config.get_external_api_url(),
                payload=payload,
                response=response,
                status=status,
                error_message=error_message,
                transmitted_at=datetime.utcnow(),
                retry_count=0
            )
            
            logger.info(f"Transmission logged: {transmission_record.id} for email {email_id}")
            return transmission_record
            
        except Exception as e:
            logger.error(f"Failed to log transmission: {e}")
            # Return a minimal record even if logging fails
            return TransmissionRecord(
                email_id=email_id,
                endpoint=self.config.get_external_api_url(),
                status="logging_failed",
                error_message=f"Failed to log transmission: {e}",
                transmitted_at=datetime.utcnow(),
                retry_count=0
            )
    
    # Helper methods
    def _prepare_email_payload(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare email data payload for external API."""
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "GraphAPIQuery",
            "event_type": "email_received",
            "data": {
                "message_id": email_data.get("message_id"),
                "conversation_id": email_data.get("conversation_id"),
                "subject": email_data.get("subject", ""),
                "sender": email_data.get("sender", ""),
                "recipients": email_data.get("recipients", []),
                "cc_recipients": email_data.get("cc_recipients", []),
                "bcc_recipients": email_data.get("bcc_recipients", []),
                "received_at": email_data.get("received_at"),
                "sent_at": email_data.get("sent_at"),
                "body_preview": email_data.get("body_preview", ""),
                "importance": email_data.get("importance", "normal"),
                "is_read": email_data.get("is_read", False),
                "has_attachments": email_data.get("has_attachments", False),
                "folder": email_data.get("folder", "inbox"),
                "processing_status": email_data.get("processing_status", "pending")
            },
            "metadata": {
                "account_id": email_data.get("account_id"),
                "user_id": email_data.get("user_id"),
                "processed_at": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        # Add attachments info if present
        if email_data.get("attachments"):
            payload["data"]["attachments"] = [
                {
                    "name": att.get("name"),
                    "content_type": att.get("content_type"),
                    "size": att.get("size")
                }
                for att in email_data["attachments"]
            ]
        
        # Add custom metadata if present
        if email_data.get("metadata"):
            payload["metadata"].update(email_data["metadata"])
        
        return payload
    
    def _prepare_notification_payload(self, notification_data: Dict[str, Any], notification_type: str) -> Dict[str, Any]:
        """Prepare notification payload for external API."""
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "GraphAPIQuery",
            "notification_type": notification_type,
            "title": notification_data.get("title", ""),
            "message": notification_data.get("message", ""),
            "data": notification_data.get("data", {}),
            "metadata": {
                "user_id": notification_data.get("user_id"),
                "account_id": notification_data.get("account_id"),
                "severity": notification_data.get("severity", "info")
            }
        }
        
        return payload
    
    async def _handle_response_errors(self, response: httpx.Response) -> None:
        """Handle HTTP response errors."""
        if response.status_code < 400:
            return
        
        try:
            error_data = response.json()
            error_message = error_data.get("message", error_data.get("error", "Unknown error"))
        except json.JSONDecodeError:
            error_message = f"HTTP {response.status_code}: {response.text}"
        
        if response.status_code == 401:
            raise ExternalAPIAuthenticationError(f"Authentication failed: {error_message}")
        elif response.status_code == 403:
            raise ExternalAPIAuthenticationError(f"Access forbidden: {error_message}")
        elif response.status_code == 429:
            # Rate limiting
            retry_after = response.headers.get("Retry-After", "60")
            raise ExternalAPIRateLimitError(
                f"Rate limit exceeded. Retry after {retry_after} seconds",
                retry_after=int(retry_after)
            )
        elif response.status_code >= 500:
            raise ExternalAPIError(f"Server error: {error_message}")
        else:
            raise ExternalAPIError(f"API error ({response.status_code}): {error_message}")
    
    # Health check and testing methods
    async def health_check(self, endpoint: Optional[str] = None) -> bool:
        """Check if external API is accessible."""
        try:
            # Determine endpoint
            if endpoint:
                url = urljoin(self.config.get_external_api_url(), endpoint)
            else:
                url = urljoin(self.config.get_external_api_url(), "/health")
            
            response = await self._http_client.get(url)
            
            is_healthy = response.status_code in [200, 204]
            
            if is_healthy:
                logger.info(f"External API health check passed: {response.status_code}")
            else:
                logger.warning(f"External API health check failed: {response.status_code}")
            
            return is_healthy
            
        except Exception as e:
            logger.error(f"External API health check failed: {e}")
            return False
