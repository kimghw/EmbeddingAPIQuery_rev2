"""Microsoft Graph API adapter implementation."""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urlencode

import httpx
from msal import ConfidentialClientApplication, PublicClientApplication

from core.ports.graph_api import (
    GraphAPIPort,
    GraphAPIError,
    AuthenticationError,
    TokenExpiredError,
    RateLimitError,
    EmailData,
    TokenInfo
)
from core.ports.config import ConfigPort


logger = logging.getLogger(__name__)


class GraphAPIAdapter(GraphAPIPort):
    """Microsoft Graph API adapter implementation."""
    
    def __init__(self, config: ConfigPort):
        """
        Initialize Graph API adapter.
        
        Args:
            config: Configuration port instance
        """
        self.config = config
        self._client_app = None
        self._http_client = None
        
        # Initialize MSAL application
        self._setup_msal_app()
        
        # Initialize HTTP client
        self._setup_http_client()
        
        logger.info("Graph API adapter initialized")
    
    def _setup_msal_app(self) -> None:
        """Setup MSAL (Microsoft Authentication Library) application."""
        try:
            self._client_app = ConfidentialClientApplication(
                client_id=self.config.get_client_id(),
                client_credential=self.config.get_client_secret(),
                authority=self.config.get_authority()
            )
            logger.info("MSAL application configured successfully")
        except Exception as e:
            logger.error(f"Failed to setup MSAL application: {e}")
            raise GraphAPIError(f"MSAL setup failed: {e}")
    
    def _setup_http_client(self) -> None:
        """Setup HTTP client for Graph API requests."""
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            headers={
                "User-Agent": "GraphAPIQuery/1.0",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )
    
    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._http_client:
            await self._http_client.aclose()
            logger.info("Graph API HTTP client closed")
    
    # Authentication methods
    async def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Get OAuth authorization URL."""
        try:
            scopes = self.config.get_scopes()
            redirect_uri = self.config.get_redirect_uri()
            
            auth_url = self._client_app.get_authorization_request_url(
                scopes=scopes,
                redirect_uri=redirect_uri,
                state=state
            )
            
            logger.info("Authorization URL generated successfully")
            return auth_url
            
        except Exception as e:
            logger.error(f"Failed to get authorization URL: {e}")
            raise AuthenticationError(f"Authorization URL generation failed: {e}")
    
    async def exchange_code_for_token(self, authorization_code: str) -> TokenInfo:
        """Exchange authorization code for access token."""
        try:
            scopes = self.config.get_scopes()
            redirect_uri = self.config.get_redirect_uri()
            
            result = self._client_app.acquire_token_by_authorization_code(
                code=authorization_code,
                scopes=scopes,
                redirect_uri=redirect_uri
            )
            
            if "error" in result:
                error_msg = result.get("error_description", result.get("error"))
                logger.error(f"Token exchange failed: {error_msg}")
                raise AuthenticationError(f"Token exchange failed: {error_msg}")
            
            # Calculate expiration time
            expires_in = result.get("expires_in", 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            token_info = TokenInfo(
                access_token=result["access_token"],
                refresh_token=result.get("refresh_token"),
                expires_at=expires_at,
                scope=result.get("scope", ""),
                token_type=result.get("token_type", "Bearer")
            )
            
            logger.info("Token exchange completed successfully")
            return token_info
            
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            raise AuthenticationError(f"Token exchange failed: {e}")
    
    async def refresh_token(self, refresh_token: str) -> TokenInfo:
        """Refresh access token using refresh token."""
        try:
            scopes = self.config.get_scopes()
            
            result = self._client_app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=scopes
            )
            
            if "error" in result:
                error_msg = result.get("error_description", result.get("error"))
                logger.error(f"Token refresh failed: {error_msg}")
                raise TokenExpiredError(f"Token refresh failed: {error_msg}")
            
            # Calculate expiration time
            expires_in = result.get("expires_in", 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            token_info = TokenInfo(
                access_token=result["access_token"],
                refresh_token=result.get("refresh_token", refresh_token),
                expires_at=expires_at,
                scope=result.get("scope", ""),
                token_type=result.get("token_type", "Bearer")
            )
            
            logger.info("Token refresh completed successfully")
            return token_info
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise TokenExpiredError(f"Token refresh failed: {e}")
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate access token by making a test API call."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            response = await self._http_client.get(
                f"{self.config.get_graph_api_endpoint()}/me",
                headers=headers
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return False
    
    # Email operations
    async def get_emails(
        self,
        access_token: str,
        folder: str = "inbox",
        limit: int = 100,
        skip: int = 0,
        filter_query: Optional[str] = None
    ) -> List[EmailData]:
        """Get emails from specified folder."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Build query parameters
            params = {
                "$top": min(limit, 1000),  # Graph API max is 1000
                "$skip": skip,
                "$orderby": "receivedDateTime desc"
            }
            
            if filter_query:
                params["$filter"] = filter_query
            
            # Build URL
            if folder.lower() == "inbox":
                url = f"{self.config.get_graph_api_endpoint()}/me/messages"
            else:
                url = f"{self.config.get_graph_api_endpoint()}/me/mailFolders/{folder}/messages"
            
            response = await self._http_client.get(
                url,
                headers=headers,
                params=params
            )
            
            await self._handle_response_errors(response)
            
            data = response.json()
            emails = []
            
            for item in data.get("value", []):
                email_data = self._parse_email_data(item)
                emails.append(email_data)
            
            logger.info(f"Retrieved {len(emails)} emails from {folder}")
            return emails
            
        except Exception as e:
            logger.error(f"Failed to get emails: {e}")
            raise GraphAPIError(f"Failed to get emails: {e}")
    
    async def get_email_by_id(self, access_token: str, message_id: str) -> Optional[EmailData]:
        """Get specific email by message ID."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            url = f"{self.config.get_graph_api_endpoint()}/me/messages/{message_id}"
            
            response = await self._http_client.get(url, headers=headers)
            
            if response.status_code == 404:
                return None
            
            await self._handle_response_errors(response)
            
            data = response.json()
            email_data = self._parse_email_data(data)
            
            logger.info(f"Retrieved email with ID: {message_id}")
            return email_data
            
        except Exception as e:
            logger.error(f"Failed to get email by ID {message_id}: {e}")
            raise GraphAPIError(f"Failed to get email: {e}")
    
    async def get_delta_emails(
        self,
        access_token: str,
        delta_link: Optional[str] = None,
        folder: str = "inbox"
    ) -> Tuple[List[EmailData], str]:
        """Get email changes using delta query."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            if delta_link:
                # Use existing delta link
                url = delta_link
            else:
                # Initialize delta query
                if folder.lower() == "inbox":
                    url = f"{self.config.get_graph_api_endpoint()}/me/messages/delta"
                else:
                    url = f"{self.config.get_graph_api_endpoint()}/me/mailFolders/{folder}/messages/delta"
            
            response = await self._http_client.get(url, headers=headers)
            await self._handle_response_errors(response)
            
            data = response.json()
            emails = []
            
            for item in data.get("value", []):
                # Check if this is a deletion (item will have @removed annotation)
                if "@removed" in item:
                    # Handle deleted email
                    email_data = EmailData(
                        message_id=item["id"],
                        subject="[DELETED]",
                        body="",
                        sender="",
                        recipients=[],
                        received_at=datetime.utcnow(),
                        is_deleted=True
                    )
                else:
                    email_data = self._parse_email_data(item)
                
                emails.append(email_data)
            
            # Get next delta link
            next_delta_link = data.get("@odata.deltaLink", "")
            
            logger.info(f"Retrieved {len(emails)} email changes via delta query")
            return emails, next_delta_link
            
        except Exception as e:
            logger.error(f"Failed to get delta emails: {e}")
            raise GraphAPIError(f"Failed to get delta emails: {e}")
    
    async def mark_email_as_read(self, access_token: str, message_id: str) -> bool:
        """Mark email as read."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            url = f"{self.config.get_graph_api_endpoint()}/me/messages/{message_id}"
            
            payload = {"isRead": True}
            
            response = await self._http_client.patch(
                url,
                headers=headers,
                json=payload
            )
            
            await self._handle_response_errors(response)
            
            logger.info(f"Marked email {message_id} as read")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark email as read {message_id}: {e}")
            raise GraphAPIError(f"Failed to mark email as read: {e}")
    
    async def get_user_profile(self, access_token: str) -> Dict[str, Any]:
        """Get user profile information."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            url = f"{self.config.get_graph_api_endpoint()}/me"
            
            response = await self._http_client.get(url, headers=headers)
            await self._handle_response_errors(response)
            
            data = response.json()
            
            profile = {
                "id": data.get("id"),
                "display_name": data.get("displayName"),
                "email": data.get("mail") or data.get("userPrincipalName"),
                "given_name": data.get("givenName"),
                "surname": data.get("surname"),
                "job_title": data.get("jobTitle"),
                "office_location": data.get("officeLocation")
            }
            
            logger.info(f"Retrieved user profile for: {profile.get('email')}")
            return profile
            
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            raise GraphAPIError(f"Failed to get user profile: {e}")
    
    # Helper methods
    def _parse_email_data(self, item: Dict[str, Any]) -> EmailData:
        """Parse Graph API email item to EmailData."""
        try:
            # Parse recipients
            recipients = []
            for recipient in item.get("toRecipients", []):
                email_addr = recipient.get("emailAddress", {}).get("address", "")
                if email_addr:
                    recipients.append(email_addr)
            
            # Parse CC recipients
            cc_recipients = []
            for recipient in item.get("ccRecipients", []):
                email_addr = recipient.get("emailAddress", {}).get("address", "")
                if email_addr:
                    cc_recipients.append(email_addr)
            
            # Parse BCC recipients
            bcc_recipients = []
            for recipient in item.get("bccRecipients", []):
                email_addr = recipient.get("emailAddress", {}).get("address", "")
                if email_addr:
                    bcc_recipients.append(email_addr)
            
            # Parse sender
            sender = ""
            sender_info = item.get("sender", {}).get("emailAddress", {})
            if sender_info:
                sender = sender_info.get("address", "")
            
            # Parse dates
            received_at = None
            if item.get("receivedDateTime"):
                received_at = datetime.fromisoformat(
                    item["receivedDateTime"].replace("Z", "+00:00")
                )
            
            sent_at = None
            if item.get("sentDateTime"):
                sent_at = datetime.fromisoformat(
                    item["sentDateTime"].replace("Z", "+00:00")
                )
            
            # Parse attachments
            attachments = []
            if item.get("hasAttachments", False):
                for attachment in item.get("attachments", []):
                    attachments.append({
                        "id": attachment.get("id"),
                        "name": attachment.get("name"),
                        "content_type": attachment.get("contentType"),
                        "size": attachment.get("size")
                    })
            
            # Parse body
            body = ""
            body_info = item.get("body", {})
            if body_info:
                body = body_info.get("content", "")
            
            email_data = EmailData(
                message_id=item.get("id", ""),
                conversation_id=item.get("conversationId"),
                subject=item.get("subject", ""),
                body=body,
                body_preview=item.get("bodyPreview", ""),
                sender=sender,
                recipients=recipients,
                cc_recipients=cc_recipients,
                bcc_recipients=bcc_recipients,
                received_at=received_at,
                sent_at=sent_at,
                importance=item.get("importance", "normal"),
                is_read=item.get("isRead", False),
                has_attachments=item.get("hasAttachments", False),
                attachments=attachments,
                folder=item.get("parentFolderId", "inbox")
            )
            
            return email_data
            
        except Exception as e:
            logger.error(f"Failed to parse email data: {e}")
            raise GraphAPIError(f"Failed to parse email data: {e}")
    
    async def _handle_response_errors(self, response: httpx.Response) -> None:
        """Handle HTTP response errors."""
        if response.status_code == 200:
            return
        
        try:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", "Unknown error")
            error_code = error_data.get("error", {}).get("code", "UnknownError")
        except:
            error_message = f"HTTP {response.status_code}: {response.text}"
            error_code = f"HTTP{response.status_code}"
        
        if response.status_code == 401:
            raise AuthenticationError(f"Authentication failed: {error_message}")
        elif response.status_code == 403:
            raise AuthenticationError(f"Access forbidden: {error_message}")
        elif response.status_code == 429:
            # Rate limiting
            retry_after = response.headers.get("Retry-After", "60")
            raise RateLimitError(f"Rate limit exceeded. Retry after {retry_after} seconds")
        elif response.status_code >= 500:
            raise GraphAPIError(f"Server error: {error_message}")
        else:
            raise GraphAPIError(f"API error ({error_code}): {error_message}")
    
    # Webhook operations (for future implementation)
    async def create_subscription(
        self,
        access_token: str,
        notification_url: str,
        resource: str = "me/messages",
        change_types: List[str] = None
    ) -> Dict[str, Any]:
        """Create webhook subscription for email changes."""
        if change_types is None:
            change_types = ["created", "updated", "deleted"]
        
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Subscription expires in 3 days (max for messages)
            expiration_time = datetime.utcnow() + timedelta(days=3)
            
            payload = {
                "changeType": ",".join(change_types),
                "notificationUrl": notification_url,
                "resource": resource,
                "expirationDateTime": expiration_time.isoformat() + "Z",
                "clientState": "GraphAPIQuery-Subscription"
            }
            
            url = f"{self.config.get_graph_api_endpoint()}/subscriptions"
            
            response = await self._http_client.post(
                url,
                headers=headers,
                json=payload
            )
            
            await self._handle_response_errors(response)
            
            subscription_data = response.json()
            
            logger.info(f"Created subscription: {subscription_data.get('id')}")
            return subscription_data
            
        except Exception as e:
            logger.error(f"Failed to create subscription: {e}")
            raise GraphAPIError(f"Failed to create subscription: {e}")
    
    async def delete_subscription(self, access_token: str, subscription_id: str) -> bool:
        """Delete webhook subscription."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            url = f"{self.config.get_graph_api_endpoint()}/subscriptions/{subscription_id}"
            
            response = await self._http_client.delete(url, headers=headers)
            
            if response.status_code == 404:
                logger.warning(f"Subscription {subscription_id} not found")
                return True
            
            await self._handle_response_errors(response)
            
            logger.info(f"Deleted subscription: {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete subscription {subscription_id}: {e}")
            raise GraphAPIError(f"Failed to delete subscription: {e}")
    
    # Health check
    async def health_check(self) -> bool:
        """Check if Graph API is accessible."""
        try:
            response = await self._http_client.get(
                f"{self.config.get_graph_api_endpoint()}/$metadata"
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Graph API health check failed: {e}")
            return False
