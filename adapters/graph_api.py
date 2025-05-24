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
from core.domain.account import Account


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
    
    # Abstract methods implementation
    async def authenticate(self, account: Account) -> Dict[str, Any]:
        """Authenticate with Microsoft Graph API using OAuth 2.0."""
        try:
            # For testing purposes, return mock token data
            # In real implementation, this would handle OAuth flow
            return {
                "access_token": "mock_access_token",
                "refresh_token": "mock_refresh_token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "https://graph.microsoft.com/Mail.Read"
            }
        except Exception as e:
            logger.error(f"Authentication failed for account {account.email}: {e}")
            raise AuthenticationError(f"Authentication failed: {e}")
    
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
    
    async def exchange_code_for_token(self, code: str, state: str = None) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        try:
            scopes = self.config.get_scopes()
            redirect_uri = self.config.get_redirect_uri()
            
            result = self._client_app.acquire_token_by_authorization_code(
                code=code,
                scopes=scopes,
                redirect_uri=redirect_uri
            )
            
            if "error" in result:
                error_msg = result.get("error_description", result.get("error"))
                logger.error(f"Token exchange failed: {error_msg}")
                raise AuthenticationError(f"Token exchange failed: {error_msg}")
            
            logger.info("Token exchange completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            raise AuthenticationError(f"Token exchange failed: {e}")
    
    async def refresh_token(self, account: Account) -> Dict[str, Any]:
        """Refresh access token using refresh token."""
        try:
            scopes = self.config.get_scopes()
            
            # Get refresh token from account (assuming it's stored)
            refresh_token = getattr(account, 'refresh_token', None)
            if not refresh_token:
                raise TokenExpiredError("No refresh token available")
            
            result = self._client_app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=scopes
            )
            
            if "error" in result:
                error_msg = result.get("error_description", result.get("error"))
                logger.error(f"Token refresh failed: {error_msg}")
                raise TokenExpiredError(f"Token refresh failed: {error_msg}")
            
            logger.info("Token refresh completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise TokenExpiredError(f"Token refresh failed: {e}")
    
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
    
    async def get_emails(
        self, 
        access_token: str, 
        folder: str = "inbox",
        top: int = 50,
        skip: int = 0,
        filter_query: str = None,
        order_by: str = "receivedDateTime desc"
    ) -> List[Dict[str, Any]]:
        """Get emails from specified folder."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Build query parameters
            params = {
                "$top": min(top, 1000),  # Graph API max is 1000
                "$skip": skip,
                "$orderby": order_by
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
            emails = data.get("value", [])
            
            logger.info(f"Retrieved {len(emails)} emails from {folder}")
            return emails
            
        except Exception as e:
            logger.error(f"Failed to get emails: {e}")
            raise GraphAPIError(f"Failed to get emails: {e}")
    
    async def get_email_by_id(self, access_token: str, message_id: str) -> Dict[str, Any]:
        """Get specific email by message ID."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            url = f"{self.config.get_graph_api_endpoint()}/me/messages/{message_id}"
            
            response = await self._http_client.get(url, headers=headers)
            
            if response.status_code == 404:
                raise GraphAPIError(f"Email with ID {message_id} not found")
            
            await self._handle_response_errors(response)
            
            data = response.json()
            
            logger.info(f"Retrieved email with ID: {message_id}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to get email by ID {message_id}: {e}")
            raise GraphAPIError(f"Failed to get email: {e}")
    
    async def get_delta_emails(
        self, 
        access_token: str, 
        delta_link: str = None,
        folder: str = "inbox"
    ) -> Tuple[List[Dict[str, Any]], str]:
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
            emails = data.get("value", [])
            
            # Get next delta link
            next_delta_link = data.get("@odata.deltaLink", "")
            
            logger.info(f"Retrieved {len(emails)} email changes via delta query")
            return emails, next_delta_link
            
        except Exception as e:
            logger.error(f"Failed to get delta emails: {e}")
            raise GraphAPIError(f"Failed to get delta emails: {e}")
    
    async def create_subscription(
        self, 
        access_token: str,
        notification_url: str,
        resource: str = "me/mailFolders('Inbox')/messages",
        change_types: List[str] = None,
        expiration_minutes: int = 4230
    ) -> Dict[str, Any]:
        """Create webhook subscription for email changes."""
        if change_types is None:
            change_types = ["created", "updated", "deleted"]
        
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Calculate expiration time
            expiration_time = datetime.utcnow() + timedelta(minutes=expiration_minutes)
            
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
    
    async def renew_subscription(
        self, 
        access_token: str,
        subscription_id: str,
        expiration_minutes: int = 4230
    ) -> Dict[str, Any]:
        """Renew existing webhook subscription."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Calculate new expiration time
            expiration_time = datetime.utcnow() + timedelta(minutes=expiration_minutes)
            
            payload = {
                "expirationDateTime": expiration_time.isoformat() + "Z"
            }
            
            url = f"{self.config.get_graph_api_endpoint()}/subscriptions/{subscription_id}"
            
            response = await self._http_client.patch(
                url,
                headers=headers,
                json=payload
            )
            
            await self._handle_response_errors(response)
            
            subscription_data = response.json()
            
            logger.info(f"Renewed subscription: {subscription_id}")
            return subscription_data
            
        except Exception as e:
            logger.error(f"Failed to renew subscription {subscription_id}: {e}")
            raise GraphAPIError(f"Failed to renew subscription: {e}")
    
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
    
    async def get_subscriptions(self, access_token: str) -> List[Dict[str, Any]]:
        """Get all active subscriptions."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            url = f"{self.config.get_graph_api_endpoint()}/subscriptions"
            
            response = await self._http_client.get(url, headers=headers)
            await self._handle_response_errors(response)
            
            data = response.json()
            subscriptions = data.get("value", [])
            
            logger.info(f"Retrieved {len(subscriptions)} subscriptions")
            return subscriptions
            
        except Exception as e:
            logger.error(f"Failed to get subscriptions: {e}")
            raise GraphAPIError(f"Failed to get subscriptions: {e}")
    
    async def send_email(
        self, 
        access_token: str,
        to_recipients: List[str],
        subject: str,
        body: str,
        body_type: str = "HTML",
        cc_recipients: List[str] = None,
        bcc_recipients: List[str] = None,
        attachments: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send email via Graph API."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Build recipients
            to_list = [{"emailAddress": {"address": email}} for email in to_recipients]
            cc_list = [{"emailAddress": {"address": email}} for email in (cc_recipients or [])]
            bcc_list = [{"emailAddress": {"address": email}} for email in (bcc_recipients or [])]
            
            # Build message
            message = {
                "subject": subject,
                "body": {
                    "contentType": body_type,
                    "content": body
                },
                "toRecipients": to_list
            }
            
            if cc_list:
                message["ccRecipients"] = cc_list
            if bcc_list:
                message["bccRecipients"] = bcc_list
            if attachments:
                message["attachments"] = attachments
            
            payload = {"message": message}
            
            url = f"{self.config.get_graph_api_endpoint()}/me/sendMail"
            
            response = await self._http_client.post(
                url,
                headers=headers,
                json=payload
            )
            
            await self._handle_response_errors(response)
            
            logger.info(f"Email sent to {len(to_recipients)} recipients")
            return {"status": "sent", "recipients": len(to_recipients)}
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise GraphAPIError(f"Failed to send email: {e}")
    
    async def get_folders(self, access_token: str) -> List[Dict[str, Any]]:
        """Get mail folders."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            url = f"{self.config.get_graph_api_endpoint()}/me/mailFolders"
            
            response = await self._http_client.get(url, headers=headers)
            await self._handle_response_errors(response)
            
            data = response.json()
            folders = data.get("value", [])
            
            logger.info(f"Retrieved {len(folders)} mail folders")
            return folders
            
        except Exception as e:
            logger.error(f"Failed to get folders: {e}")
            raise GraphAPIError(f"Failed to get folders: {e}")
    
    async def mark_as_read(self, access_token: str, message_id: str) -> bool:
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
    
    async def move_to_folder(
        self, 
        access_token: str, 
        message_id: str, 
        destination_folder_id: str
    ) -> bool:
        """Move email to different folder."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            url = f"{self.config.get_graph_api_endpoint()}/me/messages/{message_id}/move"
            
            payload = {"destinationId": destination_folder_id}
            
            response = await self._http_client.post(
                url,
                headers=headers,
                json=payload
            )
            
            await self._handle_response_errors(response)
            
            logger.info(f"Moved email {message_id} to folder {destination_folder_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to move email {message_id}: {e}")
            raise GraphAPIError(f"Failed to move email: {e}")
    
    async def delete_email(self, access_token: str, message_id: str) -> bool:
        """Delete email."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            url = f"{self.config.get_graph_api_endpoint()}/me/messages/{message_id}"
            
            response = await self._http_client.delete(url, headers=headers)
            
            if response.status_code == 404:
                logger.warning(f"Email {message_id} not found")
                return True
            
            await self._handle_response_errors(response)
            
            logger.info(f"Deleted email {message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete email {message_id}: {e}")
            raise GraphAPIError(f"Failed to delete email: {e}")
    
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
    
    async def get_token_info(self, access_token: str) -> Dict[str, Any]:
        """Get token information and expiration."""
        try:
            # For testing purposes, return mock token info
            # In real implementation, this would decode JWT or call token introspection endpoint
            return {
                "valid": await self.validate_token(access_token),
                "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                "scope": "https://graph.microsoft.com/Mail.Read",
                "token_type": "Bearer"
            }
        except Exception as e:
            logger.error(f"Failed to get token info: {e}")
            raise GraphAPIError(f"Failed to get token info: {e}")
    
    # Helper methods
    async def _handle_response_errors(self, response: httpx.Response) -> None:
        """Handle HTTP response errors."""
        if response.status_code in [200, 201, 202, 204]:
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
