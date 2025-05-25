from typing import List, Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import asyncio
import logging

from ..domain.account import Account
from ..domain.email import Email
from ..ports.repository import AccountRepository, EmailRepository, UserRepository
from ..ports.graph_api import GraphAPIPort
from ..ports.config import ConfigPort
from .account_management import AccountManagementUseCase
from .email_detection import EmailDetectionUseCase
from .external_transmission import ExternalTransmissionUseCase


logger = logging.getLogger(__name__)


# Request/Response Models
class MultiAccountSyncRequest(BaseModel):
    """Request for multi-account synchronization."""
    user_ids: Optional[List[UUID]] = Field(None, description="Specific user IDs to sync")
    account_ids: Optional[List[UUID]] = Field(None, description="Specific account IDs to sync")
    sync_active_only: bool = Field(True, description="Only sync active accounts")
    use_delta: bool = Field(True, description="Use delta sync where available")
    parallel_execution: bool = Field(True, description="Execute account syncs in parallel")
    max_concurrent: int = Field(5, description="Maximum concurrent operations")


class AccountSyncResult(BaseModel):
    """Result of single account sync."""
    account_id: UUID
    email: str
    status: str  # success, failed, skipped
    emails_detected: int = 0
    emails_transmitted: int = 0
    error_message: Optional[str] = None
    sync_duration_ms: int = 0
    delta_link_updated: bool = False


class MultiAccountSyncResponse(BaseModel):
    """Response for multi-account synchronization."""
    total_accounts: int
    successful_syncs: int
    failed_syncs: int
    skipped_syncs: int
    account_results: List[AccountSyncResult]
    total_emails_detected: int
    total_emails_transmitted: int
    total_duration_ms: int
    sync_completed_at: datetime = Field(default_factory=lambda: datetime.now())


class TokenRefreshRequest(BaseModel):
    """Request for refreshing tokens across accounts."""
    hours_before_expiry: int = Field(24, description="Refresh tokens expiring within this many hours")
    force_refresh: bool = Field(False, description="Force refresh even if not expiring")


class TokenRefreshResponse(BaseModel):
    """Response for token refresh operation."""
    accounts_checked: int
    tokens_refreshed: int
    tokens_failed: int
    refresh_results: List[Dict[str, Any]]


class WebhookManagementRequest(BaseModel):
    """Request for webhook management."""
    operation: str  # create, renew, delete, list
    account_ids: Optional[List[UUID]] = None
    notification_url: Optional[str] = None
    expiration_hours: int = Field(72, description="Webhook expiration in hours")


class WebhookManagementResponse(BaseModel):
    """Response for webhook management."""
    operation: str
    affected_accounts: int
    successful_operations: int
    failed_operations: int
    webhook_details: List[Dict[str, Any]]


class AccountHealthCheckRequest(BaseModel):
    """Request for checking account health."""
    check_token_validity: bool = True
    check_api_connectivity: bool = True
    check_sync_status: bool = True


class AccountHealthStatus(BaseModel):
    """Health status of single account."""
    account_id: UUID
    email: str
    is_healthy: bool
    token_valid: bool
    token_expires_at: Optional[datetime]
    api_reachable: bool
    last_sync_at: Optional[datetime]
    sync_overdue: bool
    issues: List[str] = Field(default_factory=list)


class AccountHealthCheckResponse(BaseModel):
    """Response for account health check."""
    total_accounts: int
    healthy_accounts: int
    unhealthy_accounts: int
    account_statuses: List[AccountHealthStatus]
    check_completed_at: datetime = Field(default_factory=lambda: datetime.now())


# Main Use Case Implementation
class MultiAccountManagerUseCase:
    """Use case for managing multiple accounts and orchestrating operations."""
    
    def __init__(
        self,
        account_management: AccountManagementUseCase,
        email_detection: EmailDetectionUseCase,
        external_transmission: ExternalTransmissionUseCase,
        account_repository: AccountRepository,
        email_repository: EmailRepository,
        user_repository: UserRepository,
        graph_api: GraphAPIPort,
        config: ConfigPort
    ):
        self.account_management = account_management
        self.email_detection = email_detection
        self.external_transmission = external_transmission
        self.account_repository = account_repository
        self.email_repository = email_repository
        self.user_repository = user_repository
        self.graph_api = graph_api
        self.config = config
    
    async def sync_all_accounts(
        self, 
        request: MultiAccountSyncRequest
    ) -> MultiAccountSyncResponse:
        """
        Synchronize emails across multiple accounts.
        
        This orchestrates:
        1. Account selection based on criteria
        2. Parallel/sequential email detection
        3. External API transmission
        4. Delta link updates
        """
        start_time = datetime.now()
        
        # Get accounts to sync
        accounts = await self._get_accounts_to_sync(request)
        
        # Execute sync operations
        if request.parallel_execution:
            results = await self._sync_accounts_parallel(
                accounts, 
                request.use_delta, 
                request.max_concurrent
            )
        else:
            results = await self._sync_accounts_sequential(
                accounts, 
                request.use_delta
            )
        
        # Aggregate results
        total_emails_detected = sum(r.emails_detected for r in results)
        total_emails_transmitted = sum(r.emails_transmitted for r in results)
        successful_syncs = sum(1 for r in results if r.status == "success")
        failed_syncs = sum(1 for r in results if r.status == "failed")
        skipped_syncs = sum(1 for r in results if r.status == "skipped")
        
        total_duration = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return MultiAccountSyncResponse(
            total_accounts=len(accounts),
            successful_syncs=successful_syncs,
            failed_syncs=failed_syncs,
            skipped_syncs=skipped_syncs,
            account_results=results,
            total_emails_detected=total_emails_detected,
            total_emails_transmitted=total_emails_transmitted,
            total_duration_ms=total_duration
        )
    
    async def refresh_expiring_tokens(
        self, 
        request: TokenRefreshRequest
    ) -> TokenRefreshResponse:
        """
        Refresh tokens that are expiring soon across all accounts.
        """
        accounts = await self.account_repository.find_active_accounts()
        
        expiry_threshold = datetime.now() + timedelta(hours=request.hours_before_expiry)
        accounts_to_refresh = []
        
        for account in accounts:
            if request.force_refresh or (
                account.token_expires_at and 
                account.token_expires_at <= expiry_threshold
            ):
                accounts_to_refresh.append(account)
        
        refresh_results = []
        tokens_refreshed = 0
        tokens_failed = 0
        
        for account in accounts_to_refresh:
            try:
                success = await self.account_management.refresh_account_token(account.id)
                if success:
                    tokens_refreshed += 1
                    refresh_results.append({
                        "account_id": str(account.id),
                        "email": account.email_address,
                        "status": "refreshed"
                    })
                else:
                    tokens_failed += 1
                    refresh_results.append({
                        "account_id": str(account.id),
                        "email": account.email_address,
                        "status": "failed",
                        "error": "Token refresh failed"
                    })
            except Exception as e:
                tokens_failed += 1
                refresh_results.append({
                    "account_id": str(account.id),
                    "email": account.email_address,
                    "status": "failed",
                    "error": str(e)
                })
        
        return TokenRefreshResponse(
            accounts_checked=len(accounts),
            tokens_refreshed=tokens_refreshed,
            tokens_failed=tokens_failed,
            refresh_results=refresh_results
        )
    
    async def manage_webhooks(
        self, 
        request: WebhookManagementRequest
    ) -> WebhookManagementResponse:
        """
        Manage webhooks across multiple accounts.
        """
        # Get target accounts
        if request.account_ids:
            accounts = []
            for account_id in request.account_ids:
                account = await self.account_repository.find_by_id(account_id)
                if account:
                    accounts.append(account)
        else:
            accounts = await self.account_repository.find_active_accounts()
        
        webhook_details = []
        successful_operations = 0
        failed_operations = 0
        
        for account in accounts:
            try:
                if request.operation == "create":
                    result = await self._create_webhook_for_account(
                        account, 
                        request.notification_url,
                        request.expiration_hours
                    )
                elif request.operation == "renew":
                    result = await self._renew_webhook_for_account(
                        account,
                        request.expiration_hours
                    )
                elif request.operation == "delete":
                    result = await self._delete_webhook_for_account(account)
                elif request.operation == "list":
                    result = await self._list_webhooks_for_account(account)
                else:
                    result = {"error": f"Unknown operation: {request.operation}"}
                
                if "error" not in result:
                    successful_operations += 1
                else:
                    failed_operations += 1
                
                webhook_details.append({
                    "account_id": str(account.id),
                    "email": account.email_address,
                    **result
                })
                
            except Exception as e:
                failed_operations += 1
                webhook_details.append({
                    "account_id": str(account.id),
                    "email": account.email_address,
                    "error": str(e)
                })
        
        return WebhookManagementResponse(
            operation=request.operation,
            affected_accounts=len(accounts),
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            webhook_details=webhook_details
        )
    
    async def check_accounts_health(
        self, 
        request: AccountHealthCheckRequest
    ) -> AccountHealthCheckResponse:
        """
        Check health status of all accounts.
        """
        accounts = await self.account_repository.find_all()
        
        account_statuses = []
        healthy_accounts = 0
        unhealthy_accounts = 0
        
        for account in accounts:
            status = await self._check_account_health(account, request)
            account_statuses.append(status)
            
            if status.is_healthy:
                healthy_accounts += 1
            else:
                unhealthy_accounts += 1
        
        return AccountHealthCheckResponse(
            total_accounts=len(accounts),
            healthy_accounts=healthy_accounts,
            unhealthy_accounts=unhealthy_accounts,
            account_statuses=account_statuses
        )
    
    async def schedule_periodic_sync(
        self,
        interval_minutes: int = 5,
        max_duration_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Schedule periodic synchronization of all accounts.
        """
        logger.info(f"Starting periodic sync with {interval_minutes} minute interval")
        
        start_time = datetime.now()
        max_end_time = start_time + timedelta(minutes=max_duration_minutes)
        
        sync_count = 0
        total_emails = 0
        
        while datetime.now() < max_end_time:
            try:
                # Run sync
                sync_request = MultiAccountSyncRequest(
                    sync_active_only=True,
                    use_delta=True,
                    parallel_execution=True
                )
                
                result = await self.sync_all_accounts(sync_request)
                
                sync_count += 1
                total_emails += result.total_emails_detected
                
                logger.info(
                    f"Periodic sync #{sync_count} completed. "
                    f"Emails detected: {result.total_emails_detected}"
                )
                
                # Check if we should continue
                if datetime.now() + timedelta(minutes=interval_minutes) >= max_end_time:
                    break
                
                # Wait for next interval
                await asyncio.sleep(interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"Error in periodic sync: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
        
        return {
            "sync_count": sync_count,
            "total_emails_detected": total_emails,
            "duration_minutes": int((datetime.now() - start_time).total_seconds() / 60)
        }
    
    # Private helper methods
    async def _get_accounts_to_sync(
        self, 
        request: MultiAccountSyncRequest
    ) -> List[Account]:
        """Get accounts based on sync request criteria."""
        if request.account_ids:
            # Specific accounts requested
            accounts = []
            for account_id in request.account_ids:
                account = await self.account_repository.find_by_id(account_id)
                if account:
                    accounts.append(account)
        elif request.user_ids:
            # Accounts for specific users
            accounts = []
            for user_id in request.user_ids:
                user_accounts = await self.account_repository.find_by_user_id(user_id)
                accounts.extend(user_accounts)
        else:
            # All accounts
            if request.sync_active_only:
                accounts = await self.account_repository.find_active_accounts()
            else:
                accounts = await self.account_repository.find_all()
        
        return accounts
    
    async def _sync_accounts_parallel(
        self, 
        accounts: List[Account], 
        use_delta: bool,
        max_concurrent: int
    ) -> List[AccountSyncResult]:
        """Sync accounts in parallel with concurrency limit."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def sync_with_semaphore(account):
            async with semaphore:
                return await self._sync_single_account(account, use_delta)
        
        tasks = [sync_with_semaphore(account) for account in accounts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(AccountSyncResult(
                    account_id=accounts[i].id,
                    email=accounts[i].email_address,
                    status="failed",
                    error_message=str(result)
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    async def _sync_accounts_sequential(
        self, 
        accounts: List[Account], 
        use_delta: bool
    ) -> List[AccountSyncResult]:
        """Sync accounts sequentially."""
        results = []
        
        for account in accounts:
            try:
                result = await self._sync_single_account(account, use_delta)
                results.append(result)
            except Exception as e:
                results.append(AccountSyncResult(
                    account_id=account.id,
                    email=account.email_address,
                    status="failed",
                    error_message=str(e)
                ))
        
        return results
    
    async def _sync_single_account(
        self, 
        account: Account, 
        use_delta: bool
    ) -> AccountSyncResult:
        """Sync single account."""
        start_time = datetime.now()
        
        try:
            # Check if account is ready
            if not account.is_sync_ready():
                return AccountSyncResult(
                    account_id=account.id,
                    email=account.email_address,
                    status="skipped",
                    error_message="Account not ready for sync"
                )
            
            # Detect emails
            detection_result = await self.email_detection.detect_email_changes({
                "account_id": account.id,
                "method": "delta_query" if use_delta else "polling",
                "delta_link": account.delta_link if use_delta else None
            })
            
            emails_detected = detection_result.total_changes
            
            # Transmit emails
            transmission_result = await self.external_transmission.process_pending_transmissions(
                limit=100,
                priority_order=True
            )
            
            emails_transmitted = transmission_result.successful_transmissions
            
            # Update delta link if changed
            delta_link_updated = False
            if detection_result.new_delta_link and detection_result.new_delta_link != account.delta_link:
                await self.account_repository.update_sync_info(
                    account.id,
                    detection_result.new_delta_link
                )
                delta_link_updated = True
            
            sync_duration = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return AccountSyncResult(
                account_id=account.id,
                email=account.email_address,
                status="success",
                emails_detected=emails_detected,
                emails_transmitted=emails_transmitted,
                sync_duration_ms=sync_duration,
                delta_link_updated=delta_link_updated
            )
            
        except Exception as e:
            sync_duration = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return AccountSyncResult(
                account_id=account.id,
                email=account.email_address,
                status="failed",
                error_message=str(e),
                sync_duration_ms=sync_duration
            )
    
    async def _check_account_health(
        self, 
        account: Account, 
        request: AccountHealthCheckRequest
    ) -> AccountHealthStatus:
        """Check health of single account."""
        issues = []
        
        # Check token validity
        token_valid = False
        if request.check_token_validity:
            token_valid = account.is_token_valid()
            if not token_valid:
                issues.append("Token expired or invalid")
        
        # Check API connectivity
        api_reachable = False
        if request.check_api_connectivity and account.access_token:
            try:
                api_reachable = await self.graph_api.validate_token(account.access_token)
                if not api_reachable:
                    issues.append("Graph API not reachable")
            except Exception as e:
                issues.append(f"API connectivity check failed: {str(e)}")
        
        # Check sync status
        sync_overdue = False
        if request.check_sync_status:
            if account.last_sync_at:
                hours_since_sync = (datetime.now() - account.last_sync_at).total_seconds() / 3600
                if hours_since_sync > 24:  # Consider overdue if > 24 hours
                    sync_overdue = True
                    issues.append(f"Last sync was {int(hours_since_sync)} hours ago")
            else:
                sync_overdue = True
                issues.append("Account never synced")
        
        # Overall health
        is_healthy = (
            token_valid and 
            api_reachable and 
            not sync_overdue and 
            account.is_active()
        )
        
        return AccountHealthStatus(
            account_id=account.id,
            email=account.email_address,
            is_healthy=is_healthy,
            token_valid=token_valid,
            token_expires_at=account.token_expires_at,
            api_reachable=api_reachable,
            last_sync_at=account.last_sync_at,
            sync_overdue=sync_overdue,
            issues=issues
        )
    
    async def _create_webhook_for_account(
        self, 
        account: Account, 
        notification_url: str,
        expiration_hours: int
    ) -> Dict[str, Any]:
        """Create webhook for account."""
        # Implementation would use email_detection.create_webhook_subscription
        return {
            "status": "created",
            "webhook_id": "mock_webhook_id",
            "expires_at": (datetime.now() + timedelta(hours=expiration_hours)).isoformat()
        }
    
    async def _renew_webhook_for_account(
        self, 
        account: Account,
        expiration_hours: int
    ) -> Dict[str, Any]:
        """Renew webhook for account."""
        # Implementation would use email_detection.renew_webhook_subscription
        return {
            "status": "renewed",
            "webhook_id": "mock_webhook_id",
            "expires_at": (datetime.now() + timedelta(hours=expiration_hours)).isoformat()
        }
    
    async def _delete_webhook_for_account(self, account: Account) -> Dict[str, Any]:
        """Delete webhook for account."""
        # Implementation would use graph_api.delete_subscription
        return {"status": "deleted"}
    
    async def _list_webhooks_for_account(self, account: Account) -> Dict[str, Any]:
        """List webhooks for account."""
        # Implementation would use graph_api.get_subscriptions
        return {"status": "listed", "webhooks": []}
