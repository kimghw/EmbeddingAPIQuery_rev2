"""External API adapter implementation."""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.ports.external_api import (
    ExternalAPIPort,
    ExternalAPIError,
    NetworkError,
    AuthenticationError,
    RateLimitError,
    TransmissionResult
)
from core.ports.config import ConfigPort


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
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((NetworkError, RateLimitError))
    )
    async def send_email_data(
        self,
        email_data: Dict[str, Any],
        endpoint: Optional[str] = None,
        method: str = "POST"
    ) -> TransmissionResult:
        """
        Send email data to external API.
        
        Args:
            email_data: Email data to send
            endpoint: Optional specific endpoint (defaults to config)
            method: HTTP method to use
            
        Returns:
            TransmissionResult with response details
        """
        start_time = datetime.utcnow()
        
        try:
            # Determine endpoint
            if endpoint:
                url = urljoin(self.config.get_external_api_url(), endpoint)
            else:
                url = self.config.get_external_api_url()
            
            # Prepare payload
            payload = self._prepare_email_payload(email_data)
            
            logger.info(f"Sending email data to {url} via {method}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2, default=str)}")
            
            # Make request
            if method.upper() == "POST":
                response = await self._http_client.post(url, json=payload)
            elif method.upper() == "PUT":
                response = await self._http_client.put(url, json=payload)
            elif method.upper() == "PATCH":
                response = await self._http_client.patch(url, json=payload)
            else:
                raise ExternalAPIError(f"Unsupported HTTP method: {method}")
            
            # Calculate processing time
            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Handle response
            await self._handle_response_errors(response)
            
            # Parse response data
            response_data = {}
            try:
                if response.content:
                    response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}
            
            result = TransmissionResult(
                success=True,
                status_code=response.status_code,
                response_data=response_data,
                processing_time_ms=processing_time_ms,
                endpoint=url,
                method=method.upper()
            )
            
            logger.info(f"Email data sent successfully. Status: {response.status_code}, Time: {processing_time_ms}ms")
            return result
            
        except (httpx.RequestError, httpx.TimeoutException) as e:
            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            logger.error(f"Network error sending email data: {e}")
            raise NetworkError(f"Network error: {e}")
            
        except Exception as e:
            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            logger.error(f"Failed to send email data: {e}")
            
            result = TransmissionResult(
                success=False,
                status_code=0,
                error_message=str(e),
                processing_time_ms=processing_time_ms,
                endpoint=url if 'url' in locals() else "",
                method=method.upper()
            )
            
            return result
    
    async def send_batch_email_data(
        self,
        email_data_list: List[Dict[str, Any]],
        endpoint: Optional[str] = None,
        method: str = "POST"
    ) -> List[TransmissionResult]:
        """
        Send multiple email data items to external API.
        
        Args:
            email_data_list: List of email data to send
            endpoint: Optional specific endpoint
            method: HTTP method to use
            
        Returns:
            List of TransmissionResult objects
        """
        results = []
        
        for i, email_data in enumerate(email_data_list):
            try:
                result = await self.send_email_data(email_data, endpoint, method)
                results.append(result)
                
                logger.info(f"Batch item {i+1}/{len(email_data_list)} sent successfully")
                
            except Exception as e:
                logger.error(f"Failed to send batch item {i+1}/{len(email_data_list)}: {e}")
                
                result = TransmissionResult(
                    success=False,
                    status_code=0,
                    error_message=str(e),
                    processing_time_ms=0,
                    endpoint=endpoint or self.config.get_external_api_url(),
                    method=method.upper()
                )
                results.append(result)
        
        logger.info(f"Batch transmission completed. {sum(1 for r in results if r.success)}/{len(results)} successful")
        return results
    
    async def send_notification(
        self,
        notification_data: Dict[str, Any],
        endpoint: Optional[str] = None
    ) -> TransmissionResult:
        """
        Send notification to external API.
        
        Args:
            notification_data: Notification data to send
            endpoint: Optional specific endpoint
            
        Returns:
            TransmissionResult with response details
        """
        start_time = datetime.utcnow()
        
        try:
            # Determine endpoint
            if endpoint:
                url = urljoin(self.config.get_external_api_url(), endpoint)
            else:
                # Use default notification endpoint
                url = urljoin(self.config.get_external_api_url(), "/notifications")
            
            # Prepare payload
            payload = self._prepare_notification_payload(notification_data)
            
            logger.info(f"Sending notification to {url}")
            
            response = await self._http_client.post(url, json=payload)
            
            # Calculate processing time
            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Handle response
            await self._handle_response_errors(response)
            
            # Parse response data
            response_data = {}
            try:
                if response.content:
                    response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}
            
            result = TransmissionResult(
                success=True,
                status_code=response.status_code,
                response_data=response_data,
                processing_time_ms=processing_time_ms,
                endpoint=url,
                method="POST"
            )
            
            logger.info(f"Notification sent successfully. Status: {response.status_code}")
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            logger.error(f"Failed to send notification: {e}")
            
            result = TransmissionResult(
                success=False,
                status_code=0,
                error_message=str(e),
                processing_time_ms=processing_time_ms,
                endpoint=url if 'url' in locals() else "",
                method="POST"
            )
            
            return result
    
    async def health_check(self, endpoint: Optional[str] = None) -> bool:
        """
        Check if external API is accessible.
        
        Args:
            endpoint: Optional specific health check endpoint
            
        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Determine endpoint
            if endpoint:
                url = urljoin(self.config.get_external_api_url(), endpoint)
            else:
                # Use default health check endpoint
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
    
    async def get_api_status(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """
        Get API status information.
        
        Args:
            endpoint: Optional specific status endpoint
            
        Returns:
            Dictionary with API status information
        """
        try:
            # Determine endpoint
            if endpoint:
                url = urljoin(self.config.get_external_api_url(), endpoint)
            else:
                # Use default status endpoint
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
    
    # Helper methods
    def _prepare_email_payload(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare email data payload for external API.
        
        Args:
            email_data: Raw email data
            
        Returns:
            Formatted payload for external API
        """
        # Standard payload format
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
    
    def _prepare_notification_payload(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare notification payload for external API.
        
        Args:
            notification_data: Raw notification data
            
        Returns:
            Formatted notification payload
        """
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "GraphAPIQuery",
            "notification_type": notification_data.get("type", "info"),
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
            raise AuthenticationError(f"Authentication failed: {error_message}")
        elif response.status_code == 403:
            raise AuthenticationError(f"Access forbidden: {error_message}")
        elif response.status_code == 429:
            # Rate limiting
            retry_after = response.headers.get("Retry-After", "60")
            raise RateLimitError(f"Rate limit exceeded. Retry after {retry_after} seconds")
        elif response.status_code >= 500:
            raise ExternalAPIError(f"Server error: {error_message}")
        else:
            raise ExternalAPIError(f"API error ({response.status_code}): {error_message}")
    
    # Configuration and testing methods
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to external API.
        
        Returns:
            Dictionary with connection test results
        """
        test_results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "api_url": self.config.get_external_api_url(),
            "tests": {}
        }
        
        # Test health check
        try:
            health_check_result = await self.health_check()
            test_results["tests"]["health_check"] = {
                "passed": health_check_result,
                "message": "Health check passed" if health_check_result else "Health check failed"
            }
        except Exception as e:
            test_results["tests"]["health_check"] = {
                "passed": False,
                "message": f"Health check error: {e}"
            }
        
        # Test status endpoint
        try:
            status_data = await self.get_api_status()
            test_results["tests"]["status_check"] = {
                "passed": "error" not in status_data,
                "message": "Status check passed" if "error" not in status_data else f"Status check failed: {status_data.get('error')}",
                "data": status_data
            }
        except Exception as e:
            test_results["tests"]["status_check"] = {
                "passed": False,
                "message": f"Status check error: {e}"
            }
        
        # Test authentication (send a minimal test payload)
        try:
            test_payload = {
                "message_id": "test-message-id",
                "subject": "Connection Test",
                "sender": "test@example.com",
                "recipients": ["recipient@example.com"],
                "received_at": datetime.utcnow().isoformat() + "Z",
                "is_test": True
            }
            
            # Try to send test data (this might fail if the API doesn't accept test data)
            result = await self.send_email_data(test_payload, endpoint="/test")
            test_results["tests"]["authentication"] = {
                "passed": result.success,
                "message": "Authentication test passed" if result.success else f"Authentication test failed: {result.error_message}"
            }
        except Exception as e:
            test_results["tests"]["authentication"] = {
                "passed": False,
                "message": f"Authentication test error: {e}"
            }
        
        # Overall result
        all_tests_passed = all(test["passed"] for test in test_results["tests"].values())
        test_results["overall_result"] = {
            "passed": all_tests_passed,
            "message": "All tests passed" if all_tests_passed else "Some tests failed"
        }
        
        logger.info(f"Connection test completed. Overall result: {'PASS' if all_tests_passed else 'FAIL'}")
        return test_results
    
    def get_configuration_info(self) -> Dict[str, Any]:
        """
        Get configuration information (with sensitive data masked).
        
        Returns:
            Dictionary with configuration details
        """
        return {
            "api_url": self.config.get_external_api_url(),
            "api_key_configured": bool(self.config.get_external_api_key()),
            "timeout": 30.0,
            "max_retries": 3,
            "retry_strategy": "exponential_backoff"
        }
